from __future__ import annotations

import html
from functools import lru_cache
from pathlib import Path


def _template_dir() -> Path:
    """
    Locate UI template directory.

    Development default is `invariant-sdk/python/ui_src/` (sibling of the package dir).
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "ui_src",  # invariant-sdk/python/ui_src
        here.parent / "ui_src",  # fallback (if co-located)
    ]
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    raise FileNotFoundError(
        "UI templates not found. Expected `ui_src/` next to the `invariant_sdk` package directory."
    )


@lru_cache(maxsize=8)
def _read_template(name: str) -> str:
    p = _template_dir() / name
    return p.read_text(encoding="utf-8")


def render_main_page(*, crystal_id: str, overlay_status: str) -> str:
    # NOTE: Keep this template free of Python escape surprises.
    # If you need JS sequences like \\n, keep them as \\n in the HTML file.
    page = _read_template("main.html")
    page = page.replace("$$CRYSTAL_ID$$", html.escape(crystal_id))
    page = page.replace("$$OVERLAY_STATUS$$", overlay_status)
    return page


def render_graph3d_page() -> str:
    return _read_template("graph3d.html")

