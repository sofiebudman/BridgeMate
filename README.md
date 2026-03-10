# BridgeMate

This is a Flask application that provides an AI‑powered chat interface with
speech‑to‑text and text‑to‑speech features.  The frontend uses vanilla JavaScript
and interacts with the backend over simple `/api/*` endpoints.

> ⚠️ **Important**
> The web UI must be loaded via the Flask server (e.g. `http://localhost:4000`).
> Opening `index.html` directly from the file system will lead to errors such as
> "Invalid URL" when you try to record audio, because the browser cannot resolve
> the relative API paths.

## Running

```bash
uv venv .venv
source .venv/bin/activate   # or `.venv\\Scripts\\activate` on Windows
uv sync

# Configure environment variables
cp .env.example .env

# Start the app
uv run src/main.py
```

## Environment variables

The app loads `.env` automatically at startup.

Required:

- `FEATHERLESS_API_KEY`
- `HF_API_TOKEN`
- `ELEVENLABS_API_KEY`

Optional:

- `STT_PROVIDER` (`elevenlabs` or `whisper`, default `elevenlabs`)

Use `.env.example` as the template for your local `.env` file.

## Speech-to-text provider toggle

`/api/speech-to-text` supports two providers:

- `elevenlabs` (default): Uses ElevenLabs `scribe_v2`
- `whisper`: Uses Hugging Face Inference API model `openai/whisper-large-v3`

Choose the backend provider with the `STT_PROVIDER` environment variable before
starting the server.

Then open your browser at `http://localhost:4000` and start chatting or
recording.
