from pathlib import Path

from audiomind import tts
from audiomind.tts import AudioGenerator
from scripts.kokoro_worker import split_text_into_chunks


def test_segment_sorting_is_numeric():
    paths = [Path("segment_10_0.wav"), Path("segment_2_1.wav"), Path("segment_2_0.wav")]
    ordered = sorted(paths, key=AudioGenerator._segment_key)
    assert [item.name for item in ordered] == [
        "segment_2_0.wav", "segment_2_1.wav", "segment_10_0.wav"
    ]


def test_empty_audio_input_is_rejected(tmp_path):
    result = AudioGenerator(output_dir=tmp_path).generate_audio("   ")
    assert result["success"] is False
    assert result["error"] == "Text is empty"


def test_worker_path_is_packaged():
    worker = Path(tts.__file__).resolve().parents[3] / "scripts" / "kokoro_worker.py"
    assert worker.exists()


def test_worker_splits_long_narration():
    chunks = split_text_into_chunks("First sentence. " * 80, max_length=120)
    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)
