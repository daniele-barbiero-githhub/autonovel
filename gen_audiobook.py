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
    @abstractmethod
    def generate(self, segments: List[Dict[str, str]]) -> bytes:
        """Takes a list of {text, voice_id} and returns combined MP3/WAV bytes."""
        pass

    @property
    @abstractmethod
    def max_chars(self) -> int:
        pass

class ElevenLabsProvider(TTSProvider):
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
    def __init__(self):
        from kokoro_onnx import Kokoro
        model_path = MODELS_DIR / "kokoro-v0_19.onnx"
        voices_path = MODELS_DIR / "voices.bin"
        
        if not model_path.exists() or not voices_path.exists():
            print(f"ERROR: Kokoro models not found in {MODELS_DIR}")
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
            # Piper needs a real file-like object that supports seek/tell for WAV
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
    name = name.lower()
    if name == "elevenlabs":
        key = os.environ.get("ELEVENLABS_API_KEY", "")
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
        return OpenAITTSProvider(key)
    else:
        print(f"ERROR: Unknown provider {name}")
        sys.exit(1)

def load_voices(provider_name: str):
    if not VOICES_FILE.exists(): return {}
    data = json.loads(VOICES_FILE.read_text())
    voices = {}
    for name, info in data.items():
        if name.startswith("_"): continue
        prov_data = info.get("providers", {})
        vid = prov_data.get(provider_name)
        if vid and vid != "REPLACE_WITH_VOICE_ID":
            voices[name] = vid
    return voices

def load_script(ch_num):
    path = SCRIPTS_DIR / f"ch{ch_num:02d}_script.json"
    if not path.exists(): return None
    return json.loads(path.read_text())

def chunk_segments(segments, voices, max_chars):
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
    script = load_script(ch_num)
    if not script: return None
    title = script.get("title", f"Chapter {ch_num}")
    segments = script["segments"]
    if test_mode: segments = segments[:5]
    chunks = chunk_segments(segments, voices, provider.max_chars)
    total_chunks = len(chunks)
    print(f"  Ch {ch_num}: '{title}' → {len(segments)} segments → {total_chunks} chunks")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_parts = []
    for i, chunk in enumerate(chunks, 1):
        chars = sum(len(s['text']) for s in chunk)
        print(f"    [{i}/{total_chunks}] {chars} chars, {len(chunk)} segments...", end="", flush=True)
        audio_bytes = None
        for attempt in range(1, 4):
            try:
                audio_bytes = provider.generate(chunk)
                if audio_bytes: break
            except Exception as e:
                if attempt < 3: time.sleep(attempt * 5)
        if audio_bytes:
            audio_parts.append(audio_bytes)
            print(f" ✓ ({len(audio_bytes):,} bytes)")
        else:
            print(f" ✗ FAILED")

    if not audio_parts: return None
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

def assemble_full_audiobook():
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
    parser.add_argument("--test", type=int, metavar="CH", help="Test mode")
    parser.add_argument("--assemble", action="store_true", help="Assemble")
    parser.add_argument("--status", action="store_true", help="Status")
    args = parser.parse_args()
    provider = get_provider(args.provider)
    voices = load_voices(args.provider)
    if not voices:
        print(f"ERROR: No voices configured for provider '{args.provider}'")
        sys.exit(1)
    if args.assemble:
        assemble_full_audiobook()
        return
    if args.status:
        scripts = sorted(SCRIPTS_DIR.glob("ch*_script.json"))
        for script_f in scripts:
            ch_num = int(script_f.stem.replace("_script", "").replace("ch", ""))
            audio_f = OUTPUT_DIR / f"ch_{ch_num:02d}.mp3"
            print(f"  Ch {ch_num:02d}: {'✓' if audio_f.exists() else '✗'}")
        return
    if args.test:
        generate_chapter(args.test, provider, voices, test_mode=True)
        return
    scripts = sorted(SCRIPTS_DIR.glob("ch*_script.json"))
    total = len(scripts)
    start = args.start or 1
    end = args.end or total
    for ch_num in range(start, end + 1):
        generate_chapter(ch_num, provider, voices)
    assemble_full_audiobook()

if __name__ == "__main__":
    main()
