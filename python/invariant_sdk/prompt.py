"""
prompt.py — Operator Prompt for Bots

Provides the system prompt for AI agents using the Invariant SDK.
"""

from pathlib import Path
from typing import Optional

# Load prompt from bundled file
_PROMPT_FILE = Path(__file__).parent / "operator_prompt.md"
_PROMPT_CACHE: Optional[str] = None


def _load_prompt() -> str:
    """Load and cache the full prompt."""
    global _PROMPT_CACHE
    if _PROMPT_CACHE is None:
        if _PROMPT_FILE.exists():
            _PROMPT_CACHE = _PROMPT_FILE.read_text()
        else:
            _PROMPT_CACHE = "# Invariant SDK Operator\n\nUse observe(), resonate(), crystallize(), evolve(), forget()."
    return _PROMPT_CACHE


def get_prompt(section: Optional[str] = None) -> str:
    """
    Get the operator prompt for AI agents.
    
    Args:
        section: Optional section to extract. Options:
            - None: Full prompt
            - "intro": What the SDK does
            - "concepts": Core concepts (edges, relations, rings)
            - "api": API reference (all methods)
            - "examples": Interaction examples
            - "hints": Important tips
    
    Returns:
        The prompt text (or relevant section).
    
    Example:
        >>> from invariant_sdk import get_prompt
        >>> bot_prompt = get_prompt()  # Full prompt
        >>> api_only = get_prompt("api")  # Just API reference
    """
    full = _load_prompt()
    
    if section is None:
        return full
    
    # Section markers
    sections = {
        "intro": ("## What the SDK Does", "---"),
        "concepts": ("## Core Concepts", "## API Reference"),
        "api": ("## API Reference", "## Interaction Examples"),
        "examples": ("## Interaction Examples", "## Important Notes"),
        "hints": ("## Important Notes", None),
    }
    
    if section not in sections:
        return full
    
    start_marker, end_marker = sections[section]
    
    # Find section
    start_idx = full.find(start_marker)
    if start_idx == -1:
        return full
    
    if end_marker:
        end_idx = full.find(end_marker, start_idx + len(start_marker))
        if end_idx == -1:
            end_idx = len(full)
    else:
        end_idx = len(full)
    
    return full[start_idx:end_idx].strip()
