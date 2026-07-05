from __future__ import annotations

import os
import hmac
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from audiomind.tts import AudioGenerator
from audiomind.jobs import JobManager
from audiomind.services import get_services


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("AUDIOMIND_API_KEY")
    if expected and (not x_api_key or not hmac.compare_digest(x_api_key, expected)):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


services = get_services()
jobs = JobManager(services.repository)
audio = AudioGenerator(
    kokoro_env_name=services.settings.kokoro_env_name,
    output_dir=services.settings.audio_path,
)

app = FastAPI(
    title="AudioMind API",
    description="Source-grounded study tutor and chapter-wise audiobook API.",
    version="1.0.0",
    dependencies=[Depends(verify_api_key)],
)
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CollectionRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)


class QuestionRequest(BaseModel):
    collection_id: str
    question: str = Field(min_length=3, max_length=2000)


class AudiobookRequest(BaseModel):
    document_id: str
    mode: str = "simple explanation"
    voice: str = "af_heart"


class ScriptUpdate(BaseModel):
    script: str = Field(min_length=1, max_length=100000)


class ListenRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class URLRequest(BaseModel):
    collection_id: str
    url: str = Field(min_length=10, max_length=2000)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "vector_chunks": services.vector_store.collection.count(),
        "embedding_method": services.embeddings.method,
    }


@app.get("/api/collections")
def list_collections() -> list[dict]:
    services.repository.ensure_default_collection()
    return services.repository.list_collections()


@app.post("/api/collections", status_code=201)
def create_collection(request: CollectionRequest) -> dict:
    try:
        collection_id = services.repository.create_collection(request.name, request.description)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="A collection with that name already exists") from exc
    return {"id": collection_id, **request.model_dump()}


@app.get("/api/collections/{collection_id}/documents")
def list_documents(collection_id: str) -> list[dict]:
    return services.repository.list_documents(collection_id)


@app.post("/api/documents", status_code=202)
async def upload_document(
    collection_id: str = Form(...), use_ocr: bool = Form(True), file: UploadFile = File(...),
) -> dict:
    content = await file.read(services.settings.max_upload_mb * 1024 * 1024 + 1)
    filename = file.filename or "upload"
    job_id = jobs.submit(
        "document_ingestion",
        {"collection_id": collection_id, "filename": filename},
        lambda: services.ingestion.ingest_bytes(collection_id, filename, content, use_ocr),
    )
    return {"job_id": job_id, "status": "queued"}


@app.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str) -> None:
    services.ingestion.delete(document_id)


@app.post("/api/urls", status_code=202)
def ingest_url(request: URLRequest) -> dict:
    job_id = jobs.submit(
        "url_ingestion", request.model_dump(),
        lambda: services.web_ingestion.ingest_url(request.collection_id, request.url),
    )
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/ask")
def ask(request: QuestionRequest) -> dict:
    try:
        result = services.rag.ask(request.collection_id, request.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "answer": result.answer,
        "grounded": result.grounded,
        "method": result.method,
        "sources": [asdict(source) | {"label": source.label} for source in result.sources],
    }


@app.get("/api/collections/{collection_id}/history")
def qa_history(collection_id: str) -> list[dict]:
    return services.repository.list_qa(collection_id)


@app.post("/api/audiobooks", status_code=202)
def create_audiobook(request: AudiobookRequest) -> dict:
    job_id = jobs.submit(
        "narration_scripts",
        request.model_dump(),
        lambda: services.narration.create_scripts(request.document_id, request.mode, request.voice),
    )
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/audiobooks/{audiobook_id}")
def get_audiobook(audiobook_id: str) -> dict:
    result = services.repository.get_audiobook(audiobook_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return result


@app.patch("/api/chapters/{chapter_id}")
def update_script(chapter_id: str, request: ScriptUpdate) -> dict:
    services.repository.update_chapter_script(chapter_id, request.script)
    return {"id": chapter_id, "status": "script_ready"}


@app.post("/api/chapters/{chapter_id}/audio", status_code=202)
def generate_chapter_audio(chapter_id: str) -> dict:
    def task() -> dict:
        chapter = services.repository.get_chapter(chapter_id)
        if not chapter:
            raise ValueError("Chapter not found")
        output = services.settings.audio_path / f"chapter_{chapter_id}.wav"
        result = audio.generate_audio(chapter["script"], output)
        if not result["success"]:
            raise RuntimeError(result["error"])
        services.repository.update_chapter_audio(chapter_id, result["file_path"], result["duration"])
        return result

    job_id = jobs.submit("chapter_audio", {"chapter_id": chapter_id}, task)
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/listen", status_code=202)
def listen_to_answer(request: ListenRequest) -> dict:
    output = services.settings.audio_path / f"answer_{os.urandom(8).hex()}.wav"
    job_id = jobs.submit(
        "answer_audio", {"characters": len(request.text)},
        lambda: _audio_result(request.text, output),
    )
    return {"job_id": job_id, "status": "queued"}


def _audio_result(text: str, output: Path) -> dict:
    result = audio.generate_audio(text, output)
    if not result["success"]:
        raise RuntimeError(result["error"])
    return result


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = services.repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


if services.settings.audio_path.exists():
    app.mount("/audio", StaticFiles(directory=services.settings.audio_path), name="audio")
