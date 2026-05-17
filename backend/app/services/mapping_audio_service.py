from __future__ import annotations

import importlib
import io
import json
import re
import wave
from functools import lru_cache
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.core.config import settings


LMSTUDIO_ORPHEUS_VOICES: tuple[str, ...] = ("tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe")
LMSTUDIO_ORPHEUS_CUSTOM_TOKEN_PREFIX = "<custom_token_"


def synthesize_orpheus_wav(text: str, *, voice: str | None = None, model: str | None = None) -> bytes:
    normalized_text = _normalize_chunk_text(text)
    if not normalized_text:
        raise ValueError("Spoken script is empty; generate narration before audio synthesis.")
    if settings.tts_provider.strip().lower() != "lmstudio_orpheus":
        raise ValueError("Current backend TTS provider is not lmstudio_orpheus.")

    chunks = _split_orpheus_text(normalized_text)
    pause_pcm = _build_silence_pcm(180)
    pcm_segments: list[bytes] = []
    resolved_voice = _resolve_voice(voice)
    resolved_model = str(model or settings.lmstudio_orpheus_model or "orpheus-3b-0.1-ft").strip()

    for index, chunk in enumerate(chunks):
        pcm_segments.append(_generate_orpheus_pcm(chunk, voice=resolved_voice, model=resolved_model))
        if index < len(chunks) - 1:
            pcm_segments.append(pause_pcm)

    return pcm_to_wav_bytes(b"".join(pcm_segments), sample_rate=24000)


def _generate_orpheus_pcm(text: str, *, voice: str, model: str) -> bytes:
    token_stream = _stream_orpheus_tokens(
        _completions_url(),
        {
            "model": model,
            "prompt": _format_orpheus_prompt(text, voice),
            "max_tokens": 1200,
            "temperature": 0.6,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "stream": True,
        },
    )

    collected_ids: list[int] = []
    audio_chunks: list[bytes] = []
    token_index = 0
    for token_text in token_stream:
        token_id = _extract_orpheus_token_id(token_text, token_index)
        if token_id is None or token_id <= 0:
            continue

        collected_ids.append(token_id)
        token_index += 1
        if token_index % 7 == 0 and token_index > 27:
            audio_chunk = _decode_orpheus_window(collected_ids[-28:])
            if audio_chunk:
                audio_chunks.append(audio_chunk)

    if not audio_chunks:
        raise ValueError(
            "LM Studio Orpheus did not produce decodable audio tokens. Confirm the model is loaded and the local server is running."
        )

    return b"".join(audio_chunks)


def _resolve_voice(voice: str | None) -> str:
    resolved_voice = str(voice or settings.lmstudio_orpheus_voice or "tara").strip().lower()
    if resolved_voice not in LMSTUDIO_ORPHEUS_VOICES:
        return "tara"
    return resolved_voice


def _completions_url() -> str:
    configured = str(settings.lmstudio_tts_base_url or "").strip() or str(settings.lmstudio_base_url or "").strip()
    parsed = parse.urlparse(configured)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1/completions"):
        completions_path = path
    elif path.endswith("/v1/chat/completions"):
        completions_path = path[: -len("/chat/completions")] + "/completions"
    elif path.endswith("/v1"):
        completions_path = f"{path}/completions"
    else:
        completions_path = "/v1/completions"
    return parse.urlunparse(parsed._replace(path=completions_path, params="", query="", fragment=""))


def _format_orpheus_prompt(text: str, voice: str) -> str:
    return f"<|audio|>{voice}: {text}<|eot_id|>"


def _stream_orpheus_tokens(url: str, payload: dict[str, object]) -> list[str]:
    http_request = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    collected_tokens: list[str] = []
    try:
        with request.urlopen(http_request, timeout=settings.tts_timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    event_payload = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = event_payload.get("choices") or []
                if not choices:
                    continue
                token_text = str(choices[0].get("text") or "")
                if token_text:
                    collected_tokens.append(token_text)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace").strip()
        detail = f" {error_body}" if error_body else ""
        raise ValueError(f"LM Studio Orpheus request failed with HTTP {exc.code}.{detail}") from exc
    except URLError as exc:
        raise ValueError(f"LM Studio Orpheus request failed: {exc.reason}") from exc
    return collected_tokens


def _extract_orpheus_token_id(token_text: str, index: int) -> int | None:
    compact = token_text.strip()
    token_start = compact.rfind(LMSTUDIO_ORPHEUS_CUSTOM_TOKEN_PREFIX)
    if token_start == -1:
        return None

    token_fragment = compact[token_start:]
    if not token_fragment.startswith(LMSTUDIO_ORPHEUS_CUSTOM_TOKEN_PREFIX) or not token_fragment.endswith(">"):
        return None

    try:
        number_str = token_fragment[len(LMSTUDIO_ORPHEUS_CUSTOM_TOKEN_PREFIX) : -1]
        return int(number_str) - 10 - ((index % 7) * 4096)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _get_snac_decoder() -> tuple[object, object, str]:
    try:
        snac_module = importlib.import_module("snac")
    except ImportError as exc:
        raise ImportError("Missing dependency 'snac'. Install backend requirements to use LM Studio Orpheus TTS.") from exc

    try:
        torch = importlib.import_module("torch")
    except ImportError as exc:
        raise ImportError("Missing dependency 'torch'. Install backend requirements to use LM Studio Orpheus TTS.") from exc

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "mps"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        else "cpu"
    )
    model = snac_module.SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval().to(device)
    return model, torch, device


def _decode_orpheus_window(multiframe: list[int]) -> bytes | None:
    if len(multiframe) < 28:
        return None

    codes_0: list[int] = []
    codes_1: list[int] = []
    codes_2: list[int] = []
    frame_count = len(multiframe) // 7
    frame = multiframe[: frame_count * 7]

    for frame_index in range(frame_count):
        base_index = frame_index * 7
        codes_0.append(frame[base_index])
        codes_1.extend((frame[base_index + 1], frame[base_index + 4]))
        codes_2.extend((frame[base_index + 2], frame[base_index + 3], frame[base_index + 5], frame[base_index + 6]))

    for code_list in (codes_0, codes_1, codes_2):
        if any(code < 0 or code > 4096 for code in code_list):
            return None

    decoder_model, torch, device = _get_snac_decoder()
    codes = [
        torch.tensor(codes_0, device=device, dtype=torch.int32).unsqueeze(0),
        torch.tensor(codes_1, device=device, dtype=torch.int32).unsqueeze(0),
        torch.tensor(codes_2, device=device, dtype=torch.int32).unsqueeze(0),
    ]

    with torch.inference_mode():
        audio_hat = decoder_model.decode(codes)

    audio_slice = audio_hat[:, :, 2048:4096].detach().cpu().clamp(-1, 1)
    audio_int16 = (audio_slice * 32767).to(dtype=torch.int16)
    return audio_int16.numpy().tobytes()


def _split_orpheus_text(text: str) -> list[str]:
    chunk_char_limit = 260
    paragraphs = [_normalize_chunk_text(part) for part in re.split(r"\n{2,}", text) if part.strip()]
    segments: list[str] = []

    for paragraph in paragraphs or [text]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
        for sentence in sentences or [paragraph]:
            if len(sentence) <= chunk_char_limit:
                segments.append(sentence)
                continue
            segments.extend(_split_long_orpheus_segment(sentence, chunk_char_limit))

    merged: list[str] = []
    current = ""
    for segment in segments:
        candidate = f"{current} {segment}".strip() if current else segment
        if current and len(candidate) > chunk_char_limit:
            merged.append(current)
            current = segment
        else:
            current = candidate

    if current:
        merged.append(current)
    return merged or [_normalize_chunk_text(text)]


def _split_long_orpheus_segment(text: str, chunk_char_limit: int) -> list[str]:
    clause_parts = [part.strip() for part in re.split(r"(?<=[,;:])\s+", text) if part.strip()]
    if len(clause_parts) <= 1:
        return _split_orpheus_words(text, chunk_char_limit)

    pieces: list[str] = []
    current = ""
    for part in clause_parts:
        candidate = f"{current} {part}".strip() if current else part
        if current and len(candidate) > chunk_char_limit:
            pieces.append(current)
            current = part
        else:
            current = candidate
    if current:
        pieces.append(current)

    final_pieces: list[str] = []
    for piece in pieces:
        if len(piece) <= chunk_char_limit:
            final_pieces.append(piece)
        else:
            final_pieces.extend(_split_orpheus_words(piece, chunk_char_limit))
    return final_pieces


def _split_orpheus_words(text: str, chunk_char_limit: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    pieces: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) > chunk_char_limit:
            pieces.append(current)
            current = word
        else:
            current = candidate
    pieces.append(current)
    return pieces


def _normalize_chunk_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_silence_pcm(duration_ms: int, sample_rate: int = 24000) -> bytes:
    frame_count = int(sample_rate * (duration_ms / 1000.0))
    return b"\x00\x00" * frame_count


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    if len(pcm_bytes) % 2 != 0:
        raise ValueError("PCM payload length must be divisible by 2 for 16-bit mono audio.")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()