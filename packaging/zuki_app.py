"""
PyInstaller entry point for the Zuki .exe.

Double-clicking the built Zuki.exe runs this, which launches the voice
companion (equivalent to `zuki run`). Keys are read from the user config dir
(%LOCALAPPDATA%\\Zuki\\.env) when frozen — see zuki/shell/config.py — so
users just add their keys, no code checkout needed.
"""

import sys

from zuki.companion import launch

if __name__ == "__main__":
    raise SystemExit(launch())
