# Multi-Provider Text-to-Speech (TTS) Strategy

## Goal
Support multiple TTS providers, including high-quality local options (Kokoro, WhisperSpeech, MLX-TTS) and cloud options (ElevenLabs, OpenAI), while leveraging local GPU acceleration (CUDA for Linux/Windows, MPS/MLX for macOS).

## Requirements
- **Provider Abstraction**: A unified interface to switch between different TTS backends.
- **Local GPU Support**: Optimize local providers for NVIDIA GPUs (CUDA) and Apple Silicon (MLX/MPS).
- **Voice Mapping**: Centralized mapping of character names to provider-specific voice IDs or model configurations.
- **Fallbacks**: Ability to define fallback providers or voices if a specific one is unavailable.

## Supported Providers

### 1. ElevenLabs (Cloud)
- **Status**: Existing implementation.
- **Pros**: Highest quality, extensive voice library.
- **Cons**: Costly, requires internet.

### 2. Kokoro (Local - GPU Optimized)
- **Library**: `kokoro-onnx` with `onnxruntime` (MPS support on Mac).
- **Pros**: Very fast, high quality, lightweight models.
- **Cons**: Fixed set of voices.

### 3. WhisperSpeech (Local - GPU Optimized)
- **Library**: `whisperspeech`.
- **Pros**: Excellent for local GPU use, "inverted Whisper" architecture.
- **Cons**: Higher VRAM requirements than Kokoro.

### 4. MLX-TTS (Local - Apple Silicon Native)
- **Library**: `mlx-tts-server` (or `mlx-audio`).
- **Pros**: Native Apple Silicon performance using the MLX framework, OpenAI-compatible API.
- **Cons**: Mac-only, requires a running server.

### 5. OpenAI TTS (Cloud)
- **Library**: `openai` Python SDK.
- **Pros**: High quality, standardized API.
- **Cons**: Requires internet, cost.

## Integration Plan
1.  **`TTSProvider` Base Class**: Define `generate(text, voice_id) -> bytes`.
2.  **`MLXTTSProvider`**: Implement using `httpx` to call the local MLX server.
3.  **Factory Pattern**: A `get_provider(name)` function to instantiate the selected backend.
4.  **Updated `audiobook_voices.json`**: Structure to support `mlx` voice mappings.

## Success Criteria
- [x] Implement `TTSProvider` abstraction in `gen_audiobook.py`.
- [x] Add `KokoroProvider`.
- [x] Add `WhisperSpeechProvider`.
- [ ] Add `MLXTTSProvider`.
- [x] Verify that the system can switch between providers via configuration.
