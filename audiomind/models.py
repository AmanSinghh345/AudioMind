from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    chapter: str = "Document"


@dataclass
class DocumentChunk:
    id: str
    document_id: str
    collection_id: str
    filename: str
    page_number: int
    chunk_index: int
    chapter: str
    text: str

    def metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("text")
        return data


@dataclass
class RetrievedSource:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    chapter: str
    text: str
    vector_score: float
    rerank_score: float = 0.0

    @property
    def label(self) -> str:
        return f"{self.filename}, page {self.page_number}, chunk {self.chunk_index + 1}"


@dataclass
class RAGAnswer:
    answer: str
    sources: list[RetrievedSource] = field(default_factory=list)
    grounded: bool = False
    method: str = "extractive"


@dataclass
class Chapter:
    number: int
    title: str
    text: str
    start_page: int
    end_page: int
