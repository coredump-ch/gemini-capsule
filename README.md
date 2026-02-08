# Gemini Capsule for Coredump.ch

A simple Gemini capsule that mirrors the content of [coredump.ch](https://www.coredump.ch/).

## Project Structure

- `generate.py`: Python script to fetch the website content and convert it to Gemtext (`.gmi`).
- `content/`: Directory containing the static Gemtext files.
- `Dockerfile`: Multi-stage build that compiles the `agate` Rust server and bundles the content.
- `.github/workflows/docker.yml`: GitHub Action to build the server image.

## Getting Started

### 1. Generate Content
To update the mirrored content:
```bash
uv run generate.py
```

### 2. Run with Docker
Build and run the Gemini server:
```bash
docker build -t gemini-capsule .
docker run -p 1965:1965 -v gemini_certs:/app/certs gemini-capsule
```

### 3. Run with Docker Compose (Recommended)
You can also use Docker Compose to run the server and persist certificates automatically:

```bash
docker-compose up -d
```

The server will be available at `gemini://localhost/`. Note that it uses self-signed certificates generated on the fly.
