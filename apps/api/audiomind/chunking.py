from __future__ import annotations

import re
import uuid

from .models import DocumentChunk, ExtractedPage


HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


class PageAwareChunker:
    def __init__(self, chunk_size: int = 900, overlap: int = 150):
        if chunk_size < 200:
            raise ValueError("chunk_size must be at least 200 characters")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(
        self,
        pages: list[ExtractedPage],
        document_id: str,
        collection_id: str,
        filename: str,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        chunk_index = 0
        current_chapter = "Document"

        for page in pages:
            paragraphs = [item.strip() for item in re.split(r"\n\s*\n", page.text) if item.strip()]
            buffer = ""
            for paragraph in paragraphs:
                heading = HEADING_RE.match(paragraph)
                if heading:
                    current_chapter = heading.group(1).strip()
                if buffer and len(buffer) + len(paragraph) + 2 > self.chunk_size:
                    chunks.append(
                        self._make_chunk(
                            buffer, document_id, collection_id, filename,
                            page.page_number, chunk_index, current_chapter,
                        )
                    )
                    chunk_index += 1
                    buffer = self._overlap_tail(buffer)
                buffer = f"{buffer}\n\n{paragraph}".strip()

                while len(buffer) > self.chunk_size:
                    split_at = self._best_split(buffer, self.chunk_size)
                    piece = buffer[:split_at].strip()
                    chunks.append(
                        self._make_chunk(
                            piece, document_id, collection_id, filename,
                            page.page_number, chunk_index, current_chapter,
                        )
                    )
                    chunk_index += 1
                    tail_start = max(0, split_at - self.overlap)
                    buffer = buffer[tail_start:].strip()

            if buffer:
                chunks.append(
                    self._make_chunk(
                        buffer, document_id, collection_id, filename,
                        page.page_number, chunk_index, current_chapter,
                    )
                )
                chunk_index += 1

        return chunks

    @staticmethod
    def _best_split(text: str, limit: int) -> int:
        floor = int(limit * 0.65)
        for marker in ("\n", ". ", "; ", ", ", " "):
            position = text.rfind(marker, floor, limit + 1)
            if position >= floor:
                return position + len(marker)
        return limit

    def _overlap_tail(self, text: str) -> str:
        if not self.overlap:
            return ""
        start = max(0, len(text) - self.overlap)
        space = text.find(" ", start)
        return text[space + 1 :] if space >= 0 else text[start:]

    @staticmethod
    def _make_chunk(
        text: str,
        document_id: str,
        collection_id: str,
        filename: str,
        page_number: int,
        chunk_index: int,
        chapter: str,
    ) -> DocumentChunk:
        return DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            collection_id=collection_id,
            filename=filename,
            page_number=page_number,
            chunk_index=chunk_index,
            chapter=chapter or "Document",
            text=text,
        )
