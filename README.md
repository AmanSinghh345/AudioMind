# AI Audiobook

AI Audiobook is a source-grounded document workspace that turns PDFs, DOCX files, notes, CSVs, Markdown, public web pages, and scanned material into cited answers and generated narration.

## Project Structure

```text
AI-Audiobook/
  apps/
    api/                  FastAPI, Streamlit, Python package, tests
      audiomind/
      api.py
      streamlit_app.py
      requirements.txt
      requirements-tts.txt
      pyproject.toml
      tests/
      Dockerfile
    web/                  Next.js frontend
      app/
      public/
      package.json
      next.config.mjs
      Dockerfile
  data/
    uploads/              Uploaded source files
    vector_store/         Chroma vector data
    generated_audio/      Generated WAV files
  scripts/                Shared local worker scripts
  evaluation/             Offline evaluation datasets and runner
  docker-compose.yml
  .env.example
```

## Environment

Create a root `.env` from the safe example:

```powershell
copy .env.example .env
```

Important variables:

```text
GEMINI_API_KEY=your_gemini_api_key_here
AUDIOMIND_DATA_DIR=data
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000
AUDIOMIND_API_KEY=
```

`.env` is ignored by git. Keep real API keys out of `.env.example`.

## Run Backend

Use Python 3.10 or 3.11.

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

Open `http://localhost:8000/docs` for API docs.

Optional Kokoro TTS dependencies:

```powershell
pip install -r requirements-tts.txt
```

Set `KOKORO_ENV_NAME` and `TESSERACT_CMD` in `.env` as needed.

## Run Frontend

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend reads the API URL from `NEXT_PUBLIC_API_BASE_URL`; the in-app API URL control is hidden under Developer Settings.

## Data Folders

Runtime data belongs under root `data/`:

- `data/uploads/` stores uploaded documents.
- `data/vector_store/` stores Chroma vectors.
- `data/generated_audio/` stores generated audio.
- `data/audiomind.db` stores metadata, collections, documents, jobs, history, and audiobook records.

The `data/` folder is gitignored. Do not commit uploaded PDFs, vector stores, SQLite databases, or generated audio.

## Workspaces and Retrieval

Documents belong to collections, which act as workspaces. Uploads are indexed into the active workspace, and Q&A uses the selected workspace by default. This prevents unrelated PDFs from polluting retrieval context across workspaces and keeps future document-specific selection straightforward.

## Tests

```powershell
cd apps/api
pytest -q
```

Optional Kokoro integration:

```powershell
$env:RUN_KOKORO_INTEGRATION="1"
pytest -q tests/integration/test_kokoro.py
```

## Build Frontend

```powershell
cd apps/web
npm run build
```

## Docker

From the repo root:

```powershell
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Web: `http://localhost:3000`

Docker mounts root `./data` into the API container at `/app/data`.

## API Surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Runtime and vector-store health |
| `GET/POST` | `/api/collections` | List or create workspaces |
| `GET` | `/api/collections/{id}/documents` | List indexed documents in a workspace |
| `POST` | `/api/documents` | Queue multipart ingestion |
| `POST` | `/api/urls` | Queue guarded public web-page ingestion |
| `DELETE` | `/api/documents/{id}` | Delete metadata, vectors, and stored file |
| `POST` | `/api/ask` | Grounded RAG answer with source objects |
| `GET` | `/api/collections/{id}/history` | Query history |
| `POST` | `/api/audiobooks` | Queue chapter-script generation |
| `POST` | `/api/listen` | Queue answer audio |
| `GET` | `/api/jobs/{id}` | Poll persistent job state |

## Security Notes

- `.env` is ignored.
- Runtime data is ignored.
- Documents are treated as untrusted context.
- Retrieval is collection-scoped.
- Optional `AUDIOMIND_API_KEY` protects API routes with `X-API-Key`.
- Add authentication and tenant authorization before public multi-user deployment.
