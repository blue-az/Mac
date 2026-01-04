#!/usr/bin/env python3
"""
Transcribe tennis session audio to detect shot announcements.

Uses whisper-cpp (Homebrew) to transcribe Watch audio and extract
shot type announcements with timestamps.

Usage:
    python transcribe_audio.py <audio_file>
    python transcribe_audio.py ~/Documents/audio/audio_watch_20260104_123456.m4a

Output:
    announcements.csv - timestamp, text, detected_stroke
"""

import argparse
import csv
import json
import re
import subprocess
import tempfile
from pathlib import Path


# Whisper model path
WHISPER_MODEL = Path(__file__).parent / "models/whisper/ggml-base.en.bin"

# Keywords to detect stroke types
STROKE_KEYWORDS = {
    "forehand": ["forehand", "four hand", "for hand", "fore hand"],
    "backhand": ["backhand", "back hand", "back end"],
    "serve": ["serve", "server", "surf"],
}


def convert_to_wav(input_path: Path, output_path: Path) -> bool:
    """Convert audio file to WAV format for whisper-cpp."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",      # Mono
                "-c:a", "pcm_s16le",  # 16-bit PCM
                str(output_path)
            ],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting audio: {e.stderr.decode()}")
        return False


def transcribe_audio(wav_path: Path) -> list:
    """
    Run whisper-cpp transcription and return segments with timestamps.

    Returns list of dicts: [{"start_ms": int, "end_ms": int, "text": str}, ...]
    """
    if not WHISPER_MODEL.exists():
        print(f"Error: Whisper model not found at {WHISPER_MODEL}")
        print("Download with: curl -L -O https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin")
        return []

    # Ensure absolute paths
    wav_path = Path(wav_path).resolve()
    model_path = WHISPER_MODEL.resolve()

    # Run whisper-cli with JSON output
    try:
        result = subprocess.run(
            [
                "whisper-cli",
                "-m", str(model_path),
                "-f", str(wav_path),
                "-oj",  # Output JSON
                "-t", "4",  # 4 threads
            ],
            capture_output=True,
            text=True
        )
    except FileNotFoundError:
        print("Error: whisper-cli not found. Install with: brew install whisper-cpp")
        return []

    # Parse JSON output
    segments = []

    # whisper-cli outputs JSON as input_file.json (e.g., audio.wav -> audio.wav.json)
    json_path = Path(str(wav_path) + ".json")

    if json_path.exists():
        with open(json_path) as f:
            data = json.load(f)
            for seg in data.get("transcription", []):
                segments.append({
                    "start_ms": int(seg["offsets"]["from"]),
                    "end_ms": int(seg["offsets"]["to"]),
                    "text": seg["text"].strip().lower(),
                })
        # Clean up JSON file
        json_path.unlink()
    else:
        # Fallback: parse stdout if JSON file not created
        # Format: [00:00:00.000 --> 00:00:02.000]   text here
        pattern = r'\[(\d+):(\d+):(\d+\.\d+)\s*-->\s*(\d+):(\d+):(\d+\.\d+)\]\s*(.*)'
        for line in result.stdout.split('\n'):
            match = re.match(pattern, line)
            if match:
                h1, m1, s1, h2, m2, s2, text = match.groups()
                start_ms = int((int(h1)*3600 + int(m1)*60 + float(s1)) * 1000)
                end_ms = int((int(h2)*3600 + int(m2)*60 + float(s2)) * 1000)
                segments.append({
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": text.strip().lower(),
                })

    return segments


def detect_stroke_type(text: str) -> str:
    """Detect stroke type from transcribed text."""
    text_lower = text.lower()

    for stroke, keywords in STROKE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return stroke

    return ""


def extract_announcements(segments: list) -> list:
    """
    Extract shot announcements from transcription segments.

    Returns list of dicts with detected stroke types.
    """
    announcements = []

    for seg in segments:
        stroke = detect_stroke_type(seg["text"])
        if stroke:
            announcements.append({
                "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "text": seg["text"],
                "stroke": stroke,
            })

    return announcements


def transcribe_session(audio_path: Path, output_dir: Path = None) -> Path:
    """
    Full transcription pipeline for a tennis session audio file.

    Args:
        audio_path: Path to .m4a or other audio file
        output_dir: Where to save announcements.csv (default: same as audio)

    Returns:
        Path to announcements.csv
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_path}")
        return None

    if output_dir is None:
        output_dir = audio_path.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing: {audio_path.name}")

    # Convert to WAV if needed
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    if audio_path.suffix.lower() != ".wav":
        print("  Converting to WAV...")
        if not convert_to_wav(audio_path, wav_path):
            return None
    else:
        wav_path = audio_path

    # Transcribe
    print("  Transcribing with Whisper...")
    segments = transcribe_audio(wav_path)
    print(f"  Found {len(segments)} speech segments")

    # Extract announcements
    announcements = extract_announcements(segments)
    print(f"  Detected {len(announcements)} shot announcements")

    # Count by stroke type
    stroke_counts = {"forehand": 0, "backhand": 0, "serve": 0}
    for ann in announcements:
        if ann["stroke"] in stroke_counts:
            stroke_counts[ann["stroke"]] += 1

    print(f"    Forehand: {stroke_counts['forehand']}")
    print(f"    Backhand: {stroke_counts['backhand']}")
    print(f"    Serve: {stroke_counts['serve']}")

    # Save to CSV
    session_id = audio_path.stem.replace("audio_", "")
    csv_path = output_dir / f"announcements_{session_id}.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["start_ms", "end_ms", "text", "stroke"])
        writer.writeheader()
        writer.writerows(announcements)

    print(f"  Saved: {csv_path}")

    # Cleanup temp WAV
    if wav_path != audio_path:
        wav_path.unlink(missing_ok=True)

    return csv_path


def main():
    parser = argparse.ArgumentParser(description="Transcribe tennis session audio")
    parser.add_argument("audio_file", help="Path to audio file (.m4a, .wav, etc)")
    parser.add_argument("--output-dir", "-o", help="Output directory for CSV")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    transcribe_session(args.audio_file, output_dir)


if __name__ == "__main__":
    main()
