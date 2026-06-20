from __future__ import annotations

import re
from collections import OrderedDict

from .llm import TextEnhancer

from .models import Chapter
from .repository import Repository


MODE_GUIDANCE = {
    "simple explanation": "Explain technical ideas in simple language while preserving definitions and examples.",
    "exam revision": "Create concise spoken revision with definitions, key points, and likely exam facts.",
    "podcast": "Use a warm podcast-host style with transitions and occasional rhetorical questions.",
    "storytelling": "Use memorable analogies and narrative transitions without inventing facts.",
    "detailed lecture": "Teach the material as a structured lecture and preserve important detail.",
    "short summary": "Create a brief spoken summary containing only the most important supported ideas.",
}


class NarrationService:
    def __init__(self, repository: Repository):
        self.repository = repository
        self.enhancer = TextEnhancer()

    def chapters_for_document(self, document_id: str) -> list[Chapter]:
        rows = self.repository.get_document_chunks(document_id)
        if not rows:
            return []
        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        for row in rows:
            title = row["chapter"] or "Document"
            if title == "Document":
                title = f"Study Section {(row['chunk_index'] // 5) + 1}"
            grouped.setdefault(title, []).append(row)
        chapters = []
        for number, (title, items) in enumerate(grouped.items(), 1):
            chapters.append(
                Chapter(
                    number=number,
                    title=title,
                    text="\n\n".join(item["text"] for item in items),
                    start_page=min(item["page_number"] for item in items),
                    end_page=max(item["page_number"] for item in items),
                )
            )
        return chapters

    def create_scripts(
        self, document_id: str, mode: str = "simple explanation", voice: str = "af_heart",
    ) -> dict:
        document = self.repository.get_document(document_id)
        if not document:
            raise ValueError("Document not found")
        chapters = self.chapters_for_document(document_id)
        if not chapters:
            raise ValueError("Document has no indexed chapters")
        scripts = []
        for chapter in chapters:
            script = self._script(chapter, mode)
            scripts.append({"number": chapter.number, "title": chapter.title, "script": script})
        audiobook_id = self.repository.create_audiobook(
            document_id, document["filename"], mode, voice, scripts
        )
        return self.repository.get_audiobook(audiobook_id)

    def _script(self, chapter: Chapter, mode: str) -> str:
        normalized_mode = mode.lower()
        guidance = MODE_GUIDANCE.get(normalized_mode, MODE_GUIDANCE["simple explanation"])
        style = "professional" if normalized_mode in {"exam revision", "detailed lecture"} else "engaging"
        # Bound each generation request. Very large chapters remain complete through sequential sections.
        sections = self._split(chapter.text, 10000)
        generated = []
        for index, section in enumerate(sections, 1):
            input_text = (
                f"Chapter: {chapter.title}. Section {index} of {len(sections)}.\n"
                f"Narration goal: {guidance}\n\n{section}"
            )
            result = self.enhancer.enhance_with_gemini(input_text, style=style)
            if not result["success"]:
                result = self.enhancer.enhance_with_rules(input_text, style=style)
            generated.append(result["enhanced_text"])
        return "\n\n".join(generated)

    @staticmethod
    def _split(text: str, limit: int) -> list[str]:
        if len(text) <= limit:
            return [text]
        sections = []
        remaining = text
        while remaining:
            split_at = min(limit, len(remaining))
            if split_at < len(remaining):
                candidate = remaining.rfind("\n", int(limit * 0.7), limit)
                split_at = candidate if candidate > 0 else split_at
            sections.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        return [section for section in sections if section]
