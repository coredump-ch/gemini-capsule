import os

import requests
from bs4 import BeautifulSoup


def clean_text(text):
    return " ".join(text.split())


def get_relative_path(from_path, to_path):
    """
    Calculate relative path from one file to another.
    Example: from_path='der-verein/mitgliedschaft.gmi', to_path='index.gmi'
             returns '../index.gmi'
    """
    from_dir = os.path.dirname(from_path)
    if not from_dir:
        return to_path

    # Simple relative path calculation for the current use case
    levels = from_dir.count("/") + 1
    return "../" * levels + to_path


def convert_to_gemini(url, target_filename, pages_map):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    gmi_lines = []

    # Title
    title = soup.title.string if soup.title else "Coredump"
    gmi_lines.append(f"# {title}")
    gmi_lines.append("")

    # Main content - focusing on the entry-content or similar
    content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("main")

    if content:
        for element in content.find_all(["h1", "h2", "h3", "p", "ul", "li", "a"]):
            if element.name == "h1":
                gmi_lines.append(f"# {clean_text(element.get_text())}")
            elif element.name == "h2":
                gmi_lines.append(f"## {clean_text(element.get_text())}")
            elif element.name == "h3":
                gmi_lines.append(f"### {clean_text(element.get_text())}")
            elif element.name == "p":
                # Handle <br> tags within paragraphs
                for br in element.find_all("br"):
                    br.replace_with("\n")
                # Clean each line individually to preserve line breaks
                lines = element.get_text().split("\n")
                for line in lines:
                    cleaned = clean_text(line)
                    if cleaned:
                        gmi_lines.append(cleaned)
                gmi_lines.append("")
            elif element.name == "li":
                text = clean_text(element.get_text())
                if text:
                    gmi_lines.append(f"* {text}")
            elif element.name == "a":
                href = element.get("href")
                text = clean_text(element.get_text())
                if not text:
                    img = element.find("img")
                    if img:
                        text = img.get("alt") or os.path.basename(img.get("src", ""))

                if href and text:
                    # Link rewriting
                    # Normalize href for matching
                    normalized_href = href
                    if normalized_href.startswith("/"):
                        normalized_href = "https://www.coredump.ch" + normalized_href
                    if not normalized_href.endswith("/"):
                        normalized_href += "/"

                    link_rewritten = False
                    for page_url, page_filename in pages_map.items():
                        # Normalize page_url for matching
                        norm_page_url = page_url
                        if not norm_page_url.endswith("/"):
                            norm_page_url += "/"

                        if normalized_href == norm_page_url:
                            # Calculate relative path
                            relative_href = os.path.relpath(
                                page_filename, os.path.dirname(target_filename)
                            )
                            gmi_lines.append(f"=> {relative_href} {text}")
                            link_rewritten = True
                            break

                    if not link_rewritten:
                        if href.startswith("/"):
                            href = "https://www.coredump.ch" + href
                        gmi_lines.append(f"=> {href} {text}")

    # Fallback if no specific content found
    if len(gmi_lines) <= 2:
        gmi_lines.append("Could not extract main content. Please visit the website directly.")
        gmi_lines.append(f"=> {url} Coredump Website")

    return "\n".join(gmi_lines)


def main():
    pages = {
        "https://www.coredump.ch/": "index.gmi",
        "https://www.coredump.ch/kontakt/": "kontakt.gmi",
        "https://www.coredump.ch/der-verein/mitgliedschaft/": "der-verein/mitgliedschaft.gmi",
        "https://www.coredump.ch/der-verein/gonner-und-sponsoren/": (
            "der-verein/gonner-und-sponsoren.gmi"
        ),
    }

    os.makedirs("content", exist_ok=True)

    for url, filename in pages.items():
        print(f"Fetching and converting {url} to {filename}...")
        try:
            gmi_content = convert_to_gemini(url, filename, pages)

            target_path = os.path.join("content", filename)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w") as f:
                f.write(gmi_content)

            print(f"Successfully generated {target_path}")
        except Exception as e:
            print(f"Error converting {url}: {e}")


if __name__ == "__main__":
    main()
