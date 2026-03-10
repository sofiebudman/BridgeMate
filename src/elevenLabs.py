#!/usr/bin/env python3
"""
Helper functions for interacting with the ElevenLabs REST API.
Provides simple wrappers for text-to-speech and speech-to-text.
"""

import os
from io import BytesIO
from typing import Optional

import requests
from elevenlabs.client import ElevenLabs
from env_loader import load_env_file


load_env_file()

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_WHISPER_URL = "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3"
 

def _get_elevenlabs_client(api_key: Optional[str] = None) -> ElevenLabs:
    key = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("API key not provided; set ELEVENLABS_API_KEY or pass api_key")
    return ElevenLabs(api_key=key)


def text_to_speech(
    text: str,
    voice: str = "alloy",
    api_key: Optional[str] = None,
    output_path: str = "speech.mp3",
) -> str:
    """Convert ``text`` into an audio file using ElevenLabs' text-to-speech.

    Args:
        text: Text to synthesise.
        voice: Voice identifier, e.g. ``"alloy"`` or a custom voice id.
        api_key: Optional API key override. If ``None`` the
            ``ELEVEN_LABS_API_KEY`` environment variable is used.
        output_path: Where to write the generated audio.

    Returns:
        The path to the written audio file (``output_path``).
    """
    elevenlabs = _get_elevenlabs_client(api_key)

    # Use the ElevenLabs client to generate speech
    audio = elevenlabs.text_to_speech.convert(
        text=text,
        voice_id=voice,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    # Write the audio bytes to the output file
    # The SDK returns a generator of audio chunks
    with open(output_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)
    return output_path


def _speech_to_text_elevenlabs(audio_path: str, api_key: Optional[str] = None) -> str:
    elevenlabs = _get_elevenlabs_client(api_key)

    with open(audio_path, "rb") as f:
        audio_data = BytesIO(f.read())

    transcription = elevenlabs.speech_to_text.convert(
        file=audio_data,
        model_id="scribe_v2",
        tag_audio_events=True,  
        language_code="eng",   
        diarize=True,         
    )

    return transcription.text


def _speech_to_text_whisper(audio_path: str) -> str:
    if not HF_API_TOKEN:
        raise RuntimeError("HF token not provided; set HF_API_TOKEN")

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "audio/wav",
    }
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            HF_WHISPER_URL,
            headers=headers,
            data=audio_file,
            timeout=120,
        )

    if not response.ok:
        raise RuntimeError(
            f"Whisper transcription failed ({response.status_code}): {response.text}"
        )

    payload = response.json()

    # Some HF providers can return a list of segment objects instead of a dict.
    if isinstance(payload, list):
        parts = []
        for item in payload:
            if isinstance(item, dict):
                segment = str(item.get("text", "")).strip()
                if segment:
                    parts.append(segment)
        if parts:
            return " ".join(parts)

    if isinstance(payload, dict):
        text = payload.get("text", "").strip()
        if text:
            return text

        if "error" in payload:
            raise RuntimeError(f"Whisper API error: {payload['error']}")

    raise RuntimeError(f"Unexpected Whisper response: {payload}")


def speech_to_text(
    audio_path: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Transcribe audio with either ElevenLabs or Hugging Face Whisper.

    Provider is selected by argument first, then ``STT_PROVIDER`` env var,
    defaulting to ``elevenlabs``.
    """
    selected_provider = (provider or os.getenv("STT_PROVIDER", "elevenlabs")).lower()

    if selected_provider == "whisper":
        return _speech_to_text_whisper(audio_path)

    if selected_provider == "elevenlabs":
        return _speech_to_text_elevenlabs(audio_path, api_key=api_key)

    raise ValueError(
        f"Unsupported STT provider '{selected_provider}'. Use 'elevenlabs' or 'whisper'."
    )

if __name__ == "__main__":
    # simple CLI example
    import argparse

    parser = argparse.ArgumentParser(description="ElevenLabs helper commands")
    sub = parser.add_subparsers(dest="command")

    tts = sub.add_parser("tts", help="text to speech")
    tts.add_argument("text", help="text to synthesise")
    tts.add_argument(
        "-v", "--voice", default="alloy", help="voice id to use (default alloy)"
    )
    tts.add_argument(
        "-o", "--output", default="speech.mp3", help="output audio file"
    )

    stt = sub.add_parser("stt", help="speech to text")
    stt.add_argument("file", help="audio file to transcribe")

    args = parser.parse_args()
    if args.command == "tts":
        path = text_to_speech(args.text, voice=args.voice, output_path=args.output)
        print("written", path)
    elif args.command == "stt":
        text = speech_to_text(args.file)
        print(text)
    else:
        parser.print_help()