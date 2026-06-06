from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .errors import GeminiError

Progress = Callable[[str], None]

_PROMPT = """
Faca a transcricao na integra de toda a fala deste audio.

Regras obrigatorias:
1. Detecte o idioma predominante da fala.
2. Se a fala estiver em portugues, transcreva-a fielmente em portugues.
3. Se estiver em outro idioma, traduza toda a fala para portugues brasileiro.
4. Inclua somente o que foi falado. Nao descreva imagens, cenas, pessoas,
   acoes, musica, sons, ambiente, emocoes ou elementos visuais.
5. Nao inclua introducoes, conclusoes, explicacoes, comentarios, rotulos de
   locutor, notas entre colchetes ou qualquer texto que nao seja a fala.
6. Nao resuma, nao omita, nao reorganize e nao complete trechos.
7. Preserve paragrafos e pontuacao natural. Nao inclua timestamps.
8. Em "primeira_frase", retorne a primeira frase completa da transcricao em
   portugues, adequada para nomear um arquivo.
9. Se nao houver fala inteligivel, use primeira_frase vazia e
   transcricao_portugues igual a "[Nenhuma fala reconhecivel.]".
""".strip()

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "idioma_detectado": {
            "type": "string",
            "description": "Idioma predominante detectado na fala.",
        },
        "primeira_frase": {
            "type": "string",
            "description": "Primeira frase completa em portugues, ou vazia sem fala.",
        },
        "transcricao_portugues": {
            "type": "string",
            "description": "Transcricao ou traducao integral em portugues.",
        },
    },
    "required": [
        "idioma_detectado",
        "primeira_frase",
        "transcricao_portugues",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Transcription:
    detected_language: str
    first_sentence: str
    portuguese_text: str


class GeminiTranscriber:
    def __init__(
        self,
        api_key: str,
        *,
        poll_interval: float = 2.0,
        processing_timeout: float = 600.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise GeminiError(
                "Defina a variavel de ambiente GEMINI_API_KEY antes de executar."
            )
        if client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise GeminiError(
                    "Dependencia google-genai ausente. Reinstale reel-transcribe."
                ) from exc
            client = genai.Client(api_key=api_key)

        self._client = client
        self._poll_interval = poll_interval
        self._processing_timeout = processing_timeout
        self._max_attempts = max_attempts
        self._sleep = sleep

    def transcribe(
        self,
        audio_path: Path,
        model: str,
        progress: Progress | None = None,
    ) -> Transcription:
        uploaded = None
        try:
            if progress:
                progress("Enviando audio ao Gemini...")
            uploaded = self._retry(
                lambda: self._client.files.upload(file=str(audio_path))
            )
            uploaded = self._wait_until_active(uploaded, progress)

            if progress:
                progress("Transcrevendo e traduzindo com o Gemini...")
            response = self._retry(
                lambda: self._client.models.generate_content(
                    model=model,
                    contents=[uploaded, _PROMPT],
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": _RESPONSE_SCHEMA,
                        "temperature": 0,
                        "max_output_tokens": 65536,
                    },
                )
            )
            return self._parse_response(getattr(response, "text", None))
        except GeminiError:
            raise
        except Exception as exc:
            raise GeminiError(f"Falha ao processar o audio com o Gemini: {exc}") from exc
        finally:
            if uploaded is not None:
                name = getattr(uploaded, "name", None)
                if name:
                    try:
                        self._client.files.delete(name=name)
                    except Exception:
                        pass

    def _wait_until_active(self, uploaded: Any, progress: Progress | None) -> Any:
        deadline = time.monotonic() + self._processing_timeout
        current = uploaded

        while True:
            state = self._state_name(current)
            if state == "ACTIVE":
                return current
            if state in {"FAILED", "ERROR"}:
                raise GeminiError("O Gemini nao conseguiu preparar o arquivo enviado.")
            if time.monotonic() >= deadline:
                raise GeminiError("O Gemini excedeu o tempo limite ao preparar o audio.")

            if progress:
                progress("Aguardando o Gemini preparar o audio...")
            self._sleep(self._poll_interval)
            current = self._retry(
                lambda: self._client.files.get(name=getattr(current, "name"))
            )

    @staticmethod
    def _state_name(file: Any) -> str:
        state = getattr(file, "state", None)
        name = getattr(state, "name", state)
        if name is None:
            return "ACTIVE"
        return str(name).upper().split(".")[-1]

    def _retry(self, operation: Callable[[], Any]) -> Any:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return operation()
            except Exception as exc:
                if attempt >= self._max_attempts or not self._is_transient(exc):
                    raise
                self._sleep(min(2 ** (attempt - 1), 8))
        raise AssertionError("loop de tentativas terminou inesperadamente")

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        code = getattr(exc, "status_code", None)
        if code in {408, 409, 429, 500, 502, 503, 504}:
            return True
        text = str(exc).lower()
        return any(
            marker in text
            for marker in (
                "timeout",
                "temporarily unavailable",
                "connection reset",
                "429",
                "500",
                "502",
                "503",
                "504",
            )
        )

    @staticmethod
    def _parse_response(raw: str | None) -> Transcription:
        if not raw:
            raise GeminiError("O Gemini retornou uma resposta vazia.")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GeminiError("O Gemini retornou uma resposta que nao e JSON valido.") from exc

        required = (
            "idioma_detectado",
            "primeira_frase",
            "transcricao_portugues",
        )
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), str) for key in required
        ):
            raise GeminiError("A resposta do Gemini esta incompleta ou invalida.")

        transcript = data["transcricao_portugues"].strip()
        if not transcript:
            raise GeminiError("O Gemini retornou uma transcricao vazia.")

        return Transcription(
            detected_language=data["idioma_detectado"].strip(),
            first_sentence=data["primeira_frase"].strip(),
            portuguese_text=transcript,
        )
