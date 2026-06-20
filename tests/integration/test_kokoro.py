"""Optional smoke test for the external Kokoro Conda environment."""

import os
import subprocess

import pytest

from audiomind.tts import AudioGenerator


@pytest.mark.integration
def test_kokoro_environment():
    if os.getenv("RUN_KOKORO_INTEGRATION") != "1":
        pytest.skip("Set RUN_KOKORO_INTEGRATION=1 to run the Kokoro smoke test")

    environment = os.getenv("KOKORO_ENV_NAME", "ai")
    conda = subprocess.run(
        ["conda", "--version"], capture_output=True, text=True, timeout=30, shell=False
    )
    assert conda.returncode == 0, conda.stderr

    python = subprocess.run(
        ["conda", "run", "-n", environment, "python", "--version"],
        capture_output=True, text=True, timeout=120, shell=False,
    )
    assert python.returncode == 0, python.stderr

    kokoro = subprocess.run(
        [
            "conda", "run", "-n", environment, "python", "-c",
            "from kokoro import KPipeline; print(KPipeline)",
        ],
        capture_output=True, text=True, timeout=120, shell=False,
    )
    assert kokoro.returncode == 0, kokoro.stderr


@pytest.mark.integration
def test_kokoro_generates_wav(tmp_path):
    if os.getenv("RUN_KOKORO_INTEGRATION") != "1":
        pytest.skip("Set RUN_KOKORO_INTEGRATION=1 to run the Kokoro smoke test")

    output = tmp_path / "smoke.wav"
    result = AudioGenerator(
        kokoro_env_name=os.getenv("KOKORO_ENV_NAME", "ai"),
        output_dir=tmp_path,
    ).generate_audio(
        "Hello listeners. This is a short AudioMind audio generation test.",
        output,
    )
    assert result["success"], result["error"]
    assert output.exists()
    assert output.stat().st_size > 1_000
