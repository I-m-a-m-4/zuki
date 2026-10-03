# Using Zuki (the voice companion)

This is the practical guide to `zuki run` — setup, what to say, and how to get
out of trouble. For the file organizer, see [CLI.md](CLI.md).

> Zuki is Windows-only and an early build. The core loop works; expect rough
> edges, especially in speech recognition.

---

## 1. Install

Requires **Windows 10/11** and **Python 3.11+**.

```powershell
git clone <your-repo-url> zuki
cd zuki
pip install -e ".[shell,claude]"
```

This pulls the shell dependencies (PyQt6, sounddevice, mss, uiautomation, edge-tts,
faster-whisper, …) and the Anthropic SDK. First launch may download a small local
Whisper model for the wake word.

## 2. Keys

Zuki needs an **Anthropic API key** (for seeing / pointing / acting) and works
much better with a **Deepgram key** (fast, accurate speech-to-text).

Copy `.env.example` → `zuki/shell/.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...
DEEPGRAM_API_KEY=...
ZUKI_ACTIVE_LLM=claude
ZUKI_HOTKEY=ctrl+alt+m
```

Get keys: [console.anthropic.com](https://console.anthropic.com) ·
[console.deepgram.com](https://console.deepgram.com) (free tier is plenty).
On first run, a setup wizard collects these for you — plus an optional
[Composio](https://composio.dev) browser sign-in that gives background
agents 1000+ connected apps (you can always do it later; Zuki offers it
the first time a task needs an app).

## 3. Run

```powershell
zuki run
```

A small buddy appears near your cursor and Zuki sits in the system tray.

- **Push-to-talk:** hold **`Ctrl+Alt+M`**, speak, then **release**. (Hold the whole
  time you're talking — it's not tap-to-toggle.)
- **Wake word:** you can also just say **"hey Zuki"** without the hotkey.
- **Stop it talking / acting:** press **`Esc`**, or hold the hotkey again to barge in.
- **Quit:** use the **tray icon → Quit** (see troubleshooting for why this matters).

## 4. What to say

**Ask about the screen**
- "What's on my screen?"  ·  "What does this button do?"  ·  "Where's the settings icon?"

**Get a tour (it points at several things)**
- "Explain my screen."  ·  "Walk me through this."  ·  "What can I do here?"

**Make it act** (it does it directly — watch it)
- "Open Notepad and type hello world."  ·  "Click the Save button."  ·  "Go to youtube."
- **Force the "do it" mode:** start with **"go…"**, **"agent…"**, **"do it"**, **"take over…"**, or **"Zuki, go…"** — e.g. *"go open Chrome and search for lofi."* Normally Zuki guesses whether you're asking a question or giving a command; a trigger word removes the guess and guarantees it acts (great when a phrase could read either way, and for reliable demos).

**Memory & routines** (persist across restarts)
- "Remember I prefer dark mode."  ·  "What do you know about me?"
- "Save this as my morning routine: open gmail then open slack."  ·  "Do my morning routine."

**Email / calendar** (opens your logged-in web apps)
- "Check my email."  ·  "What's on my calendar today?"

**Background agents** (work while you keep talking — and leave you files)
- "Go research the best budget laptops and tell me later." → she reports back
  during a lull and opens a folder with a written report.
- "Go research **this** and tell me later" works too — she looks at your
  screen when you ask, so the background agent knows what "this" is.
- Powered by an embedded [hermes-agent](https://github.com/nousresearch/hermes-agent)
  harness running on your same Anthropic key. **Included by default** in the
  source install (except on Python 3.14, which Hermes doesn't support yet).
  `.exe` users: install Hermes once
  (`pip install hermes-agent ddgs agent-client-protocol` with any Python
  3.11–3.13, or Nous's installer) —
  Zuki finds it on PATH automatically, no config. Without it, background
  tasks fall back to a spoken web-research summary — and Zuki will tell you
  once, at the moment it would have helped, how to upgrade.
  Artifacts land in `~/.zuki/background/`.

**Connect your apps to background agents (MCP)**
Background tasks can use any [MCP](https://modelcontextprotocol.io) server.
The easiest way is to just ask: say *"go research X and put it in my Notion"*
and if Notion isn't connected yet, Zuki pops a small window — hit
**Connect**, approve in the browser that opens, and the task carries on with
real delivery. No tokens to hunt down (it's the same OAuth flow Claude Code
uses; Zuki renews the tokens herself). Skip instead, and she leaves you
files. Never a gate.

Apps with official hosted servers (Notion, Linear, Sentry, GitHub, Hugging
Face) need zero typing — Zuki knows their URLs. And for the entire long
tail, connect [Composio](https://composio.dev) once — a browser sign-in,
same as everything else (an API key from
[dashboard.composio.dev](https://dashboard.composio.dev) also works) — and
she can reach **1000+ apps**. The first time a task touches an app you
haven't authorized yet, Zuki opens the approval in your browser — click
Approve and she finishes the delivery herself. Every later ask is fully
hands-free.

You can also connect ahead of time:

```powershell
zuki connect notion     # opens your browser to approve — that's the whole flow
zuki connect composio   # same browser approve — unlocks 1000+ apps at once
zuki connect            # or interactive: name + URL/command (+ token if needed)
```

Or hand-edit the harness config yourself — `zuki connect` prints its
location (Windows: `%LOCALAPPDATA%\hermes\config.yaml`); Zuki's background
lane picks it up either way:

```yaml
mcp_servers:
  fetch:                       # example: a local stdio server
    command: python
    args: ["-m", "mcp_server_fetch"]
  composio:                    # example: hosted servers (Notion, Sheets, Slack, …)
    url: https://mcp.composio.dev/<your-server>   # from your Composio dashboard
    headers: { Authorization: "Bearer <token>" }
```

With something like [Composio](https://composio.dev) connected, *"go research X
and put it in my Notion"* completes end-to-end — research **and** delivery.
Foreground stays local-first (your screen, your sessions); connected tools are
strictly opt-in for the background lane.

**Skills** (teach her once, she keeps it — the [agentskills.io](https://agentskills.io) standard)
- "Save this as game time — open Steam and Elden Ring tutorials." → writes
  `~/.zuki/skills/game-time/SKILL.md`. Edit it in any editor, drop in skills
  from the community, or PR yours to the repo. Both her foreground agent and
  background harness use the same skills.

## 5. Troubleshooting

**It triggers but nothing records / "0 bytes captured."**
Almost always a stuck mic from a previous run. Quit via the **tray**, not `Ctrl+C`
(Ctrl+C can leave a `python.exe` holding the microphone). If it happens:
```powershell
taskkill /F /IM python.exe
```
Then relaunch. Also check **Settings → System → Sound → Input** has the right mic.

**The hotkey does nothing / a blinking bar appears.**
Another app owns `Ctrl+Alt+M` (Claude Desktop, screen tools, etc.). Change
`ZUKI_HOTKEY` in `zuki/shell/.env` to something free, e.g. `ctrl+alt+c`.

**Speech recognition mishears me.**
This is the known weak spot. A Deepgram key helps a lot vs. local Whisper. Speak a
beat after pressing the key, and hold until you've finished. The wake word ("hey
Zuki") is a coined word, so it's less reliable than push-to-talk — prefer the hotkey.

**It points slightly off.**
The buddy snaps to real UI elements via Windows accessibility, but on some apps
(canvas/games) the tree is sparse and it falls back to the model's estimate. Menus,
buttons, and standard controls are accurate.

**It won't use my Claude features.**
The acting, tours, memory, and routing all require `ANTHROPIC_API_KEY`. On the free
Ollama path, Zuki can still see, talk, and point, but not act.

**"Windows can't find <app>" when she tries to open something.**
Some apps (Steam-likes, Store installs) aren't resolvable by name. Teach her where
yours live — create `~/.zuki/apps.json`:
```json
{ "steam": ["D:\\Games\\Steam\\steam.exe", "steam://open/main"],
  "my tool": "mytool://" }
```
Candidates are tried in order (exe paths, then URL protocols); your entries
override the built-ins.

## Tuning (env vars)

| Variable | Default | What it does |
|---|---|---|
| `ZUKI_HOTKEY` | `ctrl+alt+m` | Push-to-talk combo |
| `ZUKI_WAKE_WORD` | `1` | `0` = wake word fully off (e.g. while recording a video that says "Zuki") |
| `ZUKI_STT_KEYTERMS` | — | Comma-separated words to bias speech recognition toward (e.g. `Premiere Pro,Figma`) |
| `ZUKI_STREAM_STT` / `ZUKI_STREAM_TTS` | `1` | `0` reverts to batch STT / whole-reply TTS |
| `ZUKI_MOVE_STAGGER` | `0.12` | Seconds between file moves during organize/undo (`0` = instant) |
| `ZUKI_ORGANIZE_MODEL` | Haiku | Model that plans folder cleanups |
| `ZUKI_BG_MODEL` | `claude-sonnet-5` | Model background agents run on |
| `ZUKI_BG_TIMEOUT` | `900` | Max seconds per background task (partial files are kept on timeout) |

Spend note: Zuki never limits what you can ask of her — background tasks run
on your key at your discretion. If you want hard spend caps, set them where
they belong: [console.anthropic.com](https://console.anthropic.com) → Settings → Limits.

## 6. Optional: Gmail / Calendar via the Google API

By default Zuki drives your **logged-in web apps** (no setup). For the faster,
headless API path, drop a Google **Desktop OAuth client** at
`~/.zuki/google_credentials.json` and `pip install ".[google]"`. See
[`zuki/shell/google_workspace.py`](../zuki/shell/google_workspace.py).
