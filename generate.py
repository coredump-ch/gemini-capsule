import os
import urllib.parse

import requests
from bs4 import BeautifulSoup


def clean_text(text):
    return " ".join(text.split())


def download_image(url, target_dir="content/images"):
    """Download an image and return the local path"""
    try:
        os.makedirs(target_dir, exist_ok=True)

        # Extract filename or generate one
        filename = os.path.basename(urllib.parse.urlparse(url).path)
        if not filename or "." not in filename:
            filename = f"image_{hash(url) % 100000}.jpg"

        local_path = os.path.join(target_dir, filename)

        if not os.path.exists(local_path):
            resp = requests.get(url)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
            print(f"Downloaded image: {filename}")

        return local_path
    except Exception as e:
        print(f"Failed to download image {url}: {e}")
        return url


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
            if element.name in ("h1", "h2", "h3"):
                level = int(element.name[1])
                gmi_lines.append(f"{'#' * level} {clean_text(element.get_text())}")
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
                        text = img.get("alt") or os.path.basename(str(img.get("src", "")))

                if href and text:
                    href_str = str(href)

                    # Check if this is an image link
                    if any(
                        href_str.lower().endswith(ext)
                        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                    ):
                        # Download the image and link to local version
                        if href_str.startswith("/"):
                            img_url = "https://www.coredump.ch" + href_str
                        else:
                            img_url = href_str

                        local_path = download_image(img_url)
                        relative_path = os.path.relpath(
                            local_path,
                            os.path.join("content", os.path.dirname(target_filename)),
                        )
                        gmi_lines.append(f"=> {relative_path} {text}")
                    else:
                        # Link rewriting for regular links
                        normalized_href = href_str
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
                            if href_str.startswith("/"):
                                href_str = "https://www.coredump.ch" + href_str
                            gmi_lines.append(f"=> {href_str} {text}")

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
