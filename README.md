# YT Reviser ▷ AI-Powered Lecture Revision & Incremental RAG

YT Reviser is an AI-powered YouTube lecture revision application built for students and developers. It converts lecture videos and playlists into an interactive, grounded knowledge base with clickable timestamped citations.

---

## 1. System Architecture & Data Flow

```
YouTube Playlist / Video URL
             │
             ▼
  yt-dlp Metadata Discovery
             │
             ▼
      Audio Download (yt-dlp + FFmpeg MP3 128k)
             │
             ▼
  faster-whisper Transcription (CPU / int8 on Apple Silicon M2)
             │
             ▼
  Timestamped Transcript JSON (`data/transcripts/VIDEO_ID.json`)
             │
             ▼
  Time-Aware Chunking (~75s target duration, sentence-aligned)
             │
             ▼
  Chunk JSON (`data/chunks/VIDEO_ID.json`)
             │
             ▼
  Sentence-Transformers Embeddings (`all-MiniLM-L6-v2`, 384-dim)
             │
             ▼
  Qdrant Vector Database (`./qdrant_db`, collection `yt_reviser`)
             │
             ▼
  Question Search → Cosine Similarity Retrieval
             │
             ▼
  Groq LLM Synthesis (Grounded Prompting with Citation Timestamps)
             │
             ▼
  Interactive Frontend with Clickable YouTube Jump Links & Follow-Ups
```

---

## 2. Directory Structure

```
ytreviser/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py             # Environment and paths configuration
│   │   ├── main.py               # FastAPI application entrypoint
│   │   ├── api/                  # API routers (health, ingest, playlists, chat)
│   │   ├── models/               # Pydantic schemas and manifest models
│   │   ├── services/
│   │   │   ├── manifest_service.py       # Atomic manifest & video state tracker
│   │   │   ├── youtube_service.py        # yt-dlp metadata & audio extractor
│   │   │   ├── transcription_service.py  # faster-whisper CPU/int8 engine
│   │   │   ├── chunking_service.py       # ~75s time-aware chunking engine
│   │   │   ├── embedding_service.py      # MiniLM-L6-v2 vector generator
│   │   │   ├── qdrant_service.py         # Local persistent Qdrant manager
│   │   │   ├── ingestion_engine.py       # Resumable sync & background jobs
│   │   │   └── rag_service.py            # Grounded Groq RAG & citations
│   │   └── utils/
│   │       └── logger.py
│   ├── tests/                    # Pytest unit & integration test suite
│   ├── pyproject.toml
│   └── run.py                    # Local server launcher
├── frontend/
│   ├── index.html                # Responsive UI (Ingest, Sync, Chat, Bookmarks)
│   ├── style.css                 # Modern CSS design system (Dark/Light mode)
│   └── script.js                 # Frontend API controller & status poller
├── data/
│   ├── transcripts/              # Raw timestamped transcript JSONs
│   ├── chunks/                   # Time-aware chunk JSONs
│   ├── audio/                    # Temporary/cached downloaded audio files
│   └── manifest.json             # Video & playlist state tracking manifest
├── qdrant_db/                    # Local persistent Qdrant vector database
├── .env.example
├── .gitignore
└── README.md
```

---

## 3. Prerequisites & Installation (macOS Apple Silicon M2)

### 3.1 Prerequisites
1. **Python 3.11** (managed with `uv` or system Python)
2. **FFmpeg** (required by yt-dlp for audio extraction):
   ```bash
   brew install ffmpeg
   ```

### 3.2 Setup Virtual Environment
```bash
# Create Python 3.11 virtual environment with uv
uv venv --python 3.11
source .venv/bin/activate

# Install all backend dependencies
uv pip install -e .
```

### 3.3 Environment Variables
Copy `.env.example` to `.env` and provide your Groq API key:
```bash
cp .env.example .env
```

Edit `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
QDRANT_PATH=./qdrant_db
QDRANT_COLLECTION=yt_reviser
FRONTEND_ORIGIN=http://localhost:3000
```

---

## 4. Running the Application

### 4.1 Start the FastAPI Backend
```bash
# From the project root
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend API and Swagger docs will be available at:
- API Base: `http://127.0.0.1:8000`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/health`

### 4.2 Start the Frontend
In a separate terminal:
```bash
# Serve the frontend directory on port 3000
python3 -m http.server 3000 --directory frontend
```
Open your browser at `http://localhost:3000`.

---

## 5. Usage Guide

### 5.1 Ingesting a Playlist or Video
1. In the frontend, navigate to the **Ingest & Sync** tab.
2. Paste the YouTube playlist or video URL (e.g. `https://www.youtube.com/playlist?list=PLW4OpyGE0RdY`).
3. Click **⬇ Ingest Content**.
4. The live progress panel displays discovered videos, current processing stage, and counters (Completed, Skipped, Failed).

### 5.2 Synchronizing an Existing Playlist
1. Click **⟳ Sync Playlist** or navigate to **Playlists** and click **Sync** on any registered playlist.
2. The ingestion manifest checks YouTube for new or incomplete videos, skipping already-indexed ones.
3. If everything is up to date, it displays: *"Your playlist is already up to date."*

### 5.3 Asking Revision Questions
1. Navigate to the **Ask & Revise** tab.
2. Enter your concept question (e.g. *"How does binary search work in story problems?"*).
3. The tutor provides a concept-first explanation, clickable lecture timestamp jump links, and 3 suggested follow-up questions.
4. Click **♡ Save** to bookmark key explanations in your browser.

---

## 6. Testing

Run the automated test suite with pytest:
```bash
source .venv/bin/activate
pytest backend/tests -v
```

---

## 7. Storage & Manifest Checkpoints

- **Transcripts:** `data/transcripts/{video_id}.json` (atomic writes).
- **Chunks:** `data/chunks/{video_id}.json` (approx 75s duration each).
- **Manifest:** `data/manifest.json` (records stages: Discovered, Audio Downloaded, Transcribed, Chunked, Embedded, Uploaded to Qdrant, Completed).
- **Vector DB:** `./qdrant_db` (persistent local storage).
