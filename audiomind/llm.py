"""Gemini and offline narration text enhancement."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv


load_dotenv()


class TextEnhancer:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        if self.api_key:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)

    def enhance_with_gemini(self, input_text: str, style: str = "engaging") -> dict:
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": (
                        "GEMINI_API_KEY is missing. Add it to .env or use "
                        "rule-based enhancement."
                    ),
                }

            prompt = f"""
You are an expert audiobook narrator and storyteller.
Transform the extracted text into listener-friendly narration without losing important details.

Guidelines:
- Preserve all key information unless the requested mode explicitly asks for a summary.
- Begin with a natural welcome and explain what the listener will learn.
- Make the language engaging, clear, and easy to follow aloud.
- Break long sentences into shorter spoken sentences.
- Use natural pauses and transitions.
- Remove Markdown syntax while preserving its meaning.
- Turn bullet points into spoken sequences.
- Expand abbreviations where helpful.
- Never invent facts that are absent from the source.

Narration style: {style}

Extracted content:
{input_text}
"""
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            if not getattr(response, "text", "").strip():
                return {"success": False, "error": "Gemini returned an empty response."}
            return {"success": True, "enhanced_text": response.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def enhance_with_rules(self, input_text: str, style: str = "engaging") -> dict:
        """Create listenable narration without an external model."""
        try:
            enhanced = re.sub(r"[#*\-_~`>|]", "", input_text)
            replacements = {
                "e.g.": "for example",
                "i.e.": "that is",
                "etc.": "and so on",
                "vs.": "versus",
                " approx.": " approximately",
                " no.": " number",
                " vol.": " volume",
                " fig.": " figure",
                " et al.": " and others",
            }
            for abbreviation, expanded in replacements.items():
                enhanced = enhanced.replace(abbreviation, expanded)

            introductions = {
                "engaging": (
                    "Hello listeners, welcome! In this session, we'll explore the "
                    "following content. "
                ),
                "dramatic": (
                    "Prepare for an immersive experience as we explore this material. "
                ),
                "conversational": (
                    "Hey there! Let's explore this interesting content together. "
                ),
                "professional": (
                    "Welcome. We'll now review the following information in detail. "
                ),
            }
            enhanced = introductions.get(style, introductions["professional"]) + enhanced
            sentences = re.split(r"(?<=[.!?])\s+", enhanced)
            processed = []
            for sentence in sentences:
                if len(sentence) > 150:
                    parts = re.split(r",\s+", sentence)
                    if len(parts) > 1:
                        sentence = "... ".join(parts) + "..."
                processed.append(sentence)
            return {"success": True, "enhanced_text": " ".join(processed)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
