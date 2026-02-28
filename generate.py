import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup


def clean_text(text):
    return " ".join(text.split())


def wp_full_size_url(url: str) -> str:
    """Strip WordPress thumbnail size suffix (e.g. -150x150, -675x380) from a URL."""
    return re.sub(r"-\d+x\d+(\.[a-zA-Z]+)$", r"\1", url)


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


def fetch_blog_posts_from_rss(feed_url="https://www.coredump.ch/feed/"):
    """Fetch and parse the WordPress RSS feed, returning a list of post dicts."""
    try:
        response = requests.get(feed_url)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch RSS feed: {e}")
        return []

    ns = {
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "atom": "http://www.w3.org/2005/Atom",
        "sy": "http://purl.org/rss/1.0/modules/syndication/",
    }

    root = ET.fromstring(response.content)
    channel = root.find("channel")
    if channel is None:
        print("RSS feed has no <channel> element")
        return []

    posts = []
    for item in channel.findall("item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()
        author = item.findtext("dc:creator", "", ns).strip()
        description = item.findtext("description", "").strip()

        categories = [cat.text.strip() for cat in item.findall("category") if cat.text]

        # Parse publication date
        try:
            pub_date = parsedate_to_datetime(pub_date_str)
            date_iso = pub_date.strftime("%Y-%m-%d")
            year = pub_date.strftime("%Y")
            month = pub_date.strftime("%m")
        except Exception:
            date_iso = ""
            year = ""
            month = ""

        # Extract slug from WordPress URL: /YYYY/MM/DD/slug/
        slug = ""
        parsed = urllib.parse.urlparse(link)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        # WordPress blog URL pattern: YYYY/MM/DD/slug
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
            slug = parts[3]
        elif len(parts) >= 1:
            slug = parts[-1]

        # Build the gemini content path: gemlog/YYYY/MM/slug.gmi
        if year and month and slug:
            gmi_path = f"gemlog/{year}/{month}/{slug}.gmi"
        else:
            gmi_path = f"gemlog/{slug}.gmi"

        posts.append(
            {
                "title": title,
                "url": link,
                "date": date_iso,
                "year": year,
                "month": month,
                "slug": slug,
                "author": author,
                "description": description,
                "categories": categories,
                "gmi_path": gmi_path,
            }
        )

    return posts


def convert_blog_post_to_gemini(post, pages_map):
    """Fetch and convert a single blog post to Gemtext."""
    url = post["url"]
    target_filename = post["gmi_path"]

    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    gmi_lines = []

    # Title
    title = post["title"]
    gmi_lines.append(f"# {title}")
    gmi_lines.append("")

    # Metadata block
    if post["date"]:
        gmi_lines.append(f"Datum: {post['date']}")
    if post["author"]:
        gmi_lines.append(f"Autor: {post['author']}")
    if post["categories"]:
        gmi_lines.append(f"Kategorien: {', '.join(post['categories'])}")
    gmi_lines.append("")

    # Main article content
    content = soup.find("article")
    if not content:
        content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("main")

    if content:
        # Remove unwanted elements (navigation, share buttons, comments, etc.)
        for unwanted in content.find_all(
            class_=[
                "entry-footer",
                "post-navigation",
                "sharedaddy",
                "jp-relatedposts",
                "comments-area",
                "widget_space_api_widget",
                "entry-header",
                "post-thumbnail",
            ]
        ):
            unwanted.decompose()
        for unwanted in content.find_all(["nav", "footer", "aside"]):
            unwanted.decompose()

        # Find the actual entry-content div if we grabbed article
        entry_content = content.find("div", class_="entry-content")
        if entry_content:
            content = entry_content

        _convert_content_to_gmi(content, gmi_lines, target_filename, pages_map, post_url=url)
    else:
        gmi_lines.append("(Inhalt konnte nicht extrahiert werden)")
        gmi_lines.append(f"=> {url} Original auf coredump.ch lesen")

    gmi_lines.append("")
    gmi_lines.append("---")
    gmi_lines.append("")

    # Navigation links back
    depth = len(target_filename.split("/"))  # gemlog/YYYY/MM/slug.gmi -> 4 parts
    back_prefix = "../" * (depth - 1)
    gmi_lines.append(f"=> /gemlog/index.gmi Zurück zum Gemlog")
    gmi_lines.append(f"=> /index.gmi Zurück zur Startseite")
    gmi_lines.append(f"=> {url} Auf coredump.ch lesen")

    return "\n".join(gmi_lines)


def _convert_content_to_gmi(content, gmi_lines, target_filename, pages_map, post_url=None):
    """Walk through BeautifulSoup content and append Gemtext lines."""
    seen_texts = set()

    for element in content.find_all(
        ["h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "a", "img", "figure", "pre", "blockquote"],
        recursive=True,
    ):
        # Skip elements nested inside already-processed parents to avoid duplication
        # We handle lists by processing li directly
        if element.name in ("h1", "h2", "h3", "h4"):
            text = clean_text(element.get_text())
            if text and text not in seen_texts:
                seen_texts.add(text)
                level = int(element.name[1])
                # Clamp to max ## to keep # for title
                level = min(level + 1, 3)
                gmi_lines.append(f"{'#' * level} {text}")

        elif element.name == "p":
            # Skip if parent is a list item or blockquote (handled elsewhere)
            if element.parent and element.parent.name in ("li", "blockquote"):
                continue
            for br in element.find_all("br"):
                br.replace_with("\n")
            lines = element.get_text().split("\n")
            added = False
            for line in lines:
                cleaned = clean_text(line)
                if cleaned:
                    gmi_lines.append(cleaned)
                    added = True
            if added:
                gmi_lines.append("")

        elif element.name == "pre":
            code_text = element.get_text()
            if code_text.strip():
                gmi_lines.append("```")
                gmi_lines.append(code_text.rstrip())
                gmi_lines.append("```")
                gmi_lines.append("")

        elif element.name == "blockquote":
            text = clean_text(element.get_text())
            if text:
                gmi_lines.append(f"> {text}")
                gmi_lines.append("")

        elif element.name == "li":
            # Only direct li children of ul/ol (not nested li inside li)
            text = clean_text(element.get_text())
            if text:
                gmi_lines.append(f"* {text}")

        elif element.name in ("ul", "ol"):
            # Add a blank line after list blocks
            # Check if next sibling is not another list item
            gmi_lines.append("")

        elif element.name == "a":
            # Only render standalone links (not inside p/li/h* — those are handled by their parent)
            if element.parent and element.parent.name in ("p", "li", "h1", "h2", "h3", "h4"):
                continue

            href = element.get("href")
            text = clean_text(element.get_text())

            # For links wrapping an <img>, derive text from alt only (no filename fallback)
            inner_img = element.find("img")
            if not text and inner_img:
                text = clean_text(inner_img.get("alt", ""))

            if not href:
                continue

            href_str = str(href)

            # Skip self-referencing links (e.g. WordPress title anchor permalink)
            if post_url:
                norm_post = post_url if post_url.endswith("/") else post_url + "/"
                norm_href_check = href_str if href_str.endswith("/") else href_str + "/"
                if norm_href_check == norm_post:
                    continue

            # If the <a> wraps an <img>, treat it as an image link regardless of href.
            # WordPress galleries link to attachment pages (HTML), but the real image
            # URL can be found in the nested <img> (prefer data-orig-file or data-large-file
            # over the thumbnail src).
            if inner_img:
                img_src = (
                    inner_img.get("data-orig-file")
                    or inner_img.get("data-large-file")
                    or wp_full_size_url(inner_img.get("src", ""))
                )
                if img_src:
                    if img_src.startswith("/"):
                        img_url = "https://www.coredump.ch" + img_src
                    else:
                        img_url = img_src
                    if img_url.startswith("http"):
                        local_path = download_image(img_url)
                        abs_path = "/" + local_path.removeprefix("content/")
                        line = f"=> {abs_path}"
                        if text:
                            line += f" {text}"
                        gmi_lines.append(line)
                continue

            if not text:
                continue

            if any(
                href_str.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
            ):
                if href_str.startswith("/"):
                    img_url = "https://www.coredump.ch" + href_str
                else:
                    img_url = href_str
                local_path = download_image(img_url)
                abs_path = "/" + local_path.removeprefix("content/")
                gmi_lines.append(f"=> {abs_path} {text}")
            else:
                full_url = href_str
                if full_url.startswith("/"):
                    full_url = "https://www.coredump.ch" + full_url

                norm_href = full_url if full_url.endswith("/") else full_url + "/"
                link_target = full_url

                for page_url, page_filename in pages_map.items():
                    norm_page_url = page_url if page_url.endswith("/") else page_url + "/"
                    if norm_href == norm_page_url:
                        link_target = "/" + page_filename
                        break

                gmi_lines.append(f"=> {link_target} {text}")

        elif element.name == "img":
            # Standalone images (not inside <a>)
            if element.parent and element.parent.name == "a":
                continue
            src = element.get("src", "")
            alt = clean_text(element.get("alt", ""))
            if src:
                if src.startswith("/"):
                    img_url = "https://www.coredump.ch" + src
                else:
                    img_url = src
                if img_url.startswith("http"):
                    local_path = download_image(img_url)
                    abs_path = "/" + local_path.removeprefix("content/")
                    line = f"=> {abs_path}"
                    if alt:
                        line += f" {alt}"
                    gmi_lines.append(line)

        elif element.name == "figure":
            # Figures are handled via their img/a children above
            pass


def generate_gemlog_index(posts):
    """Generate the subscribable gemlog index page."""
    gmi_lines = []
    gmi_lines.append("# Coredump Gemlog")
    gmi_lines.append("## Hacker- und Makerspace in Rapperswil-Jona")
    gmi_lines.append("")
    gmi_lines.append("Willkommen beim Coredump Blog im Gemini-Format.")
    gmi_lines.append("Dieser Gemlog kann von Gemini-Clients wie Lagrange abonniert werden.")
    gmi_lines.append("")

    for post in posts:
        date = post["date"]
        title = post["title"]
        gmi_path = post["gmi_path"]
        # Path relative to gemlog/index.gmi -> gemlog/YYYY/MM/slug.gmi
        # so relative link is YYYY/MM/slug.gmi
        rel_path = "/".join(gmi_path.split("/")[1:])  # strip "gemlog/" prefix
        gmi_lines.append(f"=> {rel_path} {date} - {title}")

    gmi_lines.append("")
    gmi_lines.append("=> /index.gmi Zurück zur Startseite")
    gmi_lines.append("=> https://www.coredump.ch/blog/ Blog auf coredump.ch")

    return "\n".join(gmi_lines)


def convert_to_gemini(url, target_filename, pages_map):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    gmi_lines = []

    # Title
    title = soup.title.string if soup.title else "Coredump"
    gmi_lines.append(f"# {title}")
    gmi_lines.append("")
    if target_filename == "index.gmi":
        gmi_lines.append("```")
        gmi_lines.append(r"""
  ___ ___  _ __ ___  __| |_   _ _ __ ___  _ __
 / __/ _ \| `__/ _ \/ _' | | | | `_ ' _ \| '_ \
| (_| (_) | | |  __/ (_| | |_| | | | | | | |_) |
 \___\___/|_|  \___|\__,_|\__,_|_| |_| |_| .__/
                                         |_|""")
        gmi_lines.append("```")

    # Main content - focusing on the main or entry-content
    content = soup.find("main")
    if not content:
        content = soup.find("div", class_="entry-content")

    if content:
        # Remove opening status widget
        for widget in content.find_all(class_="widget_space_api_widget"):
            widget.decompose()

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
                        text = clean_text(img.get("alt", ""))

                if href:
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
                        abs_path = "/" + local_path.removeprefix("content/")
                        line = f"=> {abs_path}"
                        if text:
                            line += f" {text}"
                        gmi_lines.append(line)
                    else:
                        # Normalize the link
                        full_url = href_str
                        if full_url.startswith("/"):
                            full_url = "https://www.coredump.ch" + full_url

                        # Try to match with internal pages
                        norm_href = full_url if full_url.endswith("/") else full_url + "/"
                        link_target = full_url

                        for page_url, page_filename in pages_map.items():
                            norm_page_url = page_url if page_url.endswith("/") else page_url + "/"
                            if norm_href == norm_page_url:
                                link_target = "/" + page_filename
                                break

                        if text:
                            gmi_lines.append(f"=> {link_target} {text}")

    # Fallback if no specific content found
    if len(gmi_lines) <= 2:
        gmi_lines.append("Could not extract main content. Please visit the website directly.")
        gmi_lines.append(f"=> {url} Coredump Website")

    return "\n".join(gmi_lines)


def main():
    static_pages = {
        "https://www.coredump.ch/": "index.gmi",
        "https://www.coredump.ch/kontakt/": "kontakt.gmi",
        "https://www.coredump.ch/der-verein/mitgliedschaft/": "der-verein/mitgliedschaft.gmi",
        "https://www.coredump.ch/der-verein/gonner-und-sponsoren/": (
            "der-verein/gonner-und-sponsoren.gmi"
        ),
    }

    os.makedirs("content", exist_ok=True)

    # --- Fetch blog posts from RSS ---
    print("Fetching blog posts from RSS feed...")
    posts = fetch_blog_posts_from_rss()
    print(f"Found {len(posts)} blog posts.")

    # Build pages_map: includes static pages + all blog posts
    pages_map = dict(static_pages)
    pages_map["https://www.coredump.ch/blog/"] = "gemlog/index.gmi"
    for post in posts:
        pages_map[post["url"]] = post["gmi_path"]

    # --- Generate static pages ---
    for url, filename in static_pages.items():
        print(f"Fetching and converting {url} to {filename}...")
        try:
            gmi_content = convert_to_gemini(url, filename, pages_map)
            target_path = os.path.join("content", filename)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w") as f:
                f.write(gmi_content)
            print(f"Successfully generated {target_path}")
        except Exception as e:
            print(f"Error converting {url}: {e}")

    # --- Generate gemlog index ---
    print("Generating gemlog/index.gmi (subscribable gemlog)...")
    os.makedirs("content/gemlog", exist_ok=True)
    gemlog_index = generate_gemlog_index(posts)
    with open("content/gemlog/index.gmi", "w") as f:
        f.write(gemlog_index)
    print("Successfully generated content/gemlog/index.gmi")

    # --- Generate individual blog post pages ---
    print(f"Generating {len(posts)} individual blog post pages...")
    for i, post in enumerate(posts):
        target_path = os.path.join("content", post["gmi_path"])
        print(f"  [{i + 1}/{len(posts)}] {post['title']} -> {target_path}")
        try:
            gmi_content = convert_blog_post_to_gemini(post, pages_map)
            if gmi_content:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    f.write(gmi_content)
        except Exception as e:
            print(f"  Error: {e}")

    print("\nDone!")


if __name__ == "__main__":
    main()
