import requests
from bs4 import BeautifulSoup
import os

def clean_text(text):
    return " ".join(text.split())

def convert_to_gemini(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    gmi_lines = []

    # Title
    title = soup.title.string if soup.title else "Coredump"
    gmi_lines.append(f"# {title}")
    gmi_lines.append("")

    # Main content - focusing on the entry-content or similar
    content = soup.find('div', class_='entry-content')
    if not content:
        content = soup.find('main')
    
    if content:
        for element in content.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'li', 'a']):
            if element.name == 'h1':
                gmi_lines.append(f"# {clean_text(element.get_text())}")
            elif element.name == 'h2':
                gmi_lines.append(f"## {clean_text(element.get_text())}")
            elif element.name == 'h3':
                gmi_lines.append(f"### {clean_text(element.get_text())}")
            elif element.name == 'p':
                text = clean_text(element.get_text())
                if text:
                    gmi_lines.append(text)
                    gmi_lines.append("")
            elif element.name == 'li':
                gmi_lines.append(f"* {clean_text(element.get_text())}")
            elif element.name == 'a':
                href = element.get('href')
                text = clean_text(element.get_text())
                if href and text:
                    if href.startswith('/'):
                        href = "https://www.coredump.ch" + href
                    gmi_lines.append(f"=> {href} {text}")

    # Fallback if no specific content found
    if len(gmi_lines) <= 2:
        gmi_lines.append("Could not extract main content. Please visit the website directly.")
        gmi_lines.append(f"=> {url} Coredump Website")

    return "\n".join(gmi_lines)

def main():
    url = "https://www.coredump.ch/"
    print(f"Fetching and converting {url}...")
    try:
        gmi_content = convert_to_gemini(url)
        
        os.makedirs("content", exist_ok=True)
        with open("content/index.gmi", "w") as f:
            f.write(gmi_content)
        
        print("Successfully generated content/index.gmi")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
