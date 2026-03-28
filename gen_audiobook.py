#!/usr/bin/env python3
"""
Generate audiobook from parsed scripts using multiple TTS providers.
Supports ElevenLabs, Kokoro (Local), Piper (Local), MLX-TTS (Local), and OpenAI.

Usage:
  python gen_audiobook.py --provider mlx          # Use local MLX-TTS (Apple Silicon)
  python gen_audiobook.py --provider kokoro       # Use local Kokoro
  python gen_audiobook.py --provider piper        # Use local Piper
  python gen_audiobook.py --provider elevenlabs   # Use ElevenLabs (default)
  python gen_audiobook.py 1                       # Single chapter
  python gen_audiobook.py 1 5                     # Range
  python gen_audiobook.py --list-voices           # List available voices
  python gen_audiobook.py --status                # Show generation status
"""
import os
import sys
import json
import io
import re
import time
import argparse
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import numpy as np
import soundfile as sf
from pydub import AudioSegment
import httpx

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

AUDIO_DIR = BASE_DIR / "audiobook"
SCRIPTS_DIR = AUDIO_DIR / "scripts"
OUTPUT_DIR = AUDIO_DIR / "chapters"
VOICES_FILE = BASE_DIR / "audiobook_voices.json"
MODELS_DIR = BASE_DIR / "models"

# --- Provider Abstraction ---

class TTSProvider(ABC):
    """Base class for Text-to-Speech providers."""
    @abstractmethod
    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        """Takes a list of {text, voice_id} and returns combined MP3/WAV bytes."""
        pass

    @property
    @abstractmethod
    def max_chars(self) -> int:
        """Maximum characters allowed per generation call."""
        pass

class ElevenLabsProvider(TTSProvider):
    """ElevenLabs TTS Provider."""
    def __init__(self, api_key: str):
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=api_key)
        self._max_chars = 4500

    @property
    def max_chars(self) -> int:
        return self._max_chars

    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        audio = self.client.text_to_dialogue.convert(inputs=segments)
        audio_bytes = b""
        for chunk in audio:
            if isinstance(chunk, bytes):
                audio_bytes += chunk
        return audio_bytes

class KokoroProvider(TTSProvider):
    """Local Kokoro TTS Provider using ONNX."""
    def __init__(self):
        from kokoro_onnx import Kokoro
        model_path = MODELS_DIR / "kokoro-v0_19.onnx"
        voices_path = MODELS_DIR / "voices.bin"
        
        if not model_path.exists() or not voices_path.exists():
            print(f"ERROR: Kokoro models not found in {MODELS_DIR}")
            print("Please download 'kokoro-v0_19.onnx' and 'voices.bin' to the models/ directory.")
            sys.exit(1)
            
        self.kokoro = Kokoro(str(model_path), str(voices_path))
        self._max_chars = 1000000

    @property
    def max_chars(self) -> int:
        return self._max_chars

    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        combined_audio = []
        sample_rate = 24000
        for seg in segments:
            samples, sr = self.kokoro.create(seg['text'], voice=seg['voice_id'], speed=1.0, lang="en-us")
            combined_audio.append(samples)
            sample_rate = sr
            combined_audio.append(np.zeros(int(sr * 0.1)))

        if not combined_audio:
            return b""
        full_audio = np.concatenate(combined_audio)
        buffer = io.BytesIO()
        sf.write(buffer, full_audio, sample_rate, format='WAV')
        buffer.seek(0)
        audio_seg = AudioSegment.from_wav(buffer)
        mp3_buffer = io.BytesIO()
        audio_seg.export(mp3_buffer, format="mp3", bitrate="192k")
        return mp3_buffer.getvalue()

class PiperProvider(TTSProvider):
    """Local Piper TTS Provider."""
    def __init__(self):
        from piper import PiperVoice
        self.PiperVoice = PiperVoice
        self._max_chars = 5000
        self.voices_cache = {}

    @property
    def max_chars(self) -> int:
        return self._max_chars

    def _get_voice(self, voice_id: str):
        if voice_id not in self.voices_cache:
            model_path = MODELS_DIR / f"{voice_id}.onnx"
            config_path = MODELS_DIR / f"{voice_id}.onnx.json"
            if not model_path.exists():
                voice_id = "en_US-lessac-medium"
                model_path = MODELS_DIR / f"{voice_id}.onnx"
                config_path = MODELS_DIR / f"{voice_id}.onnx.json"
            
            if not model_path.exists():
                print(f"ERROR: Piper model {voice_id} not found in {MODELS_DIR}")
                return None
            self.voices_cache[voice_id] = self.PiperVoice.load(str(model_path), str(config_path))
        return self.voices_cache[voice_id]

    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        combined = AudioSegment.empty()
        for seg in segments:
            voice = self._get_voice(seg['voice_id'])
            if not voice: continue
            
            buffer = io.BytesIO()
            import wave
            with wave.open(buffer, "wb") as wav_file:
                voice.synthesize_wav(seg['text'], wav_file)
            
            buffer.seek(0)
            part = AudioSegment.from_wav(buffer)
            combined += part
            combined += AudioSegment.silent(duration=100)
            
        mp3_buffer = io.BytesIO()
        combined.export(mp3_buffer, format="mp3", bitrate="192k")
        return mp3_buffer.getvalue()

class MLXTTSProvider(TTSProvider):
    """Local MLX-TTS Provider for Apple Silicon."""
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._max_chars = 10000

    @property
    def max_chars(self) -> int:
        return self._max_chars

    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        combined = AudioSegment.empty()
        with httpx.Client(timeout=300.0) as client:
            for seg in segments:
                response = client.post(
                    f"{self.base_url}/v1/audio/speech",
                    json={
                        "model": "mlx-community/Kokoro-82M",
                        "input": seg['text'],
                        "voice": seg['voice_id'],
                        "speed": 1.0
                    }
                )
                if response.status_code == 200:
                    part = AudioSegment.from_file(io.BytesIO(response.content))
                    combined += part
                    combined += AudioSegment.silent(duration=100)
            
        mp3_buffer = io.BytesIO()
        combined.export(mp3_buffer, format="mp3", bitrate="192k")
        return mp3_buffer.getvalue()

class OpenAITTSProvider(TTSProvider):
    """OpenAI Cloud TTS Provider."""
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self._max_chars = 4000

    @property
    def max_chars(self) -> int:
        return self._max_chars

    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        combined = AudioSegment.empty()
        for seg in segments:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=seg['voice_id'],
                input=seg['text']
            )
            part = AudioSegment.from_file(io.BytesIO(response.content), format="mp3")
            combined += part
            combined += AudioSegment.silent(duration=200)
        mp3_buffer = io.BytesIO()
        combined.export(mp3_buffer, format="mp3", bitrate="192k")
        return mp3_buffer.getvalue()

def get_provider(name: str) -> TTSProvider:
    """Initialize selected TTS provider."""
    name = name.lower()
    if name == "elevenlabs":
        key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not key:
            print("ERROR: ELEVENLABS_API_KEY not set in .env", file=sys.stderr)
            sys.exit(1)
        return ElevenLabsProvider(key)
    elif name == "kokoro":
        return KokoroProvider()
    elif name == "piper":
        return PiperProvider()
    elif name == "mlx":
        url = os.environ.get("MLX_TTS_SERVER_URL", "http://localhost:8000")
        return MLXTTSProvider(url)
    elif name == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            print("ERROR: OPENAI_API_KEY not set in .env", file=sys.stderr)
            sys.exit(1)
        return OpenAITTSProvider(key)
    else:
        print(f"ERROR: Unknown provider {name}")
        sys.exit(1)

def load_voices(provider_name: str):
    """Load voice mapping from audiobook_voices.json for specific provider."""
    if not VOICES_FILE.exists():
        print(f"ERROR: {VOICES_FILE} not found. Create it first.", file=sys.stderr)
        sys.exit(1)
    data = json.loads(VOICES_FILE.read_text())
    voices = {}
    for name, info in data.items():
        if name.startswith("_"):
            continue
        prov_data = info.get("providers", {})
        vid = prov_data.get(provider_name)
        if vid and vid != "REPLACE_WITH_VOICE_ID":
            voices[name] = vid
    return voices

def load_script(ch_num):
    """Load a chapter's parsed script."""
    path = SCRIPTS_DIR / f"ch{ch_num:02d}_script.json"
    if not path.exists():
        print(f"  Script not found: {path}. Run gen_audiobook_script.py first.", file=sys.stderr)
        return None
    return json.loads(path.read_text())

def chunk_segments(segments, voices, max_chars):
    """Split segments into chunks that fit within the provider character limit."""
    chunks = []
    current_chunk = []
    current_chars = 0
    fallback_voice = list(voices.values())[0] if voices else None
    for seg in segments:
        speaker = seg["speaker"]
        text = seg["text"]
        voice_id = voices.get(speaker, voices.get("MINOR", voices.get("NARRATOR", fallback_voice)))
        if not voice_id: continue
        clean_text = re.sub(r'\[.*?\]', '', text).strip()
        if not clean_text: continue
        seg_chars = len(text)
        if seg_chars > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sub_chunk = []
            sub_chars = 0
            for sent in sentences:
                if sub_chars + len(sent) > max_chars and sub_chunk:
                    chunks.append([{"text": " ".join(sub_chunk), "voice_id": voice_id}])
                    sub_chunk = []
                    sub_chars = 0
                sub_chunk.append(sent)
                sub_chars += len(sent) + 1
            if sub_chunk:
                chunks.append([{"text": " ".join(sub_chunk), "voice_id": voice_id}])
            continue
        if current_chars + seg_chars > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0
        current_chunk.append({"text": text, "voice_id": voice_id})
        current_chars += seg_chars
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def generate_chapter(ch_num, provider, voices, test_mode=False):
    """Generate audio for a single chapter."""
    script = load_script(ch_num)
    if not script: return None
    title = script.get("title", f"Chapter {ch_num}")
    segments = script["segments"]
    if test_mode: 
        segments = segments[:5]
        print(f"  TEST MODE: using first 5 segments only")
    chunks = chunk_segments(segments, voices, provider.max_chars)
    total_chunks = len(chunks)
    print(f"  Ch {ch_num}: '{title}' → {len(segments)} segments → {total_chunks} chunks")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_parts = []
    failed_chunks = []
    
    for i, chunk in enumerate(chunks, 1):
        chars = sum(len(s['text']) for s in chunk)
        print(f"    [{i}/{total_chunks}] {chars} chars, {len(chunk)} segments...", end="", flush=True)
        audio_bytes = None
        last_error = None
        for attempt in range(1, 4):
            try:
                audio_bytes = provider.generate(chunk)
                if audio_bytes: break
            except Exception as e:
                last_error = str(e)
                if attempt < 3: time.sleep(attempt * 5)
        if audio_bytes:
            audio_parts.append(audio_bytes)
            print(f" ✓ ({len(audio_bytes):,} bytes)")
        else:
            failed_chunks.append(i)
            print(f" ✗ FAILED: {last_error}")

    if not audio_parts: return None
    
    if failed_chunks:
        manifest = {
            "chapter": ch_num,
            "total_chunks": total_chunks,
            "succeeded": [i for i in range(1, total_chunks+1) if i not in failed_chunks],
            "failed": failed_chunks,
            "complete": False,
        }
        manifest_path = OUTPUT_DIR / f"ch_{ch_num:02d}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

    combined = AudioSegment.empty()
    for part_bytes in audio_parts:
        try:
            part = AudioSegment.from_file(io.BytesIO(part_bytes))
            combined += part
        except Exception as e:
            print(f"  Error processing chunk: {e}")
    
    suffix = f"_test_{provider.__class__.__name__.lower().replace('provider', '')}" if test_mode else ""
    out_path = OUTPUT_DIR / f"ch_{ch_num:02d}{suffix}.mp3"
    combined.export(out_path, format="mp3", bitrate="192k")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  Saved: {out_path} ({size_mb:.1f} MB)")
    return str(out_path)

def list_voices(provider):
    """List available voices for the current provider."""
    print(f"\n{'='*60}")
    print(f"AVAILABLE VOICES FOR {provider.__class__.__name__.replace('Provider', '').upper()}")
    print(f"{'='*60}")
    
    if isinstance(provider, ElevenLabsProvider):
        response = provider.client.voices.get_all()
        for voice in response.voices:
            labels = voice.labels or {}
            print(f"\n  {voice.name}")
            print(f"    ID: {voice.voice_id}")
            print(f"    {labels.get('gender', '')} | {labels.get('age', '')} | {labels.get('accent', '')}")
    else:
        # For other providers, we just show what's in our mapping
        voices = load_voices(args.provider)
        for name, vid in voices.items():
            print(f"  {name}: {vid}")

def assemble_full_audiobook():
    """Concatenate all chapter audio files into one."""
    chapter_files = sorted(OUTPUT_DIR.glob("ch_*.mp3"))
    chapter_files = [f for f in chapter_files if "_test" not in f.name]
    if not chapter_files: return
    print(f"\nAssembling {len(chapter_files)} chapters into full audiobook...")
    combined = AudioSegment.empty()
    for f in chapter_files:
        part = AudioSegment.from_file(f)
        combined += part
        combined += AudioSegment.silent(duration=1000)
    out = AUDIO_DIR / "full_audiobook.mp3"
    combined.export(out, format="mp3", bitrate="192k")
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"  Full audiobook: {out} ({size_mb:.1f} MB)")

def main():
    parser = argparse.ArgumentParser(description="Generate audiobook from parsed scripts")
    parser.add_argument("start", nargs="?", type=int, help="Start chapter")
    parser.add_argument("end", nargs="?", type=int, help="End chapter")
    parser.add_argument("--provider", default="elevenlabs", choices=["elevenlabs", "kokoro", "piper", "mlx", "openai"], help="TTS provider")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument("--test", type=int, metavar="CH", help="Test mode")
    parser.add_argument("--assemble", action="store_true", help="Assemble full audiobook from chapters")
    parser.add_argument("--status", action="store_true", help="Show generation status")
    
    args = parser.parse_args()
    provider = get_provider(args.provider)

    if args.list_voices:
        list_voices(provider)
        return

    if args.assemble:
        assemble_full_audiobook()
        return

    if args.status:
        print(f"\n{'='*50}")
        print("AUDIOBOOK GENERATION STATUS")
        print(f"{'='*50}")
        scripts = sorted(SCRIPTS_DIR.glob("ch*_script.json"))
        for script_f in scripts:
            ch_num = int(script_f.stem.replace("_script", "").replace("ch", ""))
            audio_f = OUTPUT_DIR / f"ch_{ch_num:02d}.mp3"
            manifest_f = OUTPUT_DIR / f"ch_{ch_num:02d}_manifest.json"
            if audio_f.exists():
                size_mb = audio_f.stat().st_size / (1024*1024)
                if manifest_f.exists():
                    m = json.loads(manifest_f.read_text())
                    if m.get("failed"):
                        print(f"  Ch {ch_num:2d}: ⚠ PARTIAL ({size_mb:.1f} MB, chunks {m['failed']} failed)")
                    else:
                        print(f"  Ch {ch_num:2d}: ✓ complete ({size_mb:.1f} MB)")
                else:
                    print(f"  Ch {ch_num:2d}: ✓ ({size_mb:.1f} MB)")
            else:
                print(f"  Ch {ch_num:2d}: ✗ not generated")
        return

    voices = load_voices(args.provider)
    if not voices:
        print(f"ERROR: No voices configured for provider '{args.provider}' in audiobook_voices.json")
        sys.exit(1)

    if args.test:
        generate_chapter(args.test, provider, voices, test_mode=True)
        return

    scripts = sorted(SCRIPTS_DIR.glob("ch*_script.json"))
    total = len(scripts)
    start = args.start or 1
    end = args.end or total

    print(f"Generating audiobook using {args.provider}: chapters {start}-{end}")
    for ch_num in range(start, end + 1):
        generate_chapter(ch_num, provider, voices)
        print()

    assemble_full_audiobook()

if __name__ == "__main__":
    main()
