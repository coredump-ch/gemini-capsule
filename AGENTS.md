# AGENTS.md - Development Guidelines for Gemini Capsule

This document contains guidelines and conventions for agentic coding agents working on the gemini-capsule project.

## Project Overview

Gemini Capsule is a Python-based content mirroring application that converts WordPress websites to Gemini protocol format (Gemtext). The project uses a multi-container Docker setup with Python for content generation and Rust (agate) for serving.

## Build, Lint, and Test Commands

### Content Generation
```bash
uv run generate.py          # Generate Gemini content from website
```

### Docker Commands
```bash
docker build -t gemini-capsule .                    # Build image
docker run -p 1965:1965 -v gemini_certs:/app/certs gemini-capsule  # Run container
docker-compose up -d                               # Run with Compose (recommended)
```

### Development Environment
```bash
# Install dependencies
uv sync

# Run content generation
uv run generate.py
```

### Testing
**Note:** No automated testing framework is currently configured. When implementing tests, use pytest:
```bash
uv add pytest --dev
uv run pytest tests/                # Run all tests
uv run pytest tests/test_module.py  # Run single test file
uv run pytest -k test_function      # Run specific test
```

### Linting and Formatting
**Note:** Linting tools are not currently configured. Recommended setup:
```bash
uv add ruff --dev
uv run ruff check .                  # Lint code
uv run ruff format .                 # Format code
uv run ruff check --fix .            # Auto-fix linting issues
```

## Code Style Guidelines

### Python Conventions

#### Import Style
Follow standard Python import ordering:
```python
import os
import urllib.parse

import requests
from bs4 import BeautifulSoup
```

#### Naming Conventions
- **Functions:** `snake_case` with descriptive verbs (`download_image`, `convert_to_gemini`)
- **Variables:** `snake_case` with descriptive nouns (`target_filename`, `local_path`)
- **Constants:** `UPPER_CASE` (when defined)
- **Files:** `snake_case.py` for modules

#### Code Structure
```python
def function_name(param1: type, param2: type) -> return_type:
    """Brief docstring describing the function."""
    try:
        # Main logic
        result = operation()
        return result
    except SpecificException as e:
        print(f"Failed to <operation>: {e}")
        return fallback_value
```

#### Error Handling Pattern
Always use specific exception handling with fallback behavior:
```python
try:
    response = requests.get(url)
    response.raise_for_status()
    # Success handling
except Exception as e:
    print(f"Failed to download {url}: {e}")
    return original_url  # Return fallback
```

### File Operations
Always use `os.path.join()` for cross-platform compatibility:
```python
local_path = os.path.join(target_dir, filename)
target_path = os.path.join("content", filename)
```

### String Formatting
Use f-strings for all string formatting:
```python
gmi_lines.append(f"# {title}")
print(f"Downloaded image: {filename}")
```

### Documentation
- Add docstrings for all non-trivial functions
- Keep docstrings concise and descriptive
- Include parameter descriptions for complex functions

## Dependencies and Package Management

### Core Dependencies
- `beautifulsoup4~=4.14.3` - HTML parsing
- `requests~=2.32.5` - HTTP requests

### Adding Dependencies
```bash
uv add package_name          # Production dependency
uv add package_name --dev    # Development dependency
```

## Architecture Guidelines

### Content Processing Flow
1. **Scraping:** Fetch HTML content from WordPress site
2. **Parsing:** Extract main content using BeautifulSoup
3. **Conversion:** Transform HTML to Gemtext format
4. **Asset Handling:** Download and localize images
5. **Link Rewriting:** Convert absolute links to relative paths

### Directory Structure
```
content/
├── index.gmi                 # Main page
├── kontakt.gmi               # Contact page
├── der-verein/              # Subdirectory
│   ├── mitgliedschaft.gmi
│   └── gonner-und-sponsoren.gmi
└── images/                  # Downloaded assets
    └── *.jpg
```

### Gemini Format Guidelines
- Use `#` for main titles, `##` for sections, `###` for subsections
- Use `* ` for list items
- Use `=> URL text` for links
- Separate paragraphs with blank lines
- Clean whitespace with `" ".join(text.split())`

## Environment Configuration

### Required Environment Variables
- `GEMINI_HOSTNAME`: Server hostname (optional, defaults to localhost)

### Docker Development
- Use multi-stage builds for final image
- Expose port 1965 (standard Gemini port)
- Mount volume for certificates at `/app/certs`

## Contributing Guidelines

### Code Review Checklist
- [ ] Functions have descriptive names and docstrings
- [ ] Error handling follows the established pattern
- [ ] File paths use `os.path.join()`
- [ ] F-strings are used for string formatting
- [ ] Imports follow standard ordering
- [ ] Exception handling is specific and includes fallbacks

### Testing Requirements
- Write tests for new functions using pytest
- Test error handling paths
- Mock external HTTP requests in tests
- Verify file I/O operations

### Git Workflow
- Feature branches should be descriptive
- Commit messages should follow conventional format
- Ensure content generation runs successfully before commits

## Deployment

### Production Deployment
1. Build Docker image: `docker build -t gemini-capsule .`
2. Run with persistent certificates: `docker run -p 1965:1965 -v gemini_certs:/app/certs gemini-capsule`
3. Configure hostname with `GEMINI_HOSTNAME` environment variable

### GitHub Actions
Automated builds trigger on:
- Push to main branch
- Pull requests
- The workflow is defined in `.github/workflows/docker.yml`

## Common Patterns

### URL Processing
```python
# Handle relative vs absolute URLs
if url.startswith("/"):
    full_url = "https://www.coredump.ch" + url
else:
    full_url = url
```

### Image Download Pattern
```python
def download_image(url, target_dir="content/images"):
    os.makedirs(target_dir, exist_ok=True)
    # ... download logic ...
    if not os.path.exists(local_path):
        # Download and save
    return local_path
```

### Content Conversion Pattern
```python
def convert_to_gemini(url, target_filename, pages_map):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # ... conversion logic ...
    return "\n".join(gmi_lines)
```

## Security Considerations

- Validate all external URLs before processing
- Sanitize user input and HTML content
- Use secure practices for file operations
- Don't expose sensitive information in error messages
- Generate self-signed certificates for Gemini protocol

## Performance Notes

- Cache downloaded images to avoid redundant requests
- Use relative paths to reduce bandwidth usage
- Minimize HTTP requests by batching operations where possible
- Consider rate limiting when scraping external websites