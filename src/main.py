#!/usr/bin/env python3
"""
Flask-based frontend for chatbot with speech-to-text and text-to-speech.
Integrates ElevenLabs API and featherless chat.
"""

import os
import json
import io
from pathlib import Path
from audio_analysis import analyze_speech, build_audio_context


from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for
from openai import OpenAI

from elevenLabs import text_to_speech, speech_to_text
from featherless import run_featherless_chat, stream_featherless_chat
from immigration import run_interview_chat, stream_interview_chat
from env_loader import load_env_file


load_env_file()

# Use absolute paths for Vercel deployment compatibility
_src_dir = Path(__file__).parent.resolve()
app = Flask(
    __name__,
    template_folder=str(_src_dir / "templates"),
    static_folder=str(_src_dir / "static"),
)

# Language and country data
LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
}


def _initial_message(lang: str, user_name: str) -> str:
    """Opening message with one empathetic question; model will ask follow-ups."""
    name = user_name.strip() or "there"
    templates = {
        "en": f"Hi {name}! I'm here to help with your immigration journey. What do you need help with today?",
        "es": f"¡Hola {name}! Estoy aquí para ayudarte con tu proceso de inmigración. ¿En qué te puedo ayudar hoy?",
        "fr": f"Bonjour {name}! Je suis là pour vous aider dans votre parcours d'immigration. En quoi puis-je vous aider aujourd'hui ?",
        "de": f"Hallo {name}! Ich bin hier, um Sie bei Ihrer Einwanderung zu unterstützen. Wobei kann ich Ihnen heute helfen?",
        "it": f"Ciao {name}! Sono qui per aiutarti nel tuo percorso di immigrazione. Di cosa hai bisogno oggi?",
        "pt": f"Olá {name}! Estou aqui para ajudar na sua jornada de imigração. Em que posso ajudar hoje?",
        "ru": f"Привет {name}! Я здесь, чтобы помочь с иммиграцией. С чем вам помочь сегодня?",
        "ja": f"{name}さん、こんにちは！移民の手続きをお手伝いします。今日は何をお手伝いしましょうか？",
        "zh": f"{name}你好！我来帮你处理移民相关事宜。今天有什么需要帮忙的吗？",
        "ko": f"{name}님, 안녕하세요! 이민 과정을 도와드립니다. 오늘 무엇을 도와드릴까요?",
        "ar": f"مرحبا {name}! أنا هنا لمساعدتك في رحلة الهجرة. كيف يمكنني مساعدتك اليوم؟",
        "hi": f"नमस्ते {name}! मैं आपकी इमिग्रेशन यात्रा में मदद करने के लिए हूं। आज मैं आपकी कैसे मदद कर सकता हूं?",
    }
    return templates.get(lang, templates["en"])  

COUNTRIES = {
    "US": "United States",
    "GB": "United Kingdom",
    "ES": "Spain",
    "FR": "France",
    "DE": "Germany",
    "IT": "Italy",
    "BR": "Brazil",
    "MX": "Mexico",
    "JP": "Japan",
    "CN": "China",
    "IN": "India",
    "AU": "Australia",
}

# Voice mapping for different languages/countries
VOICE_MAP = {
    "en-US": "Adam",
    "en-GB": "Alice",
    "es-ES": "Antonio",
    "es-MX": "Diego",
    "fr-FR": "Matilda",
    "de-DE": "Hans",
    "it-IT": "Marco",
    "pt-BR": "Raquel",
    "ja-JP": "Yuki",
    "zh-CN": "Tingting",
    "ko-KR": "Min-jun",
}

# Conversation history for context
conversation_history = []
interview_mode = False
interview_context = None
# keep last-known user metadata so other endpoints (interview, translation, etc.) can pass it along
user_name_global: str = "User"
user_country_global: str = "US"
user_language_global: str = "en"


@app.route("/welcome")
def welcome():
    """Render the welcome screen."""
    return render_template("welcome.html")


@app.route("/")
def index():
    """Render the welcome screen."""
    return render_template("welcome.html")


@app.route("/chat")
def chat_page():
 
    """Render the main chat interface."""
    # Check if user has language preference
    lang = request.args.get("lang")
    if not lang:
        return redirect(url_for("index"))

    # /chat is a browser GET request, so prefer query params over JSON body.
    user_language = request.args.get("userLanguage", lang)
    user_country = request.args.get("country", "US")
    user_name = request.args.get("name", "User")
    # Track which params came from URL so we can overwrite stale localStorage
    from_url = {
        "name": "name" in request.args,
        "country": "country" in request.args,
        "lang": "lang" in request.args,
    }

    return render_template(
        "index.html",
        languages=LANGUAGES,
        countries=COUNTRIES,
        user_name=user_name,
        user_country=user_country,
        user_language=user_language,
        from_url=from_url,
        initialMessage=_initial_message(user_language, user_name),
    )


@app.route("/interview")
def interview_page():
    """Render the interview practice window."""
    return render_template("interview.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages."""
    global conversation_history

    data = request.json
    user_message = data.get("message", "")
    country = data.get("country", "US")
    user_name = data.get("userName", "User")
    user_language = data.get("userLanguage", "en")

    print(user_language, country, user_name)

    # update globals for use in other endpoints
    global user_name_global, user_country_global, user_language_global
    user_name_global = user_name
    user_country_global = country
    user_language_global = user_language

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Add user message to history
    conversation_history.append({"role": "user", "content": user_message})

    try:
        language_name = LANGUAGES.get(user_language, "English")

        def event_stream():
            assistant_parts = []
            try:
                for token in stream_featherless_chat(
                    messages=conversation_history,
                    user_language=user_language,
                    user_name=user_name,
                    user_country=country,
                ):
                    assistant_parts.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                assistant_message = "".join(assistant_parts).strip() or "No response"
                conversation_history.append({"role": "assistant", "content": assistant_message})
                yield (
                    "data: "
                    f"{json.dumps({'type': 'done', 'message': assistant_message, 'language': user_language, 'country': country})}"
                    "\n\n"
                )
            except Exception as stream_error:
                yield f"data: {json.dumps({'type': 'error', 'error': str(stream_error)})}\n\n"

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/speech-to-text", methods=["POST"])
def speech_to_text_endpoint():
    """Convert uploaded audio to text and return fluency analysis metadata."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "No audio file selected"}), 400

    try:
        stt_provider = os.getenv("STT_PROVIDER", "elevenlabs")

        # Save temporary audio file in a platform‑independent location
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_path = tmp.name
        audio_file.save(temp_path)

        # Transcribe using configured STT provider
        text = speech_to_text(temp_path, provider=stt_provider)

        # Analyse acoustic features for fluency/confidence coaching
        audio_features = analyze_speech(temp_path)
        audio_context = build_audio_context(audio_features)

        # Augment the transcription with audio metadata so the LLM can coach
        # on speaking style as well as content
        augmented_text = f"{text}\n\n{audio_context}"

        # Clean up
        try:
            os.remove(temp_path)
        except OSError:
            pass

        return jsonify({
            "text": text,
            "augmented_text": augmented_text,
            "audio_features": audio_features,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/text-to-speech", methods=["POST"])
def text_to_speech_endpoint():
    """Convert text to speech and return audio."""
    import tempfile
    
    data = request.json
    text = data.get("text", "")
    voice = data.get("voice", "JBFqnCBsd6RMkjVDRZzb")  # Use a valid ElevenLabs voice ID
    user_language = data.get("userLanguage", "en")
    country = data.get("country", "US")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # Create a temporary file for the mp3
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            temp_path = tmp.name
        
        # Generate speech and write to temp file
        text_to_speech(text, voice=voice, output_path=temp_path)

        # Read the audio file
        with open(temp_path, "rb") as f:
            audio_data = f.read()

        # Clean up temporary file
        try:
            os.remove(temp_path)
        except OSError:
            pass

        # encode as base64 so that the frontend can use atob() as expected
        import base64
        audio_b64 = base64.b64encode(audio_data).decode("ascii")

        return {
            "audio": audio_b64,
            "format": "mp3",
        }

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    """Start an AI practice interview."""
    global interview_mode, interview_context, conversation_history, user_name_global, user_country_global, user_language_global

    data = request.json
    interview_topic = data.get("topic", "general")
    user_language = data.get("userLanguage", user_language_global)
    country = data.get("country", user_country_global)
    user_name = data.get("userName", user_name_global)

    # Update globals so interview respond/end use the same context
    user_name_global = user_name
    user_country_global = country
    user_language_global = user_language

    # Reset conversation history for interview
    conversation_history = []
    interview_mode = True
    interview_context = {
        "topic": interview_topic,
        "user_language": user_language,
        "country": country,
        "user_name": user_name,
        "turn": 0,
    }

    # Start interview with opening question
    topic_descriptions = {
        "consular": "a consular visa interview for immigration purposes",
        "employment": "an employment-based immigration interview",
        "family": "a family-based immigration sponsorship interview",
        "asylum": "an asylum or refugee status interview",
        "adjustment": "an adjustment of status interview for permanent residence",
        "renewal": "a visa renewal or extension interview",
    }
    topic_desc = topic_descriptions.get(interview_topic, "an immigration interview")

    try:
        response = run_interview_chat(
            messages=[
                {
                    "role": "user",
                    "content": f"You are conducting {topic_desc}. Start the interview with your first question.",
                },
            ],
            user_language=user_language,
            user_name=user_name,
            user_country=country,
        )
        initial_question = response[0] if response else "Let's begin. Tell me about yourself."

        # Persist messages so all follow-up turns keep language & topic context
        conversation_history = [
            {"role": "assistant", "content": initial_question},
        ]
        interview_context["turn"] = 1

        return jsonify(
            {
                "question": initial_question,
                "mode": "interview",
            }
        )
    except Exception as e:
        interview_mode = False
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/respond", methods=["POST"])
def interview_respond():
    """Handle interview response."""
    global conversation_history, interview_context

    data = request.json
    user_response = data.get("response", "")

    if not user_response or not interview_mode:
        return jsonify({"error": "Not in interview mode"}), 400

    try:
        # Add user response to history
        conversation_history.append({"role": "user", "content": user_response})

        # Get interviewer response using interview mode
        response = run_interview_chat(
            messages=conversation_history,
            user_language=user_language_global,
            user_name=user_name_global,
            user_country=user_country_global,
        )
        interviewer_message = response[0] if response else "Thank you for that answer."

        # Add to history
        conversation_history.append({"role": "assistant", "content": interviewer_message})
        interview_context["turn"] += 1

        return jsonify(
            {
                
                "message": interviewer_message,
                "turn": interview_context["turn"],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/end", methods=["POST"])
def end_interview():
    """End the interview and provide feedback."""
    global interview_mode, conversation_history

    interview_mode = False

    try:
        # Get final feedback
        feedback_prompt = {
            "role": "user",
            "content": """Based on this practice interview, provide a brief summary of:
1. Strengths demonstrated
2. Areas for improvement
3. One key tip for success in this type of interview

Keep it concise and constructive.""",
        }

        conversation_history.append(feedback_prompt)
        response = run_interview_chat(
            messages=conversation_history,
            user_language=user_language_global,
            user_name=user_name_global,
            user_country=user_country_global,
        )
        feedback = response[0] if response else "Great practice session!"

        return jsonify({"feedback": feedback})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
def clear_chat():
    """Clear chat history."""
    global conversation_history
    conversation_history = []
    return jsonify({"status": "cleared"})


@app.route("/api/translate-last", methods=["POST"])
def translate_last():
    """Translate a given message into the requested language."""
    global conversation_history
    data = request.json
    text = data.get("text", "")
    user_language = data.get("userLanguage", "en")
    language_name = LANGUAGES.get(user_language, "English")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        response = run_featherless_chat(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a translator. Translate the following text into {language_name}. Output only the translated text, nothing else.",
                },
                {"role": "user", "content": text},
            ],
            user_language=user_language_global,
            user_name=user_name_global,
            user_country=user_country_global,
        )
        translated = response[0] if response else text

        # Keep history coherent so future replies use the new language
        for i in range(len(conversation_history) - 1, -1, -1):
            if conversation_history[i].get("role") == "assistant":
                conversation_history[i]["content"] = translated
                break

        return jsonify({"message": translated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/suggestions", methods=["POST"])
def suggestions():
    data = request.json
    last_message = data.get("message", "")
    user_language = data.get("userLanguage", "en")
    language_name = LANGUAGES.get(user_language, "English")

    if not last_message:
        return jsonify({"suggestions": []})

    try:
        api_key = os.getenv("FEATHERLESS_API_KEY")
        if not api_key:
            raise RuntimeError("FEATHERLESS_API_KEY is not set")

        client = OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)
        # Strip markdown and collapse whitespace so the model doesn't just echo the lines back
        import re
        clean_message = re.sub(r'\*+', '', last_message)
        clean_message = re.sub(r'\s+', ' ', clean_message).strip()[:500]

        prompt = (
            f"An immigration assistant just replied to a user with this message:\n"
            f"\"{clean_message}\"\n\n"
            f"Your task: invent 3 short questions a user might ask NEXT, based on that topic.\n"
            f"Rules:\n"
            f"- Each question must start with a question word (How, What, Can, Do, Is, When, Where, Why, etc.)\n"
            f"- Do NOT copy or quote any text from the assistant's message above\n"
            f"- Do NOT number the questions or add bullets\n"
            f"- Write in {language_name}\n"
            f"- Output ONLY the 3 questions, one per line, nothing else\n\n"
            f"Questions:"
        )
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content if resp.choices else ""
        # Only keep lines that look like questions (end with ? or start with question word)
        question_words = ("how", "what", "can", "do", "is", "when", "where", "why", "will", "should", "could", "would", "are", "does")
        all_lines = [q.strip() for q in raw.strip().splitlines() if q.strip()]
        questions = [q for q in all_lines if q.endswith("?") or q.lower().split()[0] in question_words][:3]
        if not questions:
            questions = all_lines[:3]
        return jsonify({"suggestions": questions})
    except Exception as e:
        return jsonify({"suggestions": [], "error": str(e)})

def main():
    """Run the Flask development server."""
    port = int(os.environ.get("PORT", 4000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
