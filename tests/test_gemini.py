import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from reel_transcribe.errors import GeminiError
from reel_transcribe.gemini import GeminiTranscriber


class FakeFiles:
    def __init__(self, states=None):
        self.states = list(states or ["ACTIVE"])
        self.deleted = []
        self.upload_calls = 0
        self.uploaded_file = None

    def upload(self, file):
        self.upload_calls += 1
        self.uploaded_file = file
        return SimpleNamespace(name="files/123", state=self.states.pop(0))

    def get(self, name):
        return SimpleNamespace(name=name, state=self.states.pop(0))

    def delete(self, name):
        self.deleted.append(name)


class FakeModels:
    def __init__(self, response_text, failures=0):
        self.response_text = response_text
        self.failures = failures
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures:
            self.failures -= 1
            error = RuntimeError("503 temporarily unavailable")
            error.status_code = 503
            raise error
        return SimpleNamespace(text=self.response_text)


def client(response_text, *, states=None, failures=0):
    return SimpleNamespace(
        files=FakeFiles(states),
        models=FakeModels(response_text, failures),
    )


def valid_response(language="ingles", sentence="Ola mundo."):
    return json.dumps(
        {
            "idioma_detectado": language,
            "primeira_frase": sentence,
            "transcricao_portugues": f"{sentence} Texto completo.",
        }
    )


def test_transcribes_or_translates_and_deletes_remote_file(tmp_path: Path):
    fake = client(valid_response(), states=["PROCESSING", "ACTIVE"])
    transcriber = GeminiTranscriber(
        "key",
        client=fake,
        poll_interval=0,
        sleep=lambda _: None,
    )

    audio_path = tmp_path / "audio.mp3"
    result = transcriber.transcribe(audio_path, "gemini-3.1-pro-preview")

    assert result.detected_language == "ingles"
    assert result.first_sentence == "Ola mundo."
    assert result.portuguese_text == "Ola mundo. Texto completo."
    assert fake.files.uploaded_file == str(audio_path)
    assert fake.files.deleted == ["files/123"]
    prompt = fake.models.calls[0]["contents"][1]
    assert "transcricao na integra" in prompt
    assert "Nao descreva imagens, cenas" in prompt
    config = fake.models.calls[0]["config"]
    assert config["response_mime_type"] == "application/json"
    assert config["max_output_tokens"] == 65536


def test_retries_transient_generation_failure(tmp_path: Path):
    fake = client(valid_response(), failures=1)
    transcriber = GeminiTranscriber("key", client=fake, sleep=lambda _: None)
    transcriber.transcribe(tmp_path / "audio.mp3", "model")
    assert len(fake.models.calls) == 2


@pytest.mark.parametrize("raw", [None, "not-json", "{}", '{"idioma_detectado": 1}'])
def test_rejects_invalid_response(raw, tmp_path: Path):
    fake = client(raw)
    transcriber = GeminiTranscriber("key", client=fake, sleep=lambda _: None)
    with pytest.raises(GeminiError):
        transcriber.transcribe(tmp_path / "audio.mp3", "model")
    assert fake.files.deleted == ["files/123"]


def test_requires_api_key():
    with pytest.raises(GeminiError, match="GEMINI_API_KEY"):
        GeminiTranscriber(" ")
