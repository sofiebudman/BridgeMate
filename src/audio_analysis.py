import librosa
import numpy as np

def analyze_speech(audio_path: str) -> dict:
    """Extract fluency and confidence proxies from audio."""
    y, sr = librosa.load(audio_path, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)

    # Speaking rate proxy: non-silent frames / total duration
    intervals = librosa.effects.split(y, top_db=30)  # voiced segments
    speaking_duration = sum((e - s) for s, e in intervals) / sr
    speech_ratio = speaking_duration / duration if duration > 0 else 0

    # Energy variance — high variance can indicate hesitation or stress
    rms = librosa.feature.rms(y=y)[0]
    energy_variance = float(np.var(rms))

    # Pause count — number of silent gaps
    pause_count = max(0, len(intervals) - 1)

    return {
        "duration_seconds": round(duration, 1),
        "speech_ratio": round(speech_ratio, 2),       # 0–1, higher = less silence
        "pause_count": pause_count,
        "energy_variance": round(energy_variance, 6), # proxy for voice steadiness
    }


def build_audio_context(features: dict) -> str:
    """Format audio analysis features as a compact string for LLM injection."""
    return (
        f"[Audio analysis: duration={features['duration_seconds']}s, "
        f"speech_ratio={features['speech_ratio']}, "
        f"pauses={features['pause_count']}, "
        f"energy_variance={features['energy_variance']}]"
    )