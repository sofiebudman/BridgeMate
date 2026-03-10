# BridgeMate
<img width="498" height="282" alt="Screenshot 2026-03-09 at 5 14 30 PM" src="https://github.com/user-attachments/assets/fc69a582-1270-482e-962e-43d62fb7e55f" />


**BridgMate** is a Flask application that provides an AI‑powered chat interface with
speech‑to‑text and text‑to‑speech features specializing in US Immigration policy. BridgeMate helps users prepare for interviews by simulating real-world scenarios, offering personalized guidance, and generating step-by-step immigration roadmaps. It combines AI, automatic speech recognition, RAG, and resources to make navigating the immigration process clearer and more manageable.

Built with Python, Flask, JavaScript, HTML, CSS. 


## Running

> ⚠️ **Important**
> The web UI must be loaded via the Flask server (e.g. `http://localhost:4000`).
> Opening `index.html` directly from the file system will lead to errors such as
> "Invalid URL" when you try to record audio, because the browser cannot resolve
> the relative API paths.

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
