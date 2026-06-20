"""Subprocess worker executed inside the configured Kokoro environment."""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path


def split_text_into_chunks(text: str, max_length: int = 800) -> list[str]:
    """Split narration at sentence boundaries while respecting the model limit."""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in text.split(". "):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{sentence}. "
        if current and len(current) + len(candidate) > max_length:
            chunks.append(current.strip())
            current = candidate
        else:
            current += candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[index : index + max_length] for index in range(0, len(text), max_length)]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: kokoro_worker.py TEXT_FILE [OUTPUT_DIRECTORY]")

    text_file = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        text = text_file.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("Narration text is empty")

        started = time.time()
        from kokoro import KPipeline
        import soundfile as sf

        print(f"Loaded Kokoro in {time.time() - started:.2f} seconds")
        pipeline = KPipeline(lang_code="a")
        chunks = split_text_into_chunks(text)
        print(f"Generating {len(chunks)} text chunks")

        total_segments = 0
        for chunk_index, chunk in enumerate(chunks):
            generator = pipeline(chunk, voice="af_heart")
            for segment_index, (_, _, audio) in enumerate(generator):
                output = output_dir / f"segment_{chunk_index}_{segment_index}.wav"
                sf.write(output, audio, 24000)
                total_segments += 1

        if not total_segments:
            raise RuntimeError("Kokoro did not produce any audio segments")
        print(f"Generated {total_segments} audio segments in {output_dir}")
    except Exception as exc:
        print(f"Kokoro worker failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
