# Inquix

Multi-modal RAG platform — upload text, PDF, images, and audio documents, then ask questions with streaming AI answers and source citations.

## Architecture

```
Next.js Frontend (port 3000)  →  FastAPI Backend (port 8000)  →  Ollama (LLM + Embeddings)
                                                              →  PostgreSQL + pgvector
```

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/)
- 12 GB disk space (for Docker images + Ollama models)

## Quick Start

```bash
# Clone and enter the repo
cd Inquix

# Pull Ollama models (first time only, ~3 GB)
docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull qwen2.5:3b
docker compose down

# Start everything
docker compose up --build
```

Then open **[http://localhost:3000](http://localhost:3000)**.

The first startup downloads Docker images and builds containers (~5 min). Model pulls are cached across restarts.

## Supported File Types

| Type | Extensions | Extraction Method |
|---|---|---|
| Text | `.txt`, `.md`, `.py`, `.json`, `.csv`, `.html`, `.css`, `.js` | Direct read |
| PDF | `.pdf` | PyMuPDF (text layer) |
| Image | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp` | Tesseract OCR |
| Audio | `.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm` | faster-whisper (base) |

## Usage

1. **Create a Knowledge Base** from the homepage
2. **Upload documents** via drag-and-drop in the sidebar
3. Wait for processing (status: processing → ready)
4. **Ask questions** in the chat — answers stream with source citations

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `POST /api/kb` | Create knowledge base |
| `GET /api/kb` | List knowledge bases |
| `DELETE /api/kb/{id}` | Delete knowledge base |
| `POST /api/kb/{id}/documents` | Upload document (multipart) |
| `GET /api/kb/{id}/documents` | List documents |
| `DELETE /api/kb/{id}/documents/{doc_id}` | Delete document |
| `POST /api/kb/{id}/chat` | Ask question (SSE stream) |
| `GET /api/kb/{id}/conversations` | List conversations |
| `GET /api/conversations/{id}/messages` | Get messages |

## Model Configuration

Change models in `docker-compose.yml` or `.env`:

```env
EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=qwen2.5:3b
```

CPU-friendly alternatives: `llama3.2:3b`, `phi3:mini`, `tinyllama`.

## Stopping

```bash
docker compose down
```

To wipe all data including uploaded files and models:

```bash
docker compose down -v
```
