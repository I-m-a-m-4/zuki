# Zuki for Windows — Setup Guide

## Prerequisites

- Python 3.11+
- Ollama installed (https://ollama.com) — for student/free mode
- `llama3.2-vision` model pulled: `ollama pull llama3.2-vision`

## Install

```bash
cd zuki/shell

# Student version (free, no API keys needed)
pip install -r requirements-student.txt

# Full version (all providers)
pip install -r requirements.txt
```

> **PyAudio on Windows** may need: `pip install pipwin && pipwin install pyaudio`

## Configure

**Sign in is the setup.** On first launch the app asks for a Zuki account —
sign in or create one (free). Claude requests run through the Zuki account
server, which holds the key; nothing sensitive lives in this client. Reopen it
any time from `Tray → Sign in / Create account…`.

Dev / self-host builds can instead use their own keys:

```bash
copy .env.example .env
# Edit .env and add any API keys you have
# Dev only: ANTHROPIC_API_KEY works when ZUKI_REQUIRE_ACCOUNT=0
# Everything is optional — Ollama is the free fallback
```

## Run

```bash
python main.py
```

A floating panel appears in the bottom-right corner.
The Zuki icon appears in your system tray.

**Hold `Ctrl+Alt+M`** to speak. Release to send.

## Provider Priority (auto-detected)

| Priority | LLM | STT | TTS |
|----------|-----|-----|-----|
| 1st | Claude — Zuki account (or `ANTHROPIC_API_KEY`, dev) | Deepgram (DEEPGRAM_API_KEY) | ElevenLabs (ELEVENLABS_API_KEY) |
| 2nd | OpenAI (OPENAI_API_KEY) | OpenAI Whisper (OPENAI_API_KEY) | OpenAI TTS (OPENAI_API_KEY) |
| Free | Ollama (local) | faster-whisper (local) | edge-tts (free, no key) |

## Phases Remaining

- [ ] Phase 4: Cursor overlay pointing animation (UI complete, coordinate mapping pending)
- [ ] Phase 5: Web search grounding (Tavily/DuckDuckGo wired in, needs testing)
- [ ] Phase 6: PyInstaller .exe packaging + installer
