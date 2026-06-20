from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("AUDIOMIND_DATA_DIR", "data"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "900"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    retrieval_candidates: int = int(os.getenv("RETRIEVAL_CANDIDATES", "12"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    kokoro_env_name: str = os.getenv("KOKORO_ENV_NAME", "ai")
    tesseract_cmd: str | None = os.getenv("TESSERACT_CMD")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "audiomind.db"

    @property
    def vector_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def upload_path(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def audio_path(self) -> Path:
        return self.data_dir / "audio"

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.vector_path, self.upload_path, self.audio_path):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
