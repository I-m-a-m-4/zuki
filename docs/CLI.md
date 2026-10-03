# Zuki CLI — quickstart

Zuki v0.1 is a command-line tool that tidies a folder: it asks an LLM (or a
no-AI heuristic) for a plan, then moves your files into sensible subfolders.
It runs autonomously, and **everything is undoable**.

No Claude Code, no agent SDK — Zuki calls LLM providers directly, or runs
fully offline.

## Install

```bash
cd Zuki
pip install -e .                # base install (heuristic + Ollama work now)
# add a cloud provider if you want smarter sorting:
pip install -e ".[claude]"      # or .[openai] / .[gemini]
```

## Pick how it thinks

| Provider | Setup | Notes |
|---|---|---|
| `heuristic` | nothing | No AI. Sorts by file type. Always works, zero config. |
| `ollama` | install [Ollama](https://ollama.ai) + `ollama pull llama3.1` | Free, local, private. |
| `claude` | `ANTHROPIC_API_KEY` | Best quality (recommended for real use). |
| `openai` | `OPENAI_API_KEY` | |
| `gemini` | `GOOGLE_API_KEY` | |

Put keys in a `.env` (see `.env.example`) or your environment. With a key set,
Zuki auto-selects that provider; otherwise it defaults to Ollama. Override per
run with `-p`.

## Use

```bash
# Preview only — moves nothing:
zuki organize ~/Desktop --dry-run

# Preview with the zero-config sorter (no key, no model):
zuki organize ~/Desktop -p heuristic --dry-run

# Do it (autonomous, but reversible):
zuki organize ~/Desktop

# Changed your mind:
zuki undo
```

Flags: `-n/--dry-run`, `-p/--provider NAME`, `-m/--model NAME`.

## What it will and won't touch

- Only files **directly inside** the target folder (never reaches into existing
  subfolders).
- **Move-only, never delete.** Name collisions get ` (1)`, ` (2)` suffixes.
- Skips anything **sensitive** (passwords, keys, `.env`) and protected/system
  file types.
- Refuses any target **outside your home folder**.

## Undo

Every organize writes a batch to `~/.zuki/history/`. `zuki undo` reverses the
most recent one and survives restarts.
