from __future__ import annotations

import socket
import subprocess
import time
from http.server import HTTPServer
from pathlib import Path
from typing import Optional, Type

from .overlay import OverlayGraph, find_overlays
from .physics import HaloPhysics


DEFAULT_SERVER = "http://165.22.145.158:8080"


class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def run_ui(
    handler_cls: Type,
    *,
    port: int = 8080,
    server: str = DEFAULT_SERVER,
    overlay_path: Optional[Path] = None,
) -> None:
    """
    Start the UI server for a given handler class.

    `handler_cls` is expected to be a `BaseHTTPRequestHandler` subclass that
    exposes the same class attributes as `invariant_sdk.ui.UIHandler`.
    """
    print("Invariant UI")
    print("=" * 40)
    print()

    # Kill existing
    try:
        subprocess.run(f"lsof -ti:{port} | xargs kill -9 2>/dev/null", shell=True, capture_output=True)
        time.sleep(0.3)
    except Exception:
        pass

    # Connect to crystal (α). UI must still work offline for σ-only workflows.
    print(f"Connecting to: {server}")
    physics: Optional[HaloPhysics] = None
    try:
        physics = HaloPhysics(
            server,
            overlay=overlay_path,
            auto_discover_overlay=(overlay_path is None),
        )
        handler_cls.physics = physics
        print(f"  Crystal: {physics.crystal_id}")
    except Exception as e:
        handler_cls.physics = None
        print(f"  Crystal: offline ({e})")

    # Load overlay (σ) deterministically.
    overlay: Optional[OverlayGraph] = None
    if physics and physics.overlay:
        overlay = physics.overlay
        if overlay_path:
            handler_cls.overlay_path = overlay_path
    else:
        overlays: list[Path] = [overlay_path] if overlay_path else find_overlays()
        if overlays:
            handler_cls.overlay_path = overlays[-1]
            overlay = OverlayGraph.load(overlays[-1])
        else:
            overlay = OverlayGraph()
            handler_cls.overlay_path = overlay_path or Path("./.invariant/overlay.jsonl")

    handler_cls.overlay = overlay
    handler_cls._invalidate_overlay_caches()
    handler_cls._get_overlay_index()

    if overlay:
        print(f"  Local: {overlay.n_edges} edges, {len(overlay.labels)} labels")

    print()
    print(f"→ Open http://localhost:{port}")
    print("  Ctrl+C to stop")
    print()

    httpd = ReuseHTTPServer(("localhost", port), handler_cls)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        httpd.shutdown()

