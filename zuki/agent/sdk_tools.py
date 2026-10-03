"""
DEPRECATED — intentionally empty.

Zuki no longer uses the Claude Agent SDK / Claude Code. The agent layer now
calls LLM providers directly (see ``zuki/providers/``) and organizes via a
single structured plan call (``zuki/agent/planner.py``) executed through
``safe_fs``. This module is retained only because the workspace mount does not
permit file deletion; it is not imported anywhere.
"""
