# Zuki 🧤

**Zuki for Windows — open source. Talk to your PC — she sees your screen, points at things, and actually does them.**

🎬 **Demo & write-up:** [raynanwuyep.com/clacky](https://raynanwuyep.com/clacky) · ⬇ **[Download for Windows](https://github.com/<your-username>/zuki/releases/latest)**

Zuki is a voice-first desktop companion for Windows. Hold a hotkey, talk, and she:

- **sees** your screen and answers questions about it,
- **points** — a little buddy flies to whatever you're asking about (snaps to the real UI element, pixel-accurate),
- **acts** — opens apps, clicks, types, runs multi-step tasks, using Claude Computer Use,
- **remembers** you across sessions and **learns routines** you teach her by voice,
- **tours** an app — "explain my screen" gives you a spoken, pointing walkthrough.

Her brain is **Claude** (Sonnet 5 + Computer Use); voice via **Deepgram** streaming STT and free **Edge TTS**.

### Where this fits

|                        | macOS                      | Windows                       |
|------------------------|----------------------------|-------------------------------|
| **Closed (heyclicky)** | agent mode shipped         | waitlist only                 |
| **Open source**        | OpenClicky has agent mode  | **empty — Zuki fills this** |

Clicky is Mac-only. Zuki brings the same idea to the majority of desktops that can't run it — open and free.

> ⚠️ **Early build, and honestly a bit rough.** The core loop — talk → see → point → act — works and is genuinely fun. But speech recognition isn't perfect, and the more advanced features (multi-step tasks, Gmail/Calendar, background research) are lightly tested. This is a "try it and tell me what breaks" release, not a finished product.

---

## What works today

**The voice companion — `zuki run`:**

- Push-to-talk voice; an on-screen buddy that points at what you ask about.
- *"What's on my screen?"* → a spoken answer, buddy points at the relevant thing.
- *"Explain my screen"* / *"walk me through this"* → a teaching tour that points out several things, one at a time.
- *"Open Notepad and type hello"*, *"click the Save button"*, *"go to YouTube"* → she acts on your machine.
- *"Remember I prefer dark mode"*, *"save this as my morning routine"* → cross-session memory + learned routines.
- *"Check my email"*, *"what's on my calendar"* → opens your logged-in web apps (or an opt-in Google API).
- *"Go research X and tell me later"* → a background agent works while you keep talking — and **leaves you real files**, not just words (via an embedded [hermes-agent](https://github.com/nousresearch/hermes-agent) harness, on your same Claude key). Background agents can also use **any MCP server you connect** — `zuki connect notion` or `zuki connect composio` is a browser approve, and Composio alone brings **1000+ apps** — so tasks can end in your Notion, Sheets, or Slack, not just on disk. She opens what she delivers, and never claims a delivery she didn't make.
- *"Save this as game time — open Steam and Elden Ring tutorials"* → skills are **SKILL.md files** ([agentskills.io](https://agentskills.io) standard) — editable, shareable, PR-able, and shared by both her foreground and background brains.

**The file organizer — `zuki organize`:**

- Tidies a folder from one LLM call; move-only and **fully reversible** with `zuki undo`.

## Getting started (Windows 10/11)

Create a **free Zuki account** — the app walks you through it on first launch.
That account is what powers her Claude brain: requests go through the Zuki
server, which holds the key. A **Deepgram key** is recommended for fast,
accurate voice (free tier; without it she falls back to slower local Whisper).

### Option 1 — Download the app *(no Python needed)*

1. Grab **`Zuki-v0.2.0-windows.zip`** from [**Releases**](https://github.com/<your-username>/zuki/releases/latest)
2. Extract anywhere and run `Zuki.exe`
   *(the exe is unsigned, so SmartScreen may warn on first run — "More info → Run anyway")*
3. Sign in or create your free account — that's it, she's ready
4. **Hold `Ctrl+Alt+M`, say *"what's on my screen?"*, and release** 🧤

### Option 2 — Run from source *(Python 3.11+)*

```powershell
git clone https://github.com/<your-username>/zuki.git
cd zuki
pip install -e ".[shell,claude]"
zuki run
```

Background agents — the ones that leave you files — are included by default.
(One caveat: Hermes doesn't support Python 3.14 yet, so on 3.14 she falls
back to spoken summaries until it does.)

Same flow: sign in / create an account on first launch. For dev builds you can
instead point the client at the bundled account server
(`uvicorn server.main:app --port 8787`, with `ANTHROPIC_API_KEY` in the
server's environment — never in the client), or set
`ZUKI_REQUIRE_ACCOUNT=0` and use a local key:

```
ZUKI_SERVER_URL=http://127.0.0.1:8787   # the Zuki account server
DEEPGRAM_API_KEY=...                       # recommended — fast voice
ZUKI_ACTIVE_LLM=claude
```

Full setup, what to say, and troubleshooting: **[docs/USAGE.md](docs/USAGE.md)**.

### Just want the file organizer? (no voice, no keys)

```powershell
pip install -e .
zuki organize ~/Desktop -p heuristic --dry-run   # preview, zero config
zuki organize ~/Desktop                           # do it
zuki undo                                          # reverse it
```

## A note on safety

The **file organizer** is move-only and fully reversible (`zuki undo`). The **voice agent acts directly** — like Clicky, she does what you ask rather than nagging for permission — but she stops and hands back before genuinely irreversible, high-stakes actions (send, delete, buy). It's an early build acting on your real machine, so **watch her, and press `Esc` to stop at any time.**

## Roadmap

- ~~Learnable skills (SKILL.md)~~ — **shipped in v0.2**: skills use the same open [Agent Skills standard](https://agentskills.io) as Claude, Hermes, and OpenClaw — with Zuki's twist: you teach her by *voice*.
- ~~Background agents that leave artifacts~~ — **shipped in v0.2**: "go research X" runs through an embedded [hermes-agent](https://github.com/nousresearch/hermes-agent) harness and hands you real files.
- **Zuki Bridge (MCP)** — exposing her eyes and pointer as an MCP server, so *any* agent (Claude, OpenClaw, Hermes) can see and point at a Windows screen.
- **Better desktop control** — opt-in shortcut/icon arrangement, more launcher coverage.

Issues and PRs very welcome — **contributing a skill is a 5-minute PR** (see [CONTRIBUTING.md](CONTRIBUTING.md)). 🧤

## Layout

```
zuki/
  shell/        # the voice + screen companion (zuki run) — the main app
    routing.py  #   intent routing: local fast-paths + Haiku router
    tour.py     #   guided screen tour + pointing (inline [POINT] tags)
    actions.py  #   computer-use agent, launchers, organizer, background agents
  agent/        # computer-use actuation, permission model, safe file ops + undo
  providers/    # Claude / OpenAI / Gemini / Ollama / heuristic, behind one interface
  cli.py        # zuki organize / undo / run
server/         # Zuki account server: Firebase auth + Claude proxy + quotas + admin page
docs/           # USAGE.md (start here), plus design docs
tests/          # headless tests with a fake provider
packaging/      # PyInstaller entry (zuki.spec builds the .exe)
organizer/      # early file-organizer prototype — superseded by zuki/, kept for its tests
```

## Credits & license

Zuki is an independent project. It builds on ideas and open-source work from:

- **Clicky** by [@farzaa](https://github.com/farzaa/clicky) — the original macOS screen-companion concept (MIT).
- **Clicky for Windows** by [Bitshank-2338 / Shashank Singh](https://github.com/Bitshank-2338/clicky-windows) — the Python/PyQt6 Windows companion Zuki lifts its voice + pointing pipeline from (MIT).
- **OpenClicky** by [@jasonkneen](https://github.com/jasonkneen/openclicky) — the actively maintained open-source Clicky with Agent Mode; design reference for how agent capabilities are structured (MIT, macOS/Swift).
- **Clacky** by [@Raynan00](https://github.com/Raynan00/clacky) — the Windows companion Zuki forks; its shell, account server, and agent layer originate there (MIT).

Zuki is released under the [MIT License](LICENSE). It is not affiliated with or endorsed by the above projects or Anthropic.
