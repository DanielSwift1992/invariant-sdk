#!/usr/bin/env python3
"""ui.py — Invariant Web UI entrypoint.

This module intentionally stays small:
- `UIHandler` lives in `ui_handler.py`
- server bootstrap lives in `ui_server.py`

Behavior (routes, JSON formats, UI) is preserved; this is only code organization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .ui_handler import UIHandler


DEFAULT_SERVER = "http://165.22.145.158:8080"


def run_ui(port: int = 8080, server: str = DEFAULT_SERVER, overlay_path: Optional[Path] = None):
    """Start UI server."""
    from .ui_server import run_ui as _run_ui

    _run_ui(UIHandler, port=port, server=server, overlay_path=overlay_path)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=8080)
    parser.add_argument("--server", "-s", default=DEFAULT_SERVER)
    parser.add_argument("--overlay", "-o", type=Path)
    args = parser.parse_args()
    run_ui(args.port, args.server, args.overlay)


if __name__ == "__main__":
    main()
