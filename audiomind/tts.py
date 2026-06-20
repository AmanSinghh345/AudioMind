"""Isolated Kokoro audio generation and WAV assembly."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import wave
from pathlib import Path


class AudioGenerator:
    """Generate isolated Kokoro jobs and combine their WAV segments safely."""

    def __init__(self, kokoro_env_name: str = "ai", output_dir: str | Path = "generated_audio"):
        self.kokoro_env = kokoro_env_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_audio(self, text: str, output_path: str | Path | None = None) -> dict:
        if not text or not text.strip():
            return {"success": False, "file_path": None, "error": "Text is empty"}

        started = time.time()
        try:
            with tempfile.TemporaryDirectory(prefix="audiomind_tts_") as temp_dir_name:
                temp_dir = Path(temp_dir_name)
                text_path = temp_dir / "narration.txt"
                segment_dir = temp_dir / "segments"
                segment_dir.mkdir()
                text_path.write_text(text, encoding="utf-8")

                runner = Path(__file__).resolve().parents[1] / "scripts" / "kokoro_worker.py"
                command = self._command(runner, text_path, segment_dir)
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=max(300, min(1800, len(text) // 20)),
                    shell=False,
                )
                if result.returncode != 0:
                    error = (result.stderr or result.stdout or "Kokoro failed").strip()
                    return {"success": False, "file_path": None, "error": error[-2000:]}

                segment_files = sorted(segment_dir.glob("segment_*.wav"), key=self._segment_key)
                if not segment_files:
                    return {"success": False, "file_path": None, "error": "No audio segments generated"}

                final_path = Path(output_path) if output_path else self.output_dir / f"audiobook_{uuid.uuid4().hex}.wav"
                final_path.parent.mkdir(parents=True, exist_ok=True)
                duration = self._combine_wav(segment_files, final_path)
                return {
                    "success": True,
                    "file_path": str(final_path),
                    "file_size": final_path.stat().st_size / (1024 * 1024),
                    "duration": duration,
                    "elapsed": time.time() - started,
                    "format": "audio/wav",
                    "error": None,
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "file_path": None, "error": "Audio generation timed out"}
        except Exception as exc:
            return {"success": False, "file_path": None, "error": str(exc)}

    def _command(self, runner: Path, text_path: Path, segment_dir: Path) -> list[str]:
        conda = shutil.which("conda")
        if conda and self.kokoro_env:
            return [
                conda, "run", "--no-capture-output", "-n", self.kokoro_env,
                "python", str(runner), str(text_path), str(segment_dir),
            ]
        return [sys.executable, str(runner), str(text_path), str(segment_dir)]

    @staticmethod
    def _combine_wav(segment_files: list[Path], final_path: Path) -> float:
        """Combine compatible PCM WAV segments without requiring FFmpeg."""
        expected_format: tuple[int, int, int, str] | None = None
        total_frames = 0
        frame_rate = 0

        with wave.open(str(final_path), "wb") as output:
            for segment_file in segment_files:
                with wave.open(str(segment_file), "rb") as segment:
                    current_format = (
                        segment.getnchannels(),
                        segment.getsampwidth(),
                        segment.getframerate(),
                        segment.getcomptype(),
                    )
                    if expected_format is None:
                        expected_format = current_format
                        frame_rate = segment.getframerate()
                        output.setnchannels(segment.getnchannels())
                        output.setsampwidth(segment.getsampwidth())
                        output.setframerate(frame_rate)
                        output.setcomptype(segment.getcomptype(), segment.getcompname())
                    elif current_format != expected_format:
                        raise ValueError("Kokoro returned WAV segments with incompatible formats")

                    frame_count = segment.getnframes()
                    output.writeframes(segment.readframes(frame_count))
                    total_frames += frame_count

        return total_frames / frame_rate if frame_rate else 0.0

    @staticmethod
    def _segment_key(path: Path) -> tuple[int, int]:
        parts = path.stem.split("_")
        try:
            return int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            return (0, 0)
