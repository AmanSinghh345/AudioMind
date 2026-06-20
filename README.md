# AudioMind — AI Audiobook & RAG Study Assistant

AudioMind turns PDFs, DOCX files, CSVs, text, Markdown, public web pages, and scanned notes into a persistent study library. Students can ask source-grounded questions, inspect retrieval and reranking evidence, create editable chapter narration, and generate downloadable Kokoro audio.

## Why this is more than “chat with PDF”

- Page-aware ingestion with OCR fallback for scanned PDF pages
- Content hashing, duplicate detection, and automatic re-indexing when a file changes
- Semantic embeddings with a deterministic offline fallback
- Collection-filtered Chroma retrieval and lexical/vector reranking
- Gemini answers with inline citations and explicit insufficient-evidence refusal
- Visible source chunks, pages, vector scores, and reranking scores
- Multiple study collections and persistent Q&A history
- Chapter detection, six study modes, editable scripts, and per-chapter audio
- “Listen to answer” tutoring
- SQLite metadata, isolated TTS jobs, FastAPI, OpenAPI, Docker, CI, and evaluation tooling

## Architecture

```text
Streamlit UI / REST clients
              |
          FastAPI API
              |
   +----------+-----------+
   |                      |
Ingestion              Study tools
   |                      |
extract -> chunk      retrieve -> rerank -> Gemini + citations
   |                  chapters -> scripts -> Kokoro WAV
   +----------+-----------+
              |
     SQLite + Chroma + local object storage
```

The application logic lives in `audiomind/` and is shared by Streamlit and FastAPI. Replacing the local job pool with Redis/RQ and Chroma with Qdrant does not require rewriting ingestion or RAG logic.

## Data model

SQLite persists:

- `collections`
- `documents`
- `chunks`
- `qa_history`
- `audiobooks`
- `audio_chapters`
- `jobs`

Every vector stores `document_id`, `collection_id`, filename, page, chapter, and chunk index. These fields produce verifiable citations instead of guessed source labels.

## Setup

Use Python 3.10 or 3.11 for the core application:

```powershell
conda create -n audiobook-v2 python=3.11 -y
conda activate audiobook-v2
pip install -r requirements.txt
copy .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. Without it, ingestion, retrieval, citations, and rule-based narration still work; answers use an extractive fallback.

Kokoro may be installed in the same environment or a dedicated environment:

```powershell
conda create -n ai python=3.11 -y
conda activate ai
pip install -r requirements-tts.txt
```

Set `KOKORO_ENV_NAME=ai`. AudioMind invokes that environment with `conda run`, and every request gets an isolated temporary segment directory.

OCR additionally requires Tesseract. Set `TESSERACT_CMD` if it is not available on `PATH`.

## Run

Streamlit product UI:

```powershell
conda activate audiobook-v2
streamlit run streamlit_app.py
```

AudioMind disables Streamlit's module file watcher because Transformers exposes
optional vision modules that otherwise produce harmless `torchvision` watcher
errors in text-only installations. Restart Streamlit after changing Python code.

FastAPI and interactive API documentation:

```powershell
uvicorn api:app --reload --port 8000
```

Open `http://localhost:8000/docs` for Swagger UI.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Runtime and vector-store health |
| `GET/POST` | `/api/collections` | List or create study collections |
| `GET` | `/api/collections/{id}/documents` | List indexed documents |
| `POST` | `/api/documents` | Queue multipart ingestion |
| `POST` | `/api/urls` | Queue guarded public web-page ingestion |
| `DELETE` | `/api/documents/{id}` | Delete metadata, vectors, and stored file |
| `POST` | `/api/ask` | Grounded RAG answer with source objects |
| `GET` | `/api/collections/{id}/history` | Transparent query history |
| `POST` | `/api/audiobooks` | Queue chapter-script generation |
| `PATCH` | `/api/chapters/{id}` | Save an edited script |
| `POST` | `/api/chapters/{id}/audio` | Queue isolated chapter audio |
| `POST` | `/api/listen` | Queue answer audio |
| `GET` | `/api/jobs/{id}` | Poll persistent job state |

## Retrieval pipeline

1. Extract ordered, page-aware text.
2. Mark likely chapter headings.
3. Create overlapping chunks without crossing page metadata.
4. Embed with `sentence-transformers/all-MiniLM-L6-v2`.
5. Upsert vectors with complete citation metadata.
6. Retrieve candidates inside the selected collection.
7. Rerank using vector similarity and meaningful query-term overlap.
8. Refuse low-evidence questions.
9. Ask Gemini to use only numbered sources and cite every factual claim.
10. Return the final answer separately from raw evidence and scores.

If the Sentence Transformers model is unavailable, AudioMind uses a normalized feature-hashing embedding. This keeps development and tests operational, but semantic embeddings should be used for production evaluation.

## Evaluation

Copy `evaluation/dataset.example.jsonl`, add 30–50 representative questions, and run:

```powershell
python evaluation/evaluate.py evaluation/dataset.jsonl
```

The report records citation hit rate, grounded-answer rate, refusals, source count, and latency. Do not put invented metrics on a résumé—run this dataset and report the measured result.

## Tests

```powershell
pytest -q
```

The suite covers chunk metadata, SQLite/job lifecycle, document deduplication and updates, RAG retrieval/citations, API health, audio isolation helpers, and Streamlit workspace rendering. Live Kokoro generation is intentionally opt-in:

```powershell
$env:RUN_KOKORO_INTEGRATION="1"
pytest -q tests/integration/test_kokoro.py
```

## Containers

```powershell
docker compose up --build
```

- Streamlit: `http://localhost:8501`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

Both services share the `audiomind-data` volume. For multi-instance production deployment, use PostgreSQL, object storage, Qdrant, and Redis/RQ rather than a shared SQLite file and in-process workers.

## Guardrails and security decisions

- Allowlisted extensions and configurable upload-size limit
- Server-generated storage names prevent path traversal
- Documents are treated as untrusted context; document instructions cannot override the RAG system prompt
- Collection filters prevent cross-collection retrieval
- Low-evidence questions are refused
- Secrets and generated data are gitignored
- CORS is configurable through `CORS_ORIGINS`
- Optional constant-time `X-API-Key` protection through `AUDIOMIND_API_KEY`

Authentication and tenant authorization must be added before exposing this as a public multi-user SaaS. The current build is designed for a personal portfolio deployment or trusted classroom demo.

## Resume bullet template

> Built AudioMind, a source-grounded study assistant that ingests documents and scanned notes, performs page-aware semantic retrieval with reranking and citation-backed Gemini responses, and generates editable chapter-wise audiobooks using Kokoro TTS; achieved **X% citation hit rate** across **Y evaluated questions**.
