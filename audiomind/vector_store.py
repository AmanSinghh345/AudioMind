from __future__ import annotations

from pathlib import Path

import chromadb

from .models import DocumentChunk, RetrievedSource


class ChromaVectorStore:
    def __init__(self, persist_directory: Path | str):
        self.client = chromadb.PersistentClient(path=str(persist_directory))
        self.collection = self.client.get_or_create_collection(
            "audiomind_chunks", metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[chunk.metadata() for chunk in chunks],
        )

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def search(
        self, collection_id: str, query_embedding: list[float], n_results: int = 12
    ) -> list[RetrievedSource]:
        available = self.collection.count()
        if not available:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, available),
            where={"collection_id": collection_id},
            include=["documents", "metadatas", "distances"],
        )
        sources: list[RetrievedSource] = []
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0],
            result["metadatas"][0], result["distances"][0],
        ):
            sources.append(
                RetrievedSource(
                    chunk_id=chunk_id,
                    document_id=str(metadata["document_id"]),
                    filename=str(metadata["filename"]),
                    page_number=int(metadata["page_number"]),
                    chunk_index=int(metadata["chunk_index"]),
                    chapter=str(metadata.get("chapter", "Document")),
                    text=text,
                    vector_score=max(0.0, 1.0 - float(distance)),
                )
            )
        return sources
