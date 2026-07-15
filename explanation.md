# Inquix System Architecture & Optimization Guide

This document explains the technical implementation, core logic, third-party integrations, and performance optimizations built into **Inquix**.

---

## 1. Technologies & Third-Party Libraries Stack

| Feature | Technology/Library | Execution & Purpose |
| :--- | :--- | :--- |
| **Backend Core** | Django & ASGI (Uvicorn) | Manages database transactions, ASGI event streaming, and API routers. |
| **Frontend Core** | Next.js & TailwindCSS | Renders the NotebookLM-style responsive layout. |
| **Database** | PostgreSQL & `pgvector` | Stores structural entities (KBs, documents, messages) and vectors (embeddings). |
| **Caching Layer** | Redis | Caches embeddings, LLM generation streams, and crawled web search contents. |
| **Embedding Engine** | Ollama (`nomic-embed-text`) | Generates 768-dimension dense vector representations of text blocks. |
| **LLM Engine** | Ollama (`qwen2.5:3b` / Groq) | Streams response tokens based on contextual prompts. |
| **PDF Extraction** | PyMuPDF (`fitz`) | Parses pages and extracts raw text layouts from PDFs. |
| **DOCX Extraction** | Python `zipfile` & `ElementTree` | Decompresses docx archives and parses paragraph structures from XML (pure Python). |
| **DOC Extraction** | `antiword` & Custom Fallback | Converts binary `.doc` files to plain text; falls back to an ASCII regex string scanner if missing. |
| **Image Vision & OCR** | `pytesseract` & Ollama Vision | Extracts texts using Tesseract OCR, and description captions via vision models. |
| **Offline Transcription** | `faster-whisper` | Transcribes audio uploads (MP3, WAV, WebM) on the backend using INT8/Float32. |
| **Real-time Voice STT** | Web Speech API | Transcribes user speech dynamically in the browser (SpeechRecognition). |
| **Text-to-Speech (TTS)** | Kokoro & Edge-TTS | Generates vocal feedback. Sniffs headers to output `audio/wav` vs. `audio/mpeg` formats. |
| **Web Crawling & Search**| DuckDuckGo & Crawl4AI | Queries the web and extracts readable markdown content from matching URLs. |

---

## 2. Decision Logic: Knowledge Base vs. Web Scraping

Every user chat query goes through a RAG (Retrieval-Augmented Generation) vs. Web Search fallback sequence:

```
[User Chat Query]
       │
       ▼
[Generate Query Vector Embedding]
       │
       ▼
[Query PostgreSQL using pgvector Cosine Distance]
       │
       ▼
{Is maximum similarity >= Similarity Threshold 0.45?}
       ├── Yes ──> [Select Local Context Chunks]
       └── No  ──> [Query DuckDuckGo for Search Results]
                       │
                       ▼
                   [Extract Page URLs and Crawl content via Crawl4AI]
                       │
                       ▼
                   [Assemble Web Context Chunks]
                       │
                       ▼
                   [Compile LLM Prompt Context]
                       │
                       ▼
                   [Stream LLM Tokens]
```

### Operational Rules:
1. **Local Retrieval**: When a query has a vector match above the threshold (`similarity >= 0.45`), the system assumes the user is asking about the uploaded documents. The local document chunks are retrieved, and web scraping is bypassed.
2. **Web Search Fallback**: If no matching local chunks pass the threshold, the system assumes the local documents do not contain the answer. It queries DuckDuckGo, extracts search results, scrapes the top 2 web pages using Crawl4AI, and uses the crawled content as context.

---

## 3. Input & Output Architectures

### Text Input
- Texts are chunked into paragraphs (max 500 characters) with overlap.
- Each chunk is embedded using `nomic-embed-text` and stored in the database.

### Image Input
- Images uploaded through the attach button are converted to Base64 on the frontend and posted to the backend.
- If indexed in the KB, the backend runs:
  1. Tesseract OCR to extract written text: `pytesseract.image_to_string()`.
  2. Ollama Vision (`llava-phi3:3.8b`) to generate a textual description of what is in the image.
- Both texts are saved under the document's chunks to allow vector queries.

### Audio Input
- **Real-time Speech Input**: Click-to-record voice chat uses browser-native `webkitSpeechRecognition`. It transcribes user speech in real time, updating the text area as they talk.
- **Audio File Attachment**: Audio files uploaded to the KB are converted to standard `wav` format via `ffmpeg` on the backend, then transcribed using `faster-whisper`.

---

## 4. Document Deletion Side Effects

When a document is deleted from a Knowledge Base:
1. A database cascading deletion is triggered.
2. All chunks associated with the document are deleted from the vector table in PostgreSQL.
3. Subsequent queries will no longer return matches for that document. The system will automatically fall back to Web Search if no other local documents match the query.

---

## 5. Performance Engineering & Optimizations

We implemented three layers of optimizations to ensure fast start-to-stream response times:

### 1. Lazy Stream Generators (16ms Handshake)
Previously, Django performed database lookups, vector searches, and web crawls *before* returning the HTTP response. The browser stood frozen waiting for the headers, occasionally timing out.
- **Solution**: Defer all heavy queries (vector search, database lookups, web scraping) inside the async `stream_response` generator. The backend returns the `StreamingHttpResponse` instantly (within **16ms**), establishing the connection. Heavy tasks are then run asynchronously while the connection is already active, triggering the frontend loading spinner immediately.

### 2. Multi-Layer Redis Caching
- **Embeddings Cache**: Caches vector embedding requests to avoid calling Ollama/Jina endpoints repeatedly for identical text segments.
- **Web Search Cache**: Caches DuckDuckGo scrapes by hashing a normalized version of the search query (ignoring case, spaces, and trailing punctuation) to bypass scraping delays on repeated queries.
- **LLM Cache**: Caches full streams of generated responses for duplicate prompt payloads. We implement **Smooth Playback Caching** (streaming cached content in chunks of 12 characters with a 5ms delay) to keep the UI smooth instead of snapping.

### 3. Context Window Compression
- Reduced the web crawling scrape capture limit from `5000` to `2000` characters.
- Reduced default `top_k` chunk retrieval from `5` to `3` in `config.py`.
- **Result**: Cuts down prompt size by up to 60%, speeding up Ollama's prompt evaluation pre-fill calculations significantly on local hardware.
