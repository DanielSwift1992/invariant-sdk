from __future__ import annotations

import html


def render_main_page(*, crystal_id: str, overlay_status: str) -> str:
    # NOTE: Keep this template free of Python escape surprises.
    # If you need JS sequences like \n, use \\n so runtime HTML contains \n.
    page = HTML_PAGE.replace('$$CRYSTAL_ID$$', html.escape(crystal_id))
    page = page.replace('$$OVERLAY_STATUS$$', overlay_status)
    return page


# =============================================================================
# Main HTML page (search + docs + ingest)
# =============================================================================

HTML_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invariant</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg: #0a0a0b;
            --surface: #111113;
            --surface-2: #18181b;
            --border: rgba(255, 255, 255, 0.08);
            --border-2: rgba(255, 255, 255, 0.12);
            --text: #fafafa;
            --text-2: #a1a1aa;
            --text-3: #71717a;
            --accent: #3b82f6;
            --accent-dim: rgba(59, 130, 246, 0.15);
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        
	        body {
	            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
	            background: radial-gradient(900px circle at 15% -10%, rgba(59, 130, 246, 0.14), transparent 55%), var(--bg);
	            color: var(--text);
	            min-height: 100vh;
	            padding: 92px 20px 40px;
	            -webkit-font-smoothing: antialiased;
	        }

            .nav {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                z-index: 100;
                padding: 14px 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: rgba(10, 10, 11, 0.72);
                backdrop-filter: blur(12px);
                border-bottom: 1px solid var(--border);
            }

            .nav-left {
                display: flex;
                align-items: center;
                gap: 18px;
                min-width: 0;
            }

            .nav-logo {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                font-weight: 600;
                font-size: 14px;
                letter-spacing: -0.02em;
                color: var(--text);
                text-decoration: none;
                white-space: nowrap;
            }

            .nav-logo:hover { opacity: 0.9; }

            .nav-links {
                display: flex;
                gap: 14px;
                align-items: center;
            }

            .nav-link {
                font-size: 13px;
                color: var(--text-2);
                text-decoration: none;
                padding: 6px 10px;
                border-radius: 8px;
                border: 1px solid transparent;
            }

            .nav-link:hover {
                color: var(--text);
                background: rgba(255,255,255,0.03);
                border-color: var(--border);
            }

            .nav-meta {
                display: flex;
                gap: 8px;
                align-items: center;
                flex-shrink: 0;
            }

            .chip {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 10px;
                border-radius: 999px;
                border: 1px solid var(--border);
                background: rgba(17, 17, 19, 0.8);
                font-size: 12px;
                color: var(--text-2);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                max-width: 46vw;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .chip strong { color: var(--text); font-weight: 600; }

            .chip.sigma {
                border-color: rgba(34, 197, 94, 0.22);
                background: rgba(34, 197, 94, 0.08);
                color: rgba(34, 197, 94, 0.95);
            }
        
	        .container {
	            max-width: 1100px;
	            margin: 0 auto;
	        }
        
	        h1 {
	            font-size: 28px;
	            margin-bottom: 8px;
	            color: var(--text);
	            letter-spacing: -0.02em;
	        }

	        .mark { color: var(--accent); }
        
	        .subtitle {
	            color: var(--text-2);
	            margin-bottom: 32px;
	        }

	        .hint {
	            color: var(--text-3);
	            font-size: 12px;
	            margin: 8px 0 18px;
	        }

            .layout {
                display: grid;
                grid-template-columns: 320px 1fr;
                gap: 16px;
                align-items: start;
            }

            .sidebar {
                position: sticky;
                top: 92px;
                height: calc(100vh - 120px);
                overflow: auto;
                padding: 12px 12px 14px;
                border: 1px solid var(--border);
                border-radius: 14px;
                background: rgba(17, 17, 19, 0.78);
                box-shadow: 0 14px 40px rgba(0,0,0,0.35);
            }

            .sidebar-header {
                display: flex;
                flex-direction: column;
                gap: 8px;
                margin-bottom: 10px;
            }

            .sidebar-title {
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                color: var(--text-3);
            }

            .sidebar-selected {
                margin-top: 2px;
                color: var(--text-2);
                font-size: 12px;
                word-break: break-word;
            }

            .sidebar-actions {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                justify-content: flex-end;
            }

            .file-filter {
                margin: 10px 0 10px;
            }

            .file-filter input {
                width: 100%;
                padding: 10px 12px;
                font-size: 13px;
                background: rgba(255,255,255,0.02);
                border: 1px solid var(--border);
                border-radius: 10px;
                color: var(--text);
            }

            .file-filter input:focus {
                outline: none;
                border-color: rgba(59,130,246,0.7);
                box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
            }

            .file-tree {
                display: flex;
                flex-direction: column;
                gap: 4px;
                padding-right: 6px;
                max-height: 44vh;
                overflow: auto;
            }

            .tree-folder { margin-top: 4px; }

            .tree-children {
                display: none;
                margin-left: 10px;
                padding-left: 10px;
                border-left: 1px solid rgba(255,255,255,0.06);
            }

            .tree-folder.open > .tree-children { display: block; }

            .tree-row {
                width: 100%;
                text-align: left;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 10px;
                border-radius: 10px;
                border: 1px solid transparent;
                background: rgba(255,255,255,0.02);
                color: var(--text);
                cursor: pointer;
            }

            .tree-row:hover {
                background: rgba(255,255,255,0.03);
                border-color: var(--border);
            }

            .tree-row.active {
                background: var(--accent-dim);
                border-color: rgba(59,130,246,0.35);
            }

            .tree-row .chev {
                width: 14px;
                color: var(--text-3);
                opacity: 0.9;
                transition: transform 120ms ease;
                flex-shrink: 0;
            }

            .tree-folder.open > .tree-row .chev { transform: rotate(90deg); }

            .tree-row .label {
                flex: 1;
                font-size: 13px;
                font-weight: 500;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .tree-row .meta {
                font-size: 11px;
                color: var(--text-3);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                flex-shrink: 0;
            }

            .tree-empty {
                color: var(--text-2);
                font-size: 12px;
                padding: 10px 12px;
                border: 1px dashed var(--border-2);
                border-radius: 10px;
                background: rgba(255,255,255,0.03);
            }

            .main {
                min-width: 0;
            }

            @media (max-width: 980px) {
                .layout { grid-template-columns: 1fr; }
                .sidebar { position: relative; top: auto; height: auto; max-height: none; }
                .file-tree { max-height: 260px; }
            }

	        .doc-action {
	            background: rgba(255,255,255,0.03);
	            color: var(--text);
	            border: 1px solid var(--border);
	            padding: 6px 10px;
	            border-radius: 10px;
	            cursor: pointer;
	            font-size: 12px;
	            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
	        }

	        .doc-action:hover:not(:disabled) {
	            border-color: rgba(59, 130, 246, 0.65);
	            background: var(--accent-dim);
	        }

	        .doc-action:disabled {
	            opacity: 0.55;
	            cursor: not-allowed;
	        }

	        .doc-action.danger:hover:not(:disabled) {
	            border-color: rgba(239, 68, 68, 0.65);
	            background: rgba(239, 68, 68, 0.15);
	            color: #f87171;
	        }

	        .graph-preview {
            margin-top: 16px;
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            background: rgba(255,255,255,0.03);
        }

        .graph-preview-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-2);
        }

        .graph-preview-actions {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .mini-btn {
            background: rgba(255,255,255,0.03);
            color: var(--text);
            border: 1px solid var(--border);
            padding: 4px 8px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
        }

        .mini-btn.active { border-color: var(--accent); background: var(--accent-dim); }

        .graph-preview-header a {
            color: var(--accent);
            text-decoration: none;
        }

        .graph-preview-header a:hover { text-decoration: underline; }

        .graph-frame {
            width: 100%;
            height: 340px;
            border: 0;
            background: #0d1117;
        }
        
        .search-form {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }
        
        .search-input {
            flex: 1;
            width: 100%;
            padding: 14px 18px;
            font-size: 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
        }
        
        .search-input:focus {
            outline: none;
            border-color: rgba(59,130,246,0.7);
            box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
        }
        
        .btn {
            padding: 14px 24px;
            font-size: 14px;
            font-weight: 500;
            background: var(--text);
            color: var(--bg);
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        
        .btn:hover { opacity: 0.92; }
        .btn:disabled { opacity: 0.6; cursor: wait; }
        
        /* Autocomplete styles */
        .search-wrapper {
            position: relative;
            flex: 1;
        }
        
        .autocomplete {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--surface);
            border: 1px solid var(--border);
            border-top: none;
            border-radius: 0 0 8px 8px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 100;
            display: none;
        }
        
        .autocomplete.show { display: block; }
        
        .autocomplete-item {
            padding: 10px 18px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .autocomplete-item:hover {
            background: rgba(255,255,255,0.03);
        }
        
        .autocomplete-item.local {
            border-left: 3px solid var(--success);
        }
        
        .autocomplete-item.global {
            border-left: 3px solid var(--accent);
        }
        
        .autocomplete-source {
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .autocomplete-source.local {
            background: rgba(34, 197, 94, 0.15);
            color: var(--success);
        }
        
        .autocomplete-source.global {
            background: var(--accent-dim);
            color: var(--accent);
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-2);
        }
        
        .spinner {
            display: inline-block;
            width: 24px;
            height: 24px;
            border: 3px solid var(--border);
            border-top: 3px solid var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
            vertical-align: middle;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .results {
            background: var(--surface);
            border-radius: 12px;
            padding: 24px;
            border: 1px solid var(--border);
        }
        
        .result-header {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .result-header h2 {
            font-size: 20px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .phase-badge {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
        
        .phase-badge.solid {
            background: var(--accent-dim);
            color: var(--accent);
        }
        
        .phase-badge.gas {
            background: rgba(255,255,255,0.06);
            color: var(--text-2);
        }
        
	        .result-meta {
	            display: flex;
	            gap: 16px;
	            font-size: 12px;
	            color: var(--text-3);
	            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
	        }

            /* File SERP (Locate) */
            .file-card {
                padding: 14px 16px;
                border-radius: 12px;
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.06);
                transition: border-color 0.15s, background 0.15s;
                margin-bottom: 12px;
            }

            .file-card:hover {
                border-color: rgba(59,130,246,0.45);
                background: rgba(59,130,246,0.06);
            }

            .file-top {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 12px;
            }

            .file-path {
                min-width: 0;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 13px;
                color: var(--text);
                text-decoration: none;
            }

            .file-path:hover {
                text-decoration: underline;
            }

            .file-score {
                flex-shrink: 0;
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 12px;
                color: var(--text-3);
            }

            .file-why {
                margin-top: 10px;
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                align-items: center;
                color: var(--text-2);
                font-size: 12px;
            }

            .word-pill {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 3px 8px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(17,17,19,0.65);
                color: var(--text);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 11px;
                max-width: 340px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                position: relative;
                --pct: 0;
                transition: all 0.15s ease;
            }

            .word-pill::before {
                content: "";
                position: absolute;
                left: 8px;
                right: 8px;
                bottom: 2px;
                height: 2px;
                border-radius: 999px;
                background: rgba(99, 179, 237, 0.12);
                overflow: hidden;
            }

            .word-pill::after {
                content: "";
                position: absolute;
                left: 8px;
                bottom: 2px;
                height: 2px;
                width: calc(var(--pct, 0) * 1%);
                border-radius: 999px;
                background: rgba(99, 179, 237, 0.85);
            }

            .word-pill.signal {
                border-color: rgba(99, 179, 237, 0.4);
                background: rgba(59, 130, 246, 0.15);
            }

            .word-pill.noise {
                border-color: rgba(255,255,255,0.06);
                background: rgba(17,17,19,0.4);
                color: var(--text-2);
            }

            .word-pill .pct {
                font-size: 9px;
                color: rgba(99, 179, 237, 0.8);
                font-weight: 600;
            }

            .word-pill.noise .pct {
                color: var(--text-3);
            }

            .word-pill .src {
                font-size: 9px;
                color: rgba(255,255,255,0.36);
                font-weight: 600;
            }

            .noise-details {
                display: inline-flex;
                align-items: center;
            }

            .noise-summary {
                list-style: none;
                cursor: pointer;
                padding: 3px 8px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(17,17,19,0.55);
                color: var(--text-3);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 11px;
            }

            .noise-summary:hover {
                border-color: rgba(255,255,255,0.18);
                color: var(--text-2);
            }

            .noise-details[open] .noise-summary {
                border-color: rgba(255,255,255,0.18);
                color: var(--text-2);
            }

            .noise-summary::-webkit-details-marker {
                display: none;
            }

            .noise-list {
                margin-left: 8px;
                display: inline-flex;
                flex-wrap: wrap;
                gap: 6px;
                align-items: center;
            }

            /* IDE-style code preview (continuous block) */
            .file-occ {
                margin-top: 12px;
                display: flex;
                flex-direction: column;
                background: rgba(0,0,0,0.25);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.06);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                max-height: 400px;  /* ~20 lines of code */
                overflow: auto;  /* Scroll on container, not individual lines */
            }

            .occ-line {
                display: flex;
                gap: 12px;
                align-items: baseline;
                padding: 3px 12px;
                cursor: pointer;
                transition: background 0.1s;
                border-left: 3px solid transparent;
            }

            .occ-line:hover {
                background: rgba(255,255,255,0.04);
            }

            /* Lines with matches get subtle highlight */
            .occ-line.has-match {
                background: rgba(255,215,0,0.04);
                border-left-color: rgba(255,215,0,0.3);
            }

            .occ-line.has-match:hover {
                background: rgba(255,215,0,0.08);
            }

            .occ-no {
                flex-shrink: 0;
                color: var(--text-3);
                font-size: 11px;
                min-width: 48px;
                text-align: right;
                user-select: none;
            }

            .occ-text {
                min-width: 0;
                color: var(--text);
                font-size: 12px;
                line-height: 1.5;
                white-space: pre;
            }

            /* Context lines (no matches) are dimmer */
            .occ-line:not(.has-match) .occ-text {
                color: var(--text-2);
            }

            .file-actions {
                margin-top: 12px;
                display: flex;
                gap: 10px;
                align-items: center;
                flex-wrap: wrap;
            }

            .mini-link {
                color: var(--text-2);
                text-decoration: none;
                font-size: 12px;
                padding: 6px 10px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.02);
            }

            .mini-link:hover {
                color: var(--text);
                border-color: rgba(59,130,246,0.35);
                background: rgba(59,130,246,0.06);
            }

            .outline-box {
                margin-top: 10px;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                background: rgba(17, 17, 19, 0.65);
                overflow: hidden;
            }

            .outline-head {
                padding: 10px 12px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }

            .outline-title {
                font-size: 12px;
                color: var(--text-2);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .outline-body {
                padding: 10px 12px;
            }

            .outline-item {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: baseline;
                padding: 6px 8px;
                border-radius: 10px;
                border: 1px solid transparent;
                cursor: pointer;
            }

            .outline-item:hover {
                border-color: rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.03);
            }

            .outline-name {
                min-width: 0;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 12px;
                color: var(--text);
            }

            .outline-loc {
                flex-shrink: 0;
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 11px;
                color: var(--text-3);
            }

            /* Highlight: Two-Tier Gravity (Invariant IV: Will > Observation) */
            
            /* Tier 1: Core (Will) — Gravitational centers. User's query words. */
            .hl-core {
                background: rgba(255, 215, 0, 0.16);
                border: 1px solid rgba(255, 215, 0, 0.40);
                padding: 0 3px;
                border-radius: 4px;
                font-weight: 600;
            }

            /* Tier 2: Resonant (Observation) — Context orbits. Expanded terms. */
            .hl-resonant {
                border-bottom: 2px solid rgba(59, 130, 246, 0.50);
            }

            /* Context tooltip (hover preview) */
            .context-tooltip {
                position: fixed;
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 14px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.6);
                z-index: 9999;
                max-width: min(760px, calc(100vw - 24px));
                max-height: min(520px, calc(100vh - 24px));
                overflow: hidden;
                pointer-events: auto;
            }

            .tt-head {
                padding: 10px 12px;
                background: rgba(17, 17, 19, 0.88);
                border-bottom: 1px solid rgba(255,255,255,0.06);
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: flex-start;
            }

            .tt-title {
                font-weight: 600;
                color: var(--text);
                font-size: 12px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 520px;
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            }

            .tt-sub {
                margin-top: 4px;
                font-size: 11px;
                color: var(--text-3);
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 520px;
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            }

            .tt-pills {
                margin-top: 8px;
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
                align-items: center;
            }

            .tt-pill {
                display: inline-flex;
                align-items: center;
                padding: 2px 8px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.02);
                color: var(--text-2);
                font-size: 11px;
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                max-width: 260px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .tt-pill.primary {
                background: rgba(34,197,94,0.10);
                border-color: rgba(34,197,94,0.28);
                color: var(--text);
            }

            .tt-meta {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                padding: 8px 12px;
                border-bottom: 1px solid rgba(255,255,255,0.06);
                background: rgba(0,0,0,0.18);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 11px;
                color: var(--text-3);
            }

            .tt-body {
                padding: 10px 12px;
                overflow: auto;
            }

            .ctx-row {
                display: flex;
                gap: 10px;
                align-items: baseline;
                padding: 2px 0;
            }

            .ctx-row.active {
                background: rgba(59,130,246,0.08);
                border-radius: 10px;
                padding: 4px 8px;
                margin: 2px -8px;
            }

            .ctx-no {
                width: 58px;
                flex-shrink: 0;
                text-align: right;
                color: var(--text-3);
                font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 11px;
            }

            .ctx-code {
                min-width: 0;
                flex: 1;
                white-space: pre-wrap;
                word-break: break-word;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                line-height: 1.45;
                font-size: 12px;
                color: var(--text);
            }
        
        .result-list {
            list-style: none;
        }
        
        .result-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.02);
            cursor: pointer;
            transition: background 0.2s;
            border: 1px solid transparent;
        }
        
        .result-item:hover {
            background: rgba(59,130,246,0.06);
            border-color: var(--border);
        }
        
        .result-item.ring-sigma { border-left: 3px solid var(--success); }
        .result-item.ring-alpha { border-left: 3px solid rgba(59, 130, 246, 0.55); }
        .result-item.ring-lambda { border-left: 3px solid rgba(255, 255, 255, 0.18); }
        .result-item.ring-eta { border-left: 3px solid rgba(239, 68, 68, 0.8); }
        
        .result-word {
            font-weight: 500;
            font-size: 14px;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .result-weight {
            color: var(--text-2);
            font-size: 12px;
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            flex-shrink: 0;
        }
        
        .result-loc {
            color: var(--text-3);
            font-size: 11px;
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            flex: 1;
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 0;
            margin: 0 12px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .result-loc .loc-file {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .result-loc .loc-line {
            flex-shrink: 0;
            margin-left: 0;
            color: var(--text-2);
        }

        /* Mentions (uses in docs) */
        .mentions {
            margin-top: 16px;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(255,255,255,0.02);
            overflow: hidden;
        }

        .mentions-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding: 12px 14px;
            background: rgba(17, 17, 19, 0.85);
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        .mentions-title {
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--text-3);
        }

        .mentions-meta {
            font-size: 11px;
            color: var(--text-3);
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        .mentions-body {
            padding: 12px 14px;
        }

        .mentions-actions {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 10px;
        }

        .mentions-actions .mini-btn {
            padding: 6px 10px;
            font-size: 12px;
        }

        .mentions-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .mention-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid transparent;
            background: rgba(255,255,255,0.02);
            cursor: pointer;
        }

        .mention-item:hover {
            border-color: rgba(59,130,246,0.35);
            background: rgba(59,130,246,0.06);
        }

        .mention-loc {
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            color: var(--text);
            display: flex;
            align-items: center;
            justify-content: flex-start;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .mention-loc .mention-file {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .mention-loc .mention-line {
            flex-shrink: 0;
            color: var(--text-2);
        }

        .mention-badge {
            font-size: 10px;
            padding: 3px 6px;
            border-radius: 6px;
            background: rgba(34, 197, 94, 0.12);
            color: rgba(34, 197, 94, 0.95);
            border: 1px solid rgba(34, 197, 94, 0.22);
            flex-shrink: 0;
        }

        .context-panel {
            margin-top: 12px;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            background: rgba(17, 17, 19, 0.65);
            overflow: hidden;
        }

        .context-panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: rgba(17, 17, 19, 0.85);
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        .context-panel-title {
            font-size: 12px;
            color: var(--text-2);
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 68%;
        }

        .context-panel-body {
            padding: 12px;
            white-space: pre-wrap;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            line-height: 1.5;
            color: var(--text);
        }
        
        .badge {
            font-size: 10px;
            padding: 3px 6px;
            border-radius: 4px;
            font-weight: 600;
        }
        
        .badge-sigma { background: rgba(34, 197, 94, 0.15); color: var(--success); }
        .badge-alpha { background: var(--accent-dim); color: var(--accent); }
        .badge-lambda { background: rgba(255,255,255,0.06); color: var(--text-2); }
        .badge-eta { background: rgba(239, 68, 68, 0.12); color: rgba(239, 68, 68, 0.95); }
        
        .orbit-group {
            margin-top: 20px;
        }
        
        .orbit-group h4 {
            font-size: 13px;
            margin-bottom: 12px;
            color: var(--text-2);
        }
        
        .empty {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-2);
        }
        
        .doc-section {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.06);
        }
        
        .doc-section h3 {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--text-3);
            margin-bottom: 12px;
        }
        
        .doc-upload {
            border: 1px dashed var(--border-2);
            border-radius: 12px;
            padding: 18px 14px;
            text-align: center;
            cursor: pointer;
            transition: all 0.15s;
            background: rgba(255,255,255,0.02);
        }
        
        .doc-upload:hover {
            border-color: var(--accent);
            background: var(--accent-dim);
        }

        .doc-upload.drag-over {
            border-color: var(--accent);
            background: var(--accent-dim);
        }
        
        .doc-upload input {
            display: none;
        }

        /* Tabs + legend */
        .mode-tabs {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin: 4px 0 16px;
        }

        .mode-tab {
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text-2);
            padding: 8px 16px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 13px;
        }

        .mode-tab:hover { border-color: rgba(59, 130, 246, 0.65); }

        .mode-tab.active {
            background: var(--accent-dim);
            border-color: rgba(59, 130, 246, 0.65);
            color: var(--text);
        }

        .mode-panel { display: none; }
        .mode-panel.active { display: block; }

        .legend {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            padding: 10px 14px;
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            border: 1px solid var(--border);
            font-size: 12px;
            margin-bottom: 16px;
        }

        .legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
        .legend-dot.sigma { background: var(--success); }
        .legend-dot.alpha { background: var(--accent); }
        .legend-dot.lambda { background: rgba(255,255,255,0.24); }
        .legend-dot.eta { background: rgba(239,68,68,0.75); }

        .verify-form { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
        .verify-input {
            flex: 1;
            min-width: 220px;
            padding: 12px 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
        }

        .verify-input:focus {
            outline: none;
            border-color: rgba(59,130,246,0.7);
            box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
        }

        .conflict-item {
            padding: 12px 16px;
            background: rgba(239, 68, 68, 0.05);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 12px;
            margin-bottom: 12px;
        }

        .conflict-item .src { color: var(--text); font-weight: 600; }
        .conflict-item .docs { color: var(--text-3); font-size: 12px; margin-top: 4px; }
        
            @media (max-width: 820px) {
                .nav-meta { display: none; }
            }

            @media (max-width: 560px) {
                body { padding-top: 86px; }
                .nav { padding: 12px 16px; }
                .nav-links { display: none; }
            }
	    </style>
	</head>
	<body>
        <nav class="nav">
            <div class="nav-left">
                <a class="nav-logo" href="/"><span class="mark">◆</span> Invariant</a>
                <div class="nav-links">
                    <a class="nav-link" href="/">Search</a>
                    <a class="nav-link" href="/doc">Docs</a>
                    <a class="nav-link" href="/graph3d">3D</a>
                </div>
            </div>
            <div class="nav-meta">
                <span class="chip">Crystal: <strong>$$CRYSTAL_ID$$</strong></span>
                <span class="chip sigma">$$OVERLAY_STATUS$$</span>
            </div>
        </nav>
		    <div class="container">
                <div class="layout">
                    <aside class="sidebar">
                        <div class="sidebar-header">
                            <div style="min-width:0;">
                                <div class="sidebar-title">Files</div>
                                <div class="sidebar-selected" id="sidebarSelected">All documents</div>
                            </div>
                            <div class="sidebar-actions">
                                <button id="openDocBtn" class="doc-action" type="button" disabled>Open</button>
                                <button id="revealDocBtn" class="doc-action" type="button" disabled>Reveal</button>
                                <button id="vscodeDocBtn" class="doc-action" type="button" disabled>VS Code</button>
                                <button id="reindexBtn" class="doc-action" type="button" disabled>Reindex</button>
                                <button id="deleteDocBtn" class="doc-action danger" type="button" disabled>Delete</button>
                            </div>
                        </div>

                        <div class="file-filter">
                            <input id="docFilter" type="text" placeholder="Filter files…" autocomplete="off">
                        </div>

                        <div id="docTree" class="file-tree">
                            <div class="tree-empty">Loading…</div>
                        </div>

                        <div class="doc-section">
                            <h3>Add document</h3>
                            <div class="doc-upload" id="dropZone">
                                <input type="file" id="fileInput" onchange="uploadFile(this)">
                                <p>📄 Drag file here or click to upload</p>
                                <p style="font-size: 12px; color: var(--text-3); margin-top: 8px;">
                                    Any text file (UTF-8) — .py, .js, .md, .txt, .json, etc.
                                </p>
                            </div>
                        </div>
                    </aside>

                    <main class="main">
			                <p class="subtitle" style="margin-top: 4px;">Locate files</p>
	                        <div class="hint">
	                            Paste an error, stack trace, or symbol → get ranked files. Use Outline to see structure before reading full content.
	                        </div>

                <!-- Mode Tabs -->
	                <div class="mode-tabs">
	                    <button class="mode-tab active" data-mode="search" onclick="setMode('search')">Locate</button>
	                    <button class="mode-tab" data-mode="verify" onclick="setMode('verify')">Verify</button>
	                    <button class="mode-tab" data-mode="conflicts" onclick="setMode('conflicts')">Conflicts</button>
	                </div>

                <!-- Legend -->
	                <div class="legend">
	                    <div class="legend-item"><span class="legend-dot alpha"></span> Ranked files • Score = 2^(unique matched terms) • Click a line to preview/open</div>
	                </div>
		        
		        <!-- Mode: Search -->
                <div class="mode-panel active" id="panel-search">
		            <div class="search-form">
	                    <div class="search-wrapper">
		                        <input type="text" class="search-input" id="query" 
		                               placeholder="Paste issue text / error / symbol (e.g. separability_matrix)" autofocus
		                               oninput="handleInput(this.value)" autocomplete="off">
                        <div class="autocomplete" id="autocomplete"></div>
                    </div>
	                    <button class="btn" id="searchBtn" onclick="search()">Locate</button>
	                </div>
        
	                <div id="content">
	                    <div class="empty">
	                        <h3>Paste an error or symbol</h3>
	                        <p>Get a ranked list of files + previews showing why they match</p>
	                    </div>
	                </div>
                </div>

                <!-- Mode: Verify -->
                <div class="mode-panel" id="panel-verify">
                    <div class="verify-form">
                        <input type="text" class="verify-input" id="verifySource" placeholder="Source concept (e.g. user)">
                        <span style="color:var(--text-3);align-self:center;">→</span>
                        <input type="text" class="verify-input" id="verifyTarget" placeholder="Target concept (e.g. database)">
                        <button class="btn" onclick="verifyPath()">Verify</button>
                    </div>
                    <div id="verifyResult">
                        <div class="empty">
                            <h3>Check if concepts are connected</h3>
                            <p>Enter source and target to find σ-proof</p>
                        </div>
                    </div>
                </div>

                <!-- Mode: Conflicts -->
                <div class="mode-panel" id="panel-conflicts">
                    <div id="conflictsList">
                        <div class="loading"><span class="spinner"></span>Loading conflicts...</div>
                    </div>
                </div>
                    </main>
                </div>
		    </div>

    
		    <script>
	        const queryInput = document.getElementById('query');
	        const searchBtn = document.getElementById('searchBtn');
		        const content = document.getElementById('content');
			    const autocomplete = document.getElementById('autocomplete');

                // Sidebar (IDE-like)
                const docTree = document.getElementById('docTree');
                const docFilter = document.getElementById('docFilter');
                const sidebarSelected = document.getElementById('sidebarSelected');
                const openDocBtn = document.getElementById('openDocBtn');
                const revealDocBtn = document.getElementById('revealDocBtn');
                const vscodeDocBtn = document.getElementById('vscodeDocBtn');
                const reindexBtn = document.getElementById('reindexBtn');

		        const dropZone = document.getElementById('dropZone');
		        const fileInput = document.getElementById('fileInput');
	        
	        let selectedDoc = '';
            let miniLabels = true;
	        
	        let debounceTimer;
            let currentMode = 'search';

            // Mode switching
            function setMode(mode) {
                currentMode = mode;
                document.querySelectorAll('.mode-tab').forEach(tab => {
                    tab.classList.toggle('active', tab.dataset.mode === mode);
                });
                document.querySelectorAll('.mode-panel').forEach(panel => {
                    panel.classList.toggle('active', panel.id === 'panel-' + mode);
                });
                if (mode === 'conflicts') loadConflicts();
            }

            // Verify path
            async function verifyPath() {
                const src = document.getElementById('verifySource').value.trim();
                const tgt = document.getElementById('verifyTarget').value.trim();
                const resultDiv = document.getElementById('verifyResult');
                if (!src || !tgt) {
                    resultDiv.innerHTML = '<div class="empty"><h3>Enter both concepts</h3></div>';
                    return;
                }
                resultDiv.innerHTML = '<div class="loading"><span class="spinner"></span>Checking connection...</div>';
                try {
                    const res = await fetch('/api/verify?subject=' + encodeURIComponent(src) + '&object=' + encodeURIComponent(tgt));
                    const data = await res.json();
                    if (data.error) {
                        resultDiv.innerHTML = '<div class="empty"><h3>Error</h3><p>' + escHtml(data.error) + '</p></div>';
                        return;
                    }

                    const steps = Array.isArray(data.steps) ? data.steps : [];
                    const sources = Array.isArray(data.sources) ? data.sources : [];
                    const hasPath = steps.length > 0;
                    const proven = !!data.proven;
                    const status = proven ? 'proven' : (hasPath ? 'weak' : 'none');
                    const title = status === 'proven'
                        ? 'σ-proven'
                        : status === 'weak'
                            ? 'Path exists (not σ-proof)'
                            : 'No path';
                    const color = status === 'proven'
                        ? 'var(--success)'
                        : status === 'weak'
                            ? 'var(--warning)'
                            : 'var(--danger)';
                    const bg = status === 'proven'
                        ? 'rgba(34,197,94,0.05)'
                        : status === 'weak'
                            ? 'rgba(245,158,11,0.06)'
                            : 'rgba(239,68,68,0.05)';
                    const border = status === 'proven'
                        ? 'rgba(34,197,94,0.2)'
                        : status === 'weak'
                            ? 'rgba(245,158,11,0.25)'
                            : 'rgba(239,68,68,0.2)';

                    let html = `
                        <div class="results" style="background:${bg};border-color:${border};">
                            <h3 style="color:${color};margin-bottom:10px;">${escHtml(title)}</h3>
                            <div style="color:var(--text-2);font-size:13px;margin-bottom:10px;">
                                ${escHtml(String(data.message || ''))}
                            </div>
                            <div style="display:flex;gap:12px;flex-wrap:wrap;color:var(--text-3);font-size:12px;font-family:'JetBrains Mono',ui-monospace;">
                                <span>Subject: <span style="color:var(--text)">${escHtml(String(data.subject_label || src))}</span></span>
                                <span>Object: <span style="color:var(--text)">${escHtml(String(data.object_label || tgt))}</span></span>
                            </div>
                    `;

                    if (sources.length) {
                        html += `<div style="margin-top:10px;color:var(--text-3);font-size:12px;">Sources: ${sources.map(s => escHtml(String(s))).join(', ')}</div>`;
                    }

                    function ringBadge(ring) {
                        const r = String(ring || '');
                        const label = r === 'sigma' ? 'σ' : r === 'lambda' ? 'λ' : r === 'eta' ? 'η' : 'α';
                        const cls = r === 'sigma' ? 'badge-sigma' : r === 'lambda' ? 'badge-lambda' : r === 'eta' ? 'badge-eta' : 'badge-alpha';
                        return `<span class="badge ${cls}" style="margin-right:8px;">${label}</span>`;
                    }

                    if (steps.length) {
                        html += `<div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px;">`;
                        html += `<div style="color:var(--text-3);font-size:12px;margin-bottom:10px;">Path</div>`;
                        steps.forEach((s, idx) => {
                            const srcLabel = String(s.src_label || '');
                            const tgtLabel = String(s.tgt_label || '');
                            const ring = String(s.ring || '');
                            const doc = s.doc ? String(s.doc) : '';
                            const line = s.line ? String(s.line) : '';
                            const ctxHash = s.ctx_hash ? String(s.ctx_hash) : '';
                            const loc = (doc && line) ? (doc + ':' + line) : (doc || '');

                            const openBtns = doc
                                ? `
                                    <button class="mini-btn" type="button" data-open="vscode" data-doc="${escHtml(doc)}" data-line="${escHtml(line || '1')}" data-ctx-hash="${escHtml(ctxHash)}">VS Code</button>
                                    <button class="mini-btn" type="button" data-open="open" data-doc="${escHtml(doc)}" data-line="${escHtml(line || '1')}" data-ctx-hash="${escHtml(ctxHash)}">Open</button>
                                `
                                : '';

                            html += `
                                <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:rgba(255,255,255,0.02);margin-bottom:8px;">
                                    <div style="width:24px;color:var(--text-3);font-family:'JetBrains Mono',ui-monospace;">${idx + 1}</div>
                                    <div style="min-width:0;flex:1;">
                                        <div style="display:flex;align-items:center;gap:10px;min-width:0;">
                                            ${ringBadge(ring)}
                                            <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                                                ${escHtml(srcLabel)} <span style="color:var(--text-3);">→</span> ${escHtml(tgtLabel)}
                                            </div>
                                        </div>
                                        ${loc ? `<div style="margin-top:4px;color:var(--text-3);font-size:11px;font-family:'JetBrains Mono',ui-monospace;">${escHtml(loc)}</div>` : ''}
                                    </div>
                                    <div style="display:flex;gap:8px;flex-shrink:0;">
                                        ${openBtns}
                                    </div>
                                </div>
                            `;
                        });
                        html += `</div>`;
                    }

                    html += `</div>`;
                    resultDiv.innerHTML = html;

                    resultDiv.querySelectorAll('button[data-open]').forEach(btn => {
                        btn.onclick = async (e) => {
                            e.stopPropagation();
                            const mode = btn.dataset.open;
                            const doc = btn.dataset.doc;
                            const line = btn.dataset.line || '1';
                            const ctxHash = btn.dataset.ctxHash || '';
                            await openDoc(mode, doc, line, ctxHash);
                        };
                    });
                } catch (e) {
                    resultDiv.innerHTML = '<div class="empty"><h3>Error</h3><p>' + escHtml(e.message) + '</p></div>';
                }
            }

            // Load conflicts
            async function loadConflicts() {
                const listDiv = document.getElementById('conflictsList');
                try {
                    const res = await fetch('/api/conflicts');
                    const data = await res.json();
                    const conflicts = data.conflicts || [];
                    if (conflicts.length === 0) {
                        listDiv.innerHTML = '<div class="empty"><h3>No Conflicts</h3><p>Overlay contains no conflicting σ-claims.</p></div>';
                        return;
                    }
                    let html = '<div style="margin-bottom:16px;color:var(--warning);font-weight:600;">' + conflicts.length + ' conflicts detected</div>';
                    conflicts.slice(0, 30).forEach(c => {
                        const target = c && c.target ? String(c.target) : 'unknown';
                        const oldE = c && c.old ? c.old : {};
                        const newE = c && c.new ? c.new : {};
                        const oldDoc = oldE.doc ? String(oldE.doc) : '?';
                        const newDoc = newE.doc ? String(newE.doc) : '?';
                        const oldLine = oldE.line != null ? String(oldE.line) : '?';
                        const newLine = newE.line != null ? String(newE.line) : '?';
                        const oldW = oldE.weight != null ? String(oldE.weight) : '';
                        const newW = newE.weight != null ? String(newE.weight) : '';

                        html += `
                            <div class="conflict-item">
                                <div class="src">→ ${escHtml(target)}</div>
                                <div class="docs" style="display:flex;flex-direction:column;gap:8px;margin-top:10px;">
                                    <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;">
                                        <div style="min-width:0;">
                                            <div style="color:var(--text);font-family:'JetBrains Mono',ui-monospace;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escHtml(oldDoc)}:${escHtml(oldLine)}</div>
                                            ${oldW ? `<div style="color:var(--text-3);font-size:11px;">weight: ${escHtml(oldW)}</div>` : ''}
                                        </div>
                                        <div style="display:flex;gap:8px;flex-shrink:0;">
                                            <button class="mini-btn" type="button" data-open="vscode" data-doc="${escHtml(oldDoc)}" data-line="${escHtml(oldLine)}">VS Code</button>
                                            <button class="mini-btn" type="button" data-open="open" data-doc="${escHtml(oldDoc)}" data-line="${escHtml(oldLine)}">Open</button>
                                        </div>
                                    </div>
                                    <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;">
                                        <div style="min-width:0;">
                                            <div style="color:var(--text);font-family:'JetBrains Mono',ui-monospace;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escHtml(newDoc)}:${escHtml(newLine)}</div>
                                            ${newW ? `<div style="color:var(--text-3);font-size:11px;">weight: ${escHtml(newW)}</div>` : ''}
                                        </div>
                                        <div style="display:flex;gap:8px;flex-shrink:0;">
                                            <button class="mini-btn" type="button" data-open="vscode" data-doc="${escHtml(newDoc)}" data-line="${escHtml(newLine)}">VS Code</button>
                                            <button class="mini-btn" type="button" data-open="open" data-doc="${escHtml(newDoc)}" data-line="${escHtml(newLine)}">Open</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    if (conflicts.length > 30) {
                        html += '<p style="color:var(--text-3);font-size:12px;">...and ' + (conflicts.length - 30) + ' more</p>';
                    }
                    listDiv.innerHTML = html;

                    listDiv.querySelectorAll('button[data-open]').forEach(btn => {
                        btn.onclick = async (e) => {
                            e.stopPropagation();
                            const mode = btn.dataset.open;
                            const doc = btn.dataset.doc;
                            const line = btn.dataset.line || '1';
                            await openDoc(mode, doc, line, '');
                        };
                    });
                } catch (e) {
                    listDiv.innerHTML = '<div class="empty"><h3>Error loading conflicts</h3></div>';
                }
            }


            function escHtml(s) {
                return String(s)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;');
            }

            function safeDecode(v) {
                try { return decodeURIComponent(v); } catch (e) { return String(v || ''); }
            }

            function normalizeNeedles(needles) {
                const out = [];
                const seen = new Set();
                (needles || []).forEach(v => {
                    const s = String(v || '').trim();
                    if (!s) return;
                    const lower = s.toLowerCase();
                    if (seen.has(lower)) return;
                    seen.add(lower);
                    out.push(lower);
                });
                return out;
            }

            function pickPrimaryNeedle(text, needles) {
                const hay = String(text || '');
                const lower = hay.toLowerCase();
                let best = '';
                let bestPos = 1e18;
                let bestLen = 0;
                (needles || []).forEach(n => {
                    const needle = String(n || '').trim().toLowerCase();
                    if (!needle) return;
                    const pos = lower.indexOf(needle);
                    if (pos < 0) return;
                    if (pos < bestPos || (pos === bestPos && needle.length > bestLen)) {
                        best = needle;
                        bestPos = pos;
                        bestLen = needle.length;
                    }
                });
                return best || String((needles && needles[0]) || '').trim().toLowerCase();
            }

            function highlightLineHtml(text, coreNeedles, resonantNeedles) {
                // Two-Tier Gravity Highlighting (Invariant IV: Will > Observation)
                // Core (Will) = user's query words -> hl-core (bright)
                // Resonant (Observation) = expanded terms -> hl-resonant (underline)
                const src = String(text || '');
                if (!src) return '';
                
                const coreSet = new Set(normalizeNeedles(coreNeedles));
                const resSet = new Set(normalizeNeedles(resonantNeedles).filter(n => !coreSet.has(n)));
                const allNeedles = [...coreSet, ...resSet];
                
                if (!allNeedles.length) return escHtml(src);

                // Sort by length DESC (longer first: "darkness" before "dark")
                allNeedles.sort((a, b) => b.length - a.length);

                // Filter to safe word chars only
                const safeNeedles = allNeedles.filter(n => /^[a-z0-9]+$/i.test(n));
                if (!safeNeedles.length) {
                    return highlightLineHtmlFallback(text, [...coreSet, ...resSet], '');
                }

                // Build word boundary pattern - \\b in regex means word boundary
                const WB = String.fromCharCode(92) + 'b';  // backslash + b = \b for regex
                const patternStr = safeNeedles.map(n => WB + n + WB).join('|');
                let regex;
                try {
                    regex = new RegExp('(' + patternStr + ')', 'gi');
                } catch (e) {
                    return escHtml(src);
                }

                // Find matches
                const ranges = [];
                let match;
                while ((match = regex.exec(src)) !== null && ranges.length < 96) {
                    ranges.push({
                        start: match.index,
                        end: match.index + match[0].length,
                        needle: match[0].toLowerCase(),
                        original: match[0]
                    });
                }

                if (!ranges.length) return escHtml(src);

                // Build HTML with tier-based classes
                let out = '';
                let pos = 0;
                ranges.forEach(r => {
                    if (r.start > pos) out += escHtml(src.slice(pos, r.start));
                    // Invariant IV: Will > Observation in visual hierarchy
                    const cls = coreSet.has(r.needle) ? 'hl-core' : 'hl-resonant';
                    out += '<span class="' + cls + '">' + escHtml(r.original) + '</span>';
                    pos = r.end;
                });
                if (pos < src.length) out += escHtml(src.slice(pos));
                return out;
            }


            // Fallback for needles with special characters
            function highlightLineHtmlFallback(text, needles, primaryNeedle) {
                const src = String(text || '');
                const hs = src.toLowerCase();
                const ns = normalizeNeedles(needles);
                const primary = String(primaryNeedle || '').trim().toLowerCase();
                if (!src || !ns.length) return escHtml(src);

                const ranges = [];
                const MAX_RANGES = 96;
                ns.forEach(n => {
                    if (!n) return;
                    let start = 0;
                    while (start < hs.length && ranges.length < MAX_RANGES) {
                        const idx = hs.indexOf(n, start);
                        if (idx < 0) break;
                        ranges.push({ start: idx, end: idx + n.length, needle: n });
                        start = idx + n.length;
                    }
                });

                if (!ranges.length) return escHtml(src);

                ranges.sort((a, b) => {
                    if (a.start !== b.start) return a.start - b.start;
                    return (b.end - b.start) - (a.end - a.start);
                });

                const kept = [];
                let lastEnd = -1;
                for (let i = 0; i < ranges.length; i++) {
                    const r = ranges[i];
                    if (r.start < lastEnd) continue;
                    kept.push(r);
                    lastEnd = r.end;
                }

                let out = '';
                let pos = 0;
                kept.forEach(r => {
                    if (r.start > pos) out += escHtml(src.slice(pos, r.start));
                    const cls = (primary && r.needle === primary) ? 'hl hl-primary' : 'hl';
                    out += '<span class="' + cls + '">' + escHtml(src.slice(r.start, r.end)) + '</span>';
                    pos = r.end;
                });
                if (pos < src.length) out += escHtml(src.slice(pos));
                return out;
            }

            if (dropZone && fileInput) {
                dropZone.addEventListener('click', () => fileInput.click());
                dropZone.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    dropZone.classList.add('drag-over');
                });
                dropZone.addEventListener('dragleave', () => {
                    dropZone.classList.remove('drag-over');
                });
                dropZone.addEventListener('drop', (e) => {
                    e.preventDefault();
                    dropZone.classList.remove('drag-over');
                    handleDrop(e);
                });
            }

            async function reindexSelectedDoc() {
                if (!selectedDoc) return;
                if (reindexBtn) reindexBtn.disabled = true;
                content.innerHTML = '<div class="loading"><span class="spinner"></span>Reindexing ' + escHtml(selectedDoc) + '...</div>';
                try {
                    const res = await fetch('/api/reindex', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ doc: selectedDoc })
                    });
                    const data = await res.json();
                    if (data.error) {
                        content.innerHTML = '<div class="empty"><h3>Error</h3><p>' + escHtml(data.error) + '</p></div>';
                        return;
                    }
                    try { await loadDocs(); } catch (e) {}
                    if (queryInput.value.trim()) await search();
                    content.innerHTML = '<div class="empty"><h3>✓ Reindexed</h3><p>' + escHtml(selectedDoc) + '</p>'
                        + '<p style="margin-top:10px;color:var(--text-3);font-family:\\'JetBrains Mono\\', ui-monospace;">'
                        + (data.edges || 0) + ' edges rebuilt • removed ' + (data.removed_edges || 0) + '</p></div>';
                } catch (err) {
                    content.innerHTML = '<div class="empty"><h3>Reindex Error</h3><p>' + escHtml(err.message) + '</p></div>';
                } finally {
                    if (reindexBtn) reindexBtn.disabled = !selectedDoc;
                }
            }

            if (reindexBtn) {
                reindexBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    await reindexSelectedDoc();
                });
            }

            const deleteDocBtn = document.getElementById('deleteDocBtn');
            if (deleteDocBtn) {
                deleteDocBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (!selectedDoc) return;
                    if (!confirm(`Delete "${selectedDoc}" from index?\\n\\nThis removes all edges for this document. The file itself is not deleted.`)) return;
                    
                    deleteDocBtn.disabled = true;
                    deleteDocBtn.textContent = 'Deleting...';
                    try {
                        const resp = await fetch('/api/delete', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({doc: selectedDoc})
                        });
                        const data = await resp.json();
                        if (data.success) {
                            setSelectedDoc('');
                            await loadDocs();
                        } else {
                            alert(data.error || 'Delete failed');
                        }
                    } catch (err) {
                        alert('Delete error: ' + err.message);
                    }
                    deleteDocBtn.disabled = false;
                    deleteDocBtn.textContent = 'Delete';
                });
            }

            let docsCache = [];
            let openFolders = new Set();

            function loadOpenFolders() {
                try {
                    const raw = localStorage.getItem('inv_tree_open');
                    if (!raw) return;
                    const parsed = JSON.parse(raw);
                    if (Array.isArray(parsed)) openFolders = new Set(parsed.map(String));
                } catch (e) {}
            }

            function saveOpenFolders() {
                try {
                    localStorage.setItem('inv_tree_open', JSON.stringify(Array.from(openFolders)));
                } catch (e) {}
            }

	        function setSelectedDoc(doc) {
		        selectedDoc = (doc || '').trim();
		        try { localStorage.setItem('inv_doc', selectedDoc); } catch (e) {}

                if (sidebarSelected) {
                    sidebarSelected.textContent = selectedDoc || 'All documents';
                }

                const enabled = !!selectedDoc;
                if (openDocBtn) openDocBtn.disabled = !enabled;
                if (revealDocBtn) revealDocBtn.disabled = !enabled;
                if (vscodeDocBtn) vscodeDocBtn.disabled = !enabled;
                if (deleteDocBtn) deleteDocBtn.disabled = !enabled;

                if (reindexBtn) {
                    reindexBtn.disabled = !enabled;
                    reindexBtn.title = enabled
                        ? ('Reindex ' + selectedDoc + ' (adds provenance)')
                        : 'Select a document to reindex';
                }

                if (docTree) {
                    docTree.querySelectorAll('.tree-row[data-doc]').forEach(el => {
                        el.classList.toggle('active', String(el.dataset.doc || '') === selectedDoc);
                    });
                }

                try {
                    const url = new URL(window.location.href);
                    if (selectedDoc) url.searchParams.set('doc', selectedDoc);
                    else url.searchParams.delete('doc');
                    history.replaceState({}, '', url.toString());
                } catch (e) {}
	        }

            function buildTree(docs) {
                const root = { name: '', path: '', children: new Map(), files: [], edgesTotal: 0, docsTotal: 0 };
                docs.forEach(d => {
                    const full = String(d.doc || '').trim();
                    if (!full) return;
                    const edges = +d.edges || 0;
                    root.edgesTotal += edges;
                    root.docsTotal += 1;
                    const parts = full.split('/').filter(Boolean);
                    let node = root;
                    for (let i = 0; i < parts.length - 1; i++) {
                        const part = parts[i];
                        const nextPath = node.path ? (node.path + '/' + part) : part;
                        if (!node.children.has(part)) {
                            node.children.set(part, { name: part, path: nextPath, children: new Map(), files: [], edgesTotal: 0, docsTotal: 0 });
                        }
                        node = node.children.get(part);
                        node.edgesTotal += edges;
                        node.docsTotal += 1;
                    }
                    node.files.push(d);
                });
                return root;
            }

            function renderTree(node, filterActive) {
                const folders = Array.from(node.children.values()).sort((a, b) => a.name.localeCompare(b.name));
                const files = node.files.slice().sort((a, b) => String(a.doc).localeCompare(String(b.doc)));
                let html = '';

                folders.forEach(folder => {
                    const open = filterActive || openFolders.has(folder.path);
                    const meta = folder.docsTotal ? (folder.docsTotal + ' • ' + folder.edgesTotal) : '';
                    html += `
                        <div class="tree-folder ${open ? 'open' : ''}" data-folder="${escHtml(folder.path)}">
                            <button type="button" class="tree-row" data-kind="folder" data-path="${escHtml(folder.path)}">
                                <span class="chev">›</span>
                                <span class="label">${escHtml(folder.name)}</span>
                                <span class="meta">${meta}</span>
                            </button>
                            <div class="tree-children">
                                ${renderTree(folder, filterActive)}
                            </div>
                        </div>
                    `;
                });

                files.forEach(d => {
                    const full = String(d.doc || '').trim();
                    const parts = full.split('/').filter(Boolean);
                    const name = parts.length ? parts[parts.length - 1] : full;
                    const edges = +d.edges || 0;
                    const active = full === selectedDoc;
                    html += `
                        <button type="button" class="tree-row ${active ? 'active' : ''}" data-kind="file" data-doc="${escHtml(full)}" title="${escHtml(full)}">
                            <span class="chev" style="opacity:0;">›</span>
                            <span class="label">${escHtml(name)}</span>
                            <span class="meta">${edges}</span>
                        </button>
                    `;
                });

                return html;
            }

            function renderDocTree() {
                if (!docTree) return;
                const filter = (docFilter ? docFilter.value : '').trim().toLowerCase();
                const filterActive = !!filter;

                const allDocs = docsCache.slice().sort((a, b) => String(a.doc).localeCompare(String(b.doc)));
                const visibleDocs = filterActive
                    ? allDocs.filter(d => String(d.doc || '').toLowerCase().includes(filter))
                    : allDocs;

	                const totalDocs = allDocs.length;
	                const totalEdges = allDocs.reduce((s, d) => s + (+d.edges || 0), 0);
                    const allMeta = (filterActive ? (visibleDocs.length + '/' + totalDocs) : String(totalDocs)) + ' docs • ' + totalEdges + ' edges';

                let html = '';
	                html += `
	                    <button type="button" class="tree-row ${selectedDoc ? '' : 'active'}" data-kind="all" data-doc="">
	                        <span class="chev" style="opacity:0;">›</span>
	                        <span class="label">All documents</span>
	                        <span class="meta">${escHtml(allMeta)}</span>
	                    </button>
	                `;

                if (visibleDocs.length === 0) {
                    html += `<div class="tree-empty">${filterActive ? 'No matches.' : 'No local documents yet — upload one below.'}</div>`;
                    docTree.innerHTML = html;
                    return;
                }

                const tree = buildTree(visibleDocs);
                html += renderTree(tree, filterActive);
                docTree.innerHTML = html;
            }

	        async function loadDocs() {
	            try {
	                const res = await fetch('/api/docs');
	                const data = await res.json();
	                docsCache = (data.docs || []).slice();
                    renderDocTree();
                    setSelectedDoc(selectedDoc);
	            } catch (e) {
                    if (docTree) {
                        docTree.innerHTML = '<div class="tree-empty">Could not load documents.</div>';
                    }
	            }
	        }
        
        function handleInput(value) {
            clearTimeout(debounceTimer);
            if (value.length < 2) {
                autocomplete.classList.remove('show');
                return;
            }
            debounceTimer = setTimeout(() => fetchSuggestions(value), 200);
        }
        
        async function fetchSuggestions(q) {
            try {
                const res = await fetch('/api/suggest?q=' + encodeURIComponent(q));
                const data = await res.json();
                renderSuggestions(data.suggestions || []);
            } catch (e) {
                autocomplete.classList.remove('show');
            }
        }
        
        function renderSuggestions(suggestions) {
            if (suggestions.length === 0) {
                autocomplete.classList.remove('show');
                return;
            }
            
            let html = '';
            suggestions.forEach(s => {
                html += `
                    <div class="autocomplete-item ${s.source}" onclick='selectSuggestion(${JSON.stringify(s.word)})'>
                        <span>${escHtml(s.word)}</span>
                        <span class="autocomplete-source ${s.source}">${escHtml(s.source)}</span>
                    </div>
                `;
            });
            autocomplete.innerHTML = html;
            autocomplete.classList.add('show');
        }
        
        function selectSuggestion(word) {
            queryInput.value = word;
            autocomplete.classList.remove('show');
            search();
        }
        
        // Hide autocomplete on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-wrapper')) {
                autocomplete.classList.remove('show');
            }
        });
        
	        queryInput.addEventListener('keypress', (e) => {
	            if (e.key === 'Enter') {
	                autocomplete.classList.remove('show');
	                search();
	            }
	        });

                loadOpenFolders();

                if (docFilter) {
                    docFilter.addEventListener('input', () => {
                        renderDocTree();
                    });
                }

                if (docTree) {
                    docTree.addEventListener('click', (e) => {
                        const row = e.target.closest('.tree-row');
                        if (!row) return;
                        const kind = String(row.dataset.kind || '');

                        if (kind === 'folder') {
                            const folder = String(row.dataset.path || '');
                            const wrapper = row.closest('.tree-folder');
                            if (wrapper) wrapper.classList.toggle('open');
                            if (folder) {
                                if (openFolders.has(folder)) openFolders.delete(folder);
                                else openFolders.add(folder);
                                saveOpenFolders();
                            }
                            return;
                        }

                        const doc = String(row.dataset.doc || '');
                        setSelectedDoc(doc);
                        if (queryInput.value.trim()) search();
                    });
                }

                if (openDocBtn) {
                    openDocBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        if (!selectedDoc) return;
                        openDoc('open', selectedDoc, 1, '');
                    });
                }

                if (revealDocBtn) {
                    revealDocBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        if (!selectedDoc) return;
                        openDoc('reveal', selectedDoc, 1, '');
                    });
                }

                if (vscodeDocBtn) {
                    vscodeDocBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        if (!selectedDoc) return;
                        openDoc('vscode', selectedDoc, 1, '');
                    });
                }

            function setMiniLabels(on) {
                miniLabels = !!on;
                try { localStorage.setItem('inv_mini_labels', miniLabels ? '1' : '0'); } catch (e) {}
                const btn = document.getElementById('miniLabelsBtn');
                if (btn) btn.classList.toggle('active', miniLabels);
            }

            function toggleMiniLabels() {
                setMiniLabels(!miniLabels);
                const frame = document.getElementById('miniGraphFrame');
                if (!frame || !frame.src) return;
                try {
                    const url = new URL(frame.src);
                    url.searchParams.set('labels', miniLabels ? '1' : '0');
                    frame.src = url.toString();
                } catch (e) {
                    // ignore
                }
                const full = document.getElementById('fullGraphLink');
                if (full && full.href) {
                    try {
                        const url = new URL(full.href);
                        url.searchParams.set('labels', miniLabels ? '1' : '0');
                        full.href = url.toString();
                    } catch (e) {}
                }
            }
        
	        async function search() {
	            const q = queryInput.value.trim();
	            if (!q) return;

                try {
                    const url = new URL(window.location.href);
                    url.searchParams.set('q', q);
                    if (selectedDoc) url.searchParams.set('doc', selectedDoc);
                    else url.searchParams.delete('doc');
                    history.replaceState({}, '', url.toString());
                } catch (e) {}
            
            searchBtn.disabled = true;
            content.innerHTML = '<div class="loading"><span class="spinner"></span>Searching...</div>';
            
		            try {
		                let url = '/api/locate?q=' + encodeURIComponent(q);
		                if (selectedDoc) {
		                    url += '&doc=' + encodeURIComponent(selectedDoc);
		                }
		                const res = await fetch(url);
	                const data = await res.json();
	                
	                if (data.error) {
	                    content.innerHTML = '<div class="empty"><h3>Error</h3><p>' + escHtml(data.error) + '</p></div>';
	                    return;
                }
                
                renderResults(data);
            } catch (err) {
                content.innerHTML = '<div class="empty"><h3>Connection Error</h3><p>' + escHtml(err.message) + '</p></div>';
            } finally {
                searchBtn.disabled = false;
            }
        }
        
		        let outlineCache = {};

		        async function loadOutline(doc) {
		            const key = String(doc || '');
		            if (!key) return null;
		            if (outlineCache[key]) return outlineCache[key];
		            try {
		                const res = await fetch('/api/structure?doc=' + encodeURIComponent(key));
		                const data = await res.json();
		                outlineCache[key] = data || {};
		                return outlineCache[key];
		            } catch (e) {
		                outlineCache[key] = { error: 'Could not load outline' };
		                return outlineCache[key];
		            }
		        }

		        function renderOutlineHtml(doc, outline) {
		            if (!outline || outline.error) {
		                return '<div class="outline-box"><div class="outline-head"><div class="outline-title">Outline</div></div><div class="outline-body" style="color:var(--danger);font-size:12px;">' + escHtml(outline && outline.error ? outline.error : 'Error') + '</div></div>';
		            }
		            const items = Array.isArray(outline.items) ? outline.items : [];
		            if (!items.length) {
		                return '<div class="outline-box"><div class="outline-head"><div class="outline-title">Outline</div></div><div class="outline-body" style="color:var(--text-2);font-size:12px;">No structure found.</div></div>';
		            }
		            let body = '';
		            items.slice(0, 120).forEach(it => {
		                const line = Number(it.line || 0) || 0;
		                const end = Number(it.end_line || line) || line;
		                const name = String(it.name || '').trim();
		                const typ = String(it.type || '').trim();
		                if (!name || !line) return;
		                body += `
		                    <div class="outline-item" data-doc="${escHtml(doc)}" data-line="${line}">
		                        <div class="outline-name">${escHtml(typ ? (typ + ' ' + name) : name)}</div>
		                        <div class="outline-loc">${escHtml(line + (end && end !== line ? ('-' + end) : ''))}</div>
		                    </div>
		                `;
		            });
		            return `
		                <div class="outline-box">
		                    <div class="outline-head">
		                        <div class="outline-title">Outline</div>
		                        <div style="color:var(--text-3);font-size:11px;font-family:'JetBrains Mono',ui-monospace,monospace;">${escHtml(String(outline.language || outline.suffix || ''))}</div>
		                    </div>
		                    <div class="outline-body">${body}</div>
		                </div>
		            `;
		        }

		        function renderResults(data) {
		            const results = Array.isArray(data.results) ? data.results : [];
		            if (!results.length) {
		                content.innerHTML = '<div class="empty"><h3>No files found</h3><p>Try adding more specific terms from the issue (function/class/module names)</p></div>';
		                return;
		            }

		            const q = String(data.query || queryInput.value || '').trim();
		            const scope = selectedDoc ? selectedDoc : 'all';

		            let html = `
		                <div class="results">
		                    <div class="result-header">
		                        <h2>📄 Files for "${escHtml(q)}"</h2>
		                        <div class="result-meta">
		                            <span>Files: ${results.length}</span>
		                            <span>Scope: ${escHtml(scope)}</span>
		                        </div>
		                    </div>
		            `;

		            results.slice(0, 30).forEach(r => {
		                const doc = String(r.file || '').trim();
		                if (!doc) return;
		                const score = Number(r.score || 0) || 0;
		                const nMatches = Number(r.n_matches || (Array.isArray(r.matching_words) ? r.matching_words.length : 0)) || 0;
		                const words = Array.isArray(r.matching_words) ? r.matching_words : [];
		                const occ = Array.isArray(r.occurrences) ? r.occurrences : [];
		                const docHref = '/doc?doc=' + encodeURIComponent(doc) + (q ? ('&q=' + encodeURIComponent(q)) : '');
		                const graphHref = '/graph3d?doc=' + encodeURIComponent(doc) + '&radius=2';

		                // Render word pills as an "attention spectrum" (Observation Law).
		                const contributions = Array.isArray(r.word_contributions) ? r.word_contributions : [];
		                const uniformThreshold = contributions.length > 0 ? (100 / contributions.length) : 0;
		                const signalWords = Array.isArray(r.signal_words)
		                    ? r.signal_words
		                    : contributions
		                        .filter(wc => Number(wc.percent || 0) >= uniformThreshold)
		                        .map(wc => wc.word);

		                let pills = '';
		                if (contributions.length > 0) {
		                    const signal = contributions.filter(wc => Number(wc.percent || 0) >= uniformThreshold);
		                    const noise = contributions.filter(wc => Number(wc.percent || 0) < uniformThreshold);

		                    const renderPill = (wc, kind) => {
		                        const word = String(wc.word || '').trim();
		                        if (!word) return '';
		                        const pct = Number(wc.percent || 0);
		                        const isDirect = !!wc.is_direct;
		                        const src = String(wc.source_word || '').trim();
		                        const cls = (kind === 'signal') ? 'word-pill signal' : 'word-pill noise';
		                        const titleBits = [`${word}: ${pct.toFixed(1)}%`];
		                        if (!isDirect && src && src !== word) titleBits.push(`from ${src}`);
		                        const srcHtml = (!isDirect && src && src !== word) ? `<span class="src">↝${escHtml(src)}</span>` : '';
		                        return `<span class="${cls}" title="${escHtml(titleBits.join(' • '))}" style="--pct:${pct};">${escHtml(word)}<span class="pct">${escHtml(pct.toFixed(1) + '%')}</span>${srcHtml}</span>`;
		                    };

		                    pills += signal.map(wc => renderPill(wc, 'signal')).join('');
		                    if (noise.length) {
		                        pills += `
		                            <details class="noise-details">
		                                <summary class="noise-summary">+${noise.length} noise</summary>
		                                <div class="noise-list">${noise.map(wc => renderPill(wc, 'noise')).join('')}</div>
		                            </details>
		                        `;
		                    }
		                } else {
		                    // Fallback to simple word list (legacy engine)
		                    (words || []).forEach(w => {
		                        pills += `<span class="word-pill" title="${escHtml(String(w))}">${escHtml(String(w))}</span>`;
		                    });
		                }

		                let occHtml = '';
		                if (occ.length) {
		                    // Two-Tier Gravity: Core = query words (Will), Resonant = expanded (Observation)
		                    const coreWords = q.trim().toLowerCase().split(/\s+/).filter(w => w.length > 0);
		                    const resonantWords = normalizeNeedles(signalWords.length ? signalWords : words);
		                    
		                    let lines = '';
		                    occ.forEach(o => {
		                        const lineNo = Number(o.line || 0) || 0;
		                        const contentText = String(o.content || '').trim();
		                        if (!lineNo) return;
		                        
		                        const matches = Array.isArray(o.matches) ? o.matches : [];
		                        const hasMatch = matches.length > 0;
		                        const lineHtml = highlightLineHtml(contentText, coreWords, resonantWords);
		                        const lineClass = hasMatch ? 'occ-line has-match' : 'occ-line';
		                        lines += `
		                            <div class="${lineClass}" data-doc="${escHtml(doc)}" data-line="${lineNo}">
		                                <div class="occ-no">${escHtml(String(lineNo))}</div>
		                                <div class="occ-text">${lineHtml}</div>
		                            </div>
		                        `;
		                    });
		                    occHtml = `<div class="file-occ">${lines}</div>`;
		                }

		                html += `
		                    <div class="file-card" data-doc="${escHtml(doc)}">
		                        <div class="file-top">
		                            <a class="file-path" href="${docHref}">📄 ${escHtml(doc)}</a>
		                            <div class="file-score">score ${escHtml(Number.isFinite(score) ? score.toFixed(3) : String(score))} • ${escHtml(String(nMatches))} terms</div>
		                        </div>
		                        <div class="file-why">
		                            <span style="color:var(--text-3);">Matched:</span>
		                            ${pills || '<span style="color:var(--text-3);">—</span>'}
		                        </div>
		                        ${occHtml}
		                        <div class="file-actions">
		                            <button class="mini-btn" type="button" data-action="outline" data-doc="${escHtml(doc)}">Outline</button>
		                            <button class="mini-btn" type="button" data-action="vscode" data-doc="${escHtml(doc)}">VS Code</button>
		                            <button class="mini-btn" type="button" data-action="open" data-doc="${escHtml(doc)}">Open</button>
		                            <a class="mini-link" href="${graphHref}" target="_blank">Graph</a>
		                        </div>
		                        <div class="outline-slot" data-doc="${escHtml(doc)}"></div>
		                    </div>
		                `;
		            });

		            html += '</div>';
		            content.innerHTML = html;

		            // File action handlers
		            document.querySelectorAll('button[data-action]').forEach(btn => {
		                btn.addEventListener('click', async (e) => {
		                    e.preventDefault();
		                    e.stopPropagation();
		                    const doc = String(btn.dataset.doc || '');
		                    const action = String(btn.dataset.action || '');
		                    if (!doc) return;
		                    setSelectedDoc(doc);
		                    const card = btn.closest('.file-card');
		                    if (!card) return;

		                    // Prefer first occurrence line if present.
		                    let line = 1;
		                    const firstOcc = card.querySelector('.occ-line');
		                    if (firstOcc && firstOcc.dataset && firstOcc.dataset.line) {
		                        const n = Number(firstOcc.dataset.line || 1) || 1;
		                        line = n;
		                    }

		                    if (action === 'vscode') {
		                        await openDoc('vscode', doc, line, '');
		                        return;
		                    }
		                    if (action === 'open') {
		                        await openDoc('open', doc, line, '');
		                        return;
		                    }
		                    if (action === 'outline') {
		                        const slot = card.querySelector('.outline-slot');
		                        if (!slot) return;
		                        if (slot.dataset && slot.dataset.open === '1') {
		                            slot.innerHTML = '';
		                            slot.dataset.open = '0';
		                            return;
		                        }
		                        slot.dataset.open = '1';
		                        slot.innerHTML = '<div class="loading" style="padding:16px 0;"><span class="spinner"></span>Loading outline...</div>';
		                        const outline = await loadOutline(doc);
		                        slot.innerHTML = renderOutlineHtml(doc, outline);
		                        slot.querySelectorAll('.outline-item').forEach(item => {
		                            item.addEventListener('click', async (ev) => {
		                                ev.preventDefault();
		                                ev.stopPropagation();
		                                const ln = Number(item.dataset.line || 1) || 1;
		                                await openDoc('vscode', doc, ln, '');
		                            });
		                        });
		                        return;
		                    }
		                });
		            });

		            // File card click -> open in VS Code at epicenter
		            document.querySelectorAll('.file-card').forEach(card => {
		                card.style.cursor = 'pointer';
		                card.addEventListener('click', async (e) => {
		                    // Don't open if clicking on buttons/links/details inside
		                    if (e.target.closest('button, a, details, .occ-line')) return;
		                    const doc = String(card.dataset.doc || '');
		                    if (!doc) return;
		                    // Get first occurrence line (epicenter)
		                    const firstOcc = card.querySelector('.occ-line');
		                    const line = firstOcc && firstOcc.dataset.line ? Number(firstOcc.dataset.line) : 1;
		                    await openDoc('vscode', doc, line, '');
		                });
		            });

		            // Occurrence hover/click: preview + open
		            document.querySelectorAll('.occ-line').forEach(el => {
		                el.addEventListener('mouseenter', async () => {
		                    const doc = el.dataset.doc;
		                    const line = el.dataset.line;
		                    const needlesRaw = safeDecode(el.dataset.needles || '');
		                    let needles = [];
		                    if (needlesRaw) {
		                        try { needles = JSON.parse(needlesRaw) || []; } catch (e) { needles = []; }
		                    }
		                    if (!Array.isArray(needles) || !needles.length) {
		                        const word = String(el.dataset.word || '').trim();
		                        if (word) needles = [word];
		                    }
		                    if (doc && line) await showContext(el, doc, line, '', needles, q);
		                });
		                el.addEventListener('click', async (e) => {
		                    e.preventDefault();
		                    e.stopPropagation();
		                    const doc = el.dataset.doc;
		                    const line = Number(el.dataset.line || 1) || 1;
		                    if (doc) {
		                        setSelectedDoc(doc);
		                        await openDoc('vscode', doc, line, '');
		                    }
		                });
		            });
		        }
        
	        let contextCache = {};
	        let contextTooltip = null;
            let ctxHideTimer = null;

            let mentionsCache = {};

            function setupMentions(data) {
                const bodyEl = document.getElementById('mentionsBody');
                const metaEl = document.getElementById('mentionsMeta');
                const scanBtn = document.getElementById('mentionsScanBtn');
                const ctxPanel = document.getElementById('mentionsContext');
                if (!bodyEl || !metaEl) return;

                if (ctxPanel) ctxPanel.style.display = 'none';
                metaEl.textContent = '—';

                const q = String((data && data.query) || '').trim();
                if (!q || q.indexOf(' ') >= 0) {
                    if (scanBtn) scanBtn.style.display = 'none';
                    bodyEl.innerHTML = '<div class="tree-empty">Mentions are available for single-word queries.</div>';
                    return;
                }

                if (scanBtn) {
                    scanBtn.style.display = selectedDoc ? 'none' : 'inline-flex';
                    scanBtn.onclick = async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        await loadMentions(q, '');
                    };
                }

                if (selectedDoc) {
                    bodyEl.innerHTML = '<div class="loading"><span class="spinner"></span>Scanning ' + escHtml(selectedDoc) + '...</div>';
                    loadMentions(q, selectedDoc);
                } else {
                    bodyEl.innerHTML = '<div class="tree-empty">Select a document (left) to see uses, or scan all documents.</div>';
                }
            }

            async function loadMentions(query, doc) {
                const bodyEl = document.getElementById('mentionsBody');
                const metaEl = document.getElementById('mentionsMeta');
                const key = (doc || '') + '|' + String(query || '').toLowerCase();
                if (!bodyEl || !metaEl) return;

                if (mentionsCache[key]) {
                    renderMentions(mentionsCache[key], query);
                    return;
                }

                bodyEl.innerHTML = '<div class="loading"><span class="spinner"></span>Scanning documents...</div>';
                metaEl.textContent = '…';
                try {
                    let url = '/api/mentions?q=' + encodeURIComponent(query);
                    if (doc) url += '&doc=' + encodeURIComponent(doc);
                    const res = await fetch(url);
                    const data = await res.json();
                    mentionsCache[key] = data || {};
                    renderMentions(mentionsCache[key], query);
                } catch (e) {
                    bodyEl.innerHTML = '<div class="tree-empty">Could not scan documents.</div>';
                    metaEl.textContent = '—';
                }
            }

            function renderMentions(data, query) {
                const bodyEl = document.getElementById('mentionsBody');
                const metaEl = document.getElementById('mentionsMeta');
                if (!bodyEl || !metaEl) return;

                const mentions = Array.isArray(data.mentions) ? data.mentions : [];
                const total = (data.total != null) ? Number(data.total) : mentions.length;

                const docsSet = new Set();
                mentions.forEach(m => { if (m && m.doc) docsSet.add(String(m.doc)); });

                if (!mentions.length) {
                    metaEl.textContent = '0 matches';
                    bodyEl.innerHTML = '<div class="tree-empty">No matches in local documents.</div>';
                    return;
                }

                const docsCount = docsSet.size;
                metaEl.textContent = String(total || mentions.length) + ' matches' + (docsCount ? (' • ' + docsCount + ' files') : '');

                const byDoc = {};
                mentions.forEach(m => {
                    const d = String(m.doc || '');
                    if (!d) return;
                    if (!byDoc[d]) byDoc[d] = [];
                    byDoc[d].push(m);
                });

                let html = '';
                Object.keys(byDoc).sort((a, b) => a.localeCompare(b)).forEach(doc => {
                    const rows = (byDoc[doc] || []).slice();
                    rows.sort((a, b) => (Number(a.line) || 0) - (Number(b.line) || 0));
                    const docEsc = escHtml(doc);
                    html += `
                        <div style="margin-bottom:12px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px;">
                                <div style="font-weight:600;font-size:12px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${docEsc}</div>
                                <div style="font-size:11px;color:var(--text-3);font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;flex-shrink:0;">${rows.length} matches</div>
                            </div>
                            <ul class="mentions-list">
                    `;
                    rows.slice(0, 24).forEach(m => {
                        const line = (m.line != null) ? String(m.line) : '?';
                        const ctxHash = m.ctx_hash ? String(m.ctx_hash) : '';
                        html += `
                            <li class="mention-item" data-doc="${docEsc}" data-line="${escHtml(line)}" data-ctx-hash="${escHtml(ctxHash)}" data-word="${encodeURIComponent(query)}">
                                <span class="mention-loc"><span class="mention-file">${docEsc}</span><span class="mention-line">:${escHtml(line)}</span></span>
                                <span class="mention-badge">σ</span>
                            </li>
                        `;
                    });
                    html += '</ul></div>';
                });

                bodyEl.innerHTML = html;

                bodyEl.querySelectorAll('.mention-item').forEach(el => {
                    el.addEventListener('click', async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const doc = String(el.dataset.doc || '');
                        const line = String(el.dataset.line || '');
                        const ctxHash = String(el.dataset.ctxHash || '');
                        const word = safeDecode(el.dataset.word || '') || String(query || '');
                        const q = String(query || '').trim();
                        if (!doc || !line) return;
                        await showMentionContext(doc, line, ctxHash, word, q);
                    });
                });
            }

            async function showMentionContext(doc, line, ctxHash, word, query) {
                const panel = document.getElementById('mentionsContext');
                if (!panel) return;
                panel.style.display = 'block';
                panel.innerHTML = '<div class="loading" style="padding:12px;"><span class="spinner"></span>Loading context...</div>';

                const key = doc + ':' + line + ':' + (ctxHash || '');
                if (!contextCache[key]) {
                    try {
                        let url = '/api/context?doc=' + encodeURIComponent(doc) + '&line=' + encodeURIComponent(line);
                        if (ctxHash) url += '&ctx_hash=' + encodeURIComponent(ctxHash);
                        const res = await fetch(url);
                        const data = await res.json();
                        contextCache[key] = data || {};
                    } catch (e) {
                        contextCache[key] = { error: 'Could not load context', status: 'broken' };
                    }
                }

                const ctx = contextCache[key] || {};
                const status = String(ctx.status || 'unchecked');
                const statusText =
                    status === 'fresh' ? '✓ σ-fresh' :
                    status === 'relocated' ? '↔ σ-relocated' :
                    status === 'broken' ? '✗ σ-broken' :
                    '… unchecked';
                const statusColor =
                    status === 'fresh' ? 'var(--success)' :
                    status === 'relocated' ? 'var(--warning)' :
                    status === 'broken' ? 'var(--danger)' :
                    'var(--text-2)';

                const lineInfo = (ctx.actual_line && ctx.actual_line != ctx.requested_line)
                    ? (ctx.requested_line + '→' + ctx.actual_line)
                    : String(ctx.actual_line || ctx.requested_line || line);

                const anchor = String(ctx.anchor_word || word || '').trim();
                const edgeInfo = (query && anchor && query !== anchor)
                    ? ('Edge: ' + query + ' → ' + anchor)
                    : '';

                function escapeRegExp(s) {
                    return String(s).replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                }
                function highlight(text, needle) {
                    const escaped = escHtml(String(text || ''));
                    const n = String(needle || '').trim();
                    if (!n) return escaped;
                    try {
                        const re = new RegExp(escapeRegExp(n), 'ig');
                        return escaped.replace(re, (m) => '<span style="background:rgba(59,130,246,0.18);border:1px solid rgba(59,130,246,0.28);padding:0 2px;border-radius:4px;">' + m + '</span>');
                    } catch (e) {
                        return escaped;
                    }
                }

                const bodyText = ctx.content
                    ? String(ctx.content)
                    : (ctx.error ? ('Error: ' + String(ctx.error)) : '');

                panel.innerHTML = `
                    <div class="context-panel-header">
                        <div class="context-panel-title">${escHtml('📄 ' + doc + ':' + lineInfo)}</div>
                        <div style="display:flex;gap:8px;flex-shrink:0;">
                            <button class="mini-btn" type="button" data-open="vscode">VS Code</button>
                            <button class="mini-btn" type="button" data-open="open">Open</button>
                            <button class="mini-btn" type="button" data-open="reveal">Reveal</button>
                        </div>
                    </div>
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.06);">
                        <div style="color:${statusColor};font-size:11px;">${escHtml(statusText)}</div>
                        <div style="color:var(--text-3);font-size:11px;">${escHtml(edgeInfo)}</div>
                    </div>
                    <div class="context-panel-body">${highlight(bodyText, anchor || word)}</div>
                `;

                panel.querySelectorAll('button[data-open]').forEach(btn => {
                    btn.onclick = async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const mode = btn.dataset.open;
                        await openDoc(mode, doc, line, ctxHash);
                    };
                });
            }
	        
	        async function showContext(element, doc, line, ctxHash, needles, query) {
	            const MAX_LINES = 18;
	            const key = doc + ':' + line + ':' + (ctxHash || '') + ':' + String(MAX_LINES);

	            if (!contextCache[key]) {
	                try {
	                    let url = '/api/context?doc=' + encodeURIComponent(doc) + '&line=' + encodeURIComponent(line);
	                    url += '&max_lines=' + encodeURIComponent(String(MAX_LINES));
	                    if (ctxHash) url += '&ctx_hash=' + encodeURIComponent(ctxHash);
	                    const res = await fetch(url);
	                    const data = await res.json();
                        contextCache[key] = data || {};
	                } catch (e) {
	                    contextCache[key] = { error: 'Could not load context', status: 'broken' };
	                }
	            }

	            const ctx = contextCache[key];
	            if (!ctx) return;

	            if (!contextTooltip) {
	                contextTooltip = document.createElement('div');
	                contextTooltip.className = 'context-tooltip';
                    contextTooltip.addEventListener('mouseenter', () => {
                        if (ctxHideTimer) clearTimeout(ctxHideTimer);
                    });
                    contextTooltip.addEventListener('mouseleave', () => {
                        hideContextTooltip();
                    });
	                document.body.appendChild(contextTooltip);
	            }

	            const status = String(ctx.status || 'unchecked');
	            const statusText =
	                status === 'fresh' ? '✓ σ-fresh' :
	                status === 'relocated' ? '↔ σ-relocated' :
	                status === 'broken' ? '✗ σ-broken' :
	                '… unchecked';
                const statusColor =
                    status === 'fresh' ? 'var(--success)' :
                    status === 'relocated' ? 'var(--warning)' :
                    status === 'broken' ? 'var(--danger)' :
                    'var(--text-2)';

                const requestedLine = Number(ctx.requested_line || line || 0) || 0;
                const actualLine = Number(ctx.actual_line || requestedLine || line || 0) || 0;
	            const lineInfo = (requestedLine && actualLine && actualLine !== requestedLine)
	                ? (requestedLine + '→' + actualLine)
	                : String(actualLine || requestedLine || line);

                const blockStart = Number(ctx.block_start || 0) || (actualLine || requestedLine || 1);
                const blockEnd = Number(ctx.block_end || 0) || 0;
                const totalLines = Number(ctx.total_lines || 0) || 0;

                const ctxLines = Array.isArray(ctx.lines)
                    ? ctx.lines
                    : (ctx.content ? String(ctx.content).split('\\n') : []);

                const ns = normalizeNeedles(needles);
                const activeIdx = Math.max(0, Math.min(ctxLines.length - 1, (actualLine || requestedLine || 1) - blockStart));
                const activeText = String(ctxLines[activeIdx] || '');
                const primary = pickPrimaryNeedle(activeText, ns) || pickPrimaryNeedle(String(query || ''), ns);

                const pills = [];
                if (primary) pills.push(primary);
                ns.forEach(n => { if (n && n !== primary) pills.push(n); });

                const pillsHtml = pills.length
                    ? ('<div class="tt-pills">' + pills.slice(0, 10).map((w, i) => (
                        '<span class="tt-pill' + (i === 0 && primary ? ' primary' : '') + '" title="' + escHtml(w) + '">' + escHtml(w) + '</span>'
                    )).join('') + '</div>')
                    : '';

                // Two-tier highlighting: query words = core, ns = resonant
                const queryWords = String(query || '').trim().toLowerCase().split(/\s+/).filter(w => w.length > 0);
                
                let rowsHtml = '';
                for (let i = 0; i < ctxLines.length; i++) {
                    const ln = blockStart + i;
                    const isActive = actualLine ? (ln === actualLine) : (ln === requestedLine);
                    const codeHtml = highlightLineHtml(String(ctxLines[i] || ''), queryWords, ns);
                    rowsHtml += `
                        <div class="ctx-row${isActive ? ' active' : ''}">
                            <div class="ctx-no">${escHtml(String(ln))}</div>
                            <div class="ctx-code">${codeHtml}</div>
                        </div>
                    `;
                }

                const rangeText = (blockStart && (blockEnd || ctxLines.length))
                    ? (String(blockStart) + '-' + String(blockEnd || (blockStart + ctxLines.length - 1)) + (totalLines ? (' / ' + totalLines) : ''))
                    : (totalLines ? ('/ ' + totalLines) : '');

	            contextTooltip.innerHTML = `
                    <div class="tt-head">
                        <div style="min-width:0;">
                            <div class="tt-title">${escHtml(doc)}</div>
                            <div class="tt-sub">${escHtml('line ' + lineInfo)}</div>
                            ${pillsHtml}
                        </div>
                        <div style="display:flex;gap:6px;flex-shrink:0;">
                            <button class="mini-btn" type="button" data-open="vscode">VS Code</button>
                            <button class="mini-btn" type="button" data-open="open">Open</button>
                            <button class="mini-btn" type="button" data-open="reveal">Reveal</button>
                        </div>
                    </div>
                    <div class="tt-meta">
                        <div style="color:${statusColor};">${escHtml(statusText)}</div>
                        <div>${escHtml(rangeText)}</div>
                    </div>
                    <div class="tt-body">${rowsHtml || '<div style="color:var(--text-3);font-size:12px;">No context.</div>'}</div>
                `;

                contextTooltip.style.display = 'block';

                const openLine = String(actualLine || requestedLine || line || '1');
                contextTooltip.querySelectorAll('button[data-open]').forEach(btn => {
                    btn.onclick = async (e) => {
                        e.stopPropagation();
                        const mode = btn.dataset.open;
                        await openDoc(mode, doc, openLine, ctxHash);
                    };
                });

                const rect = element.getBoundingClientRect();
                const pad = 12;
                let left = rect.left + 12;
                let top = rect.bottom + 10;
                const w = contextTooltip.offsetWidth || 360;
                const h = contextTooltip.offsetHeight || 240;
                const vw = window.innerWidth || 1000;
                const vh = window.innerHeight || 800;

                if (left + w > vw - pad) left = Math.max(pad, vw - w - pad);
                if (left < pad) left = pad;

                if (top + h > vh - pad) {
                    const above = rect.top - h - 10;
                    top = (above > pad) ? above : Math.max(pad, vh - h - pad);
                }
                if (top < pad) top = pad;

                contextTooltip.style.left = left + 'px';
                contextTooltip.style.top = top + 'px';

	            element.addEventListener('mouseleave', () => {
                    scheduleHideContext(150);
	            }, { once: true });
	        }

            function hideContextTooltip() {
                if (ctxHideTimer) clearTimeout(ctxHideTimer);
                if (contextTooltip) contextTooltip.style.display = 'none';
            }

            function scheduleHideContext(ms) {
                if (ctxHideTimer) clearTimeout(ctxHideTimer);
                ctxHideTimer = setTimeout(() => {
                    if (contextTooltip) contextTooltip.style.display = 'none';
                }, ms || 150);
            }

            async function openDoc(mode, doc, line, ctxHash) {
                try {
                    let url = '/api/open?mode=' + encodeURIComponent(mode || 'open');
                    url += '&doc=' + encodeURIComponent(doc);
                    url += '&line=' + encodeURIComponent(line);
                    if (ctxHash) url += '&ctx_hash=' + encodeURIComponent(ctxHash);
                    await fetch(url);
                } catch (e) {
                    // ignore
                }
            }
        
        function searchWord(word) {
            queryInput.value = word;
            search();
        }
        
        async function uploadFile(input) {
            if (!input.files || !input.files[0]) return;
            
            const file = input.files[0];
            content.innerHTML = '<div class="loading"><span class="spinner"></span>Processing ' + escHtml(file.name) + '...</div>';
            
            try {
                const text = await file.text();
                const res = await fetch('/api/ingest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: file.name, text: text })
                });
                const data = await res.json();
                
		                if (data.error) {
		                    content.innerHTML = '<div class="empty"><h3>Error</h3><p>' + escHtml(data.error) + '</p></div>';
		                } else {
		                    try { await loadDocs(); } catch (e) {}
                            const stored = String(data.filename || file.name || '').trim();
		                    setSelectedDoc(stored);
		                    content.innerHTML = `
		                        <div class="empty">
		                            <h3>✓ Document Added</h3>
		                            <p>${data.anchors} concepts extracted, ${data.edges} connections created</p>
		                            <p style="margin-top: 16px; color: var(--success);">Selected: ${escHtml(stored)}</p>
		                        </div>
		                    `;
		                }
            } catch (err) {
                content.innerHTML = '<div class="empty"><h3>Upload Error</h3><p>' + escHtml(err.message) + '</p></div>';
            }
            
            input.value = '';
        }
        
	        function handleDrop(e) {
	            const files = e.dataTransfer.files;
	            if (files.length > 0) {
	                const fakeInput = { files: files };
	                uploadFile(fakeInput);
	            }
	        }

	        async function init() {
	            const params = new URLSearchParams(window.location.search);
	            const docParam = (params.get('doc') || '').trim();
	            let stored = '';
	            try { stored = (localStorage.getItem('inv_doc') || '').trim(); } catch (e) {}

                let storedLabels = '';
                try { storedLabels = (localStorage.getItem('inv_mini_labels') || '').trim(); } catch (e) {}
                setMiniLabels(storedLabels !== '0');
	            
	            setSelectedDoc(docParam || stored || '');
	            await loadDocs();
	            
	            const qParam = (params.get('q') || '').trim();
	            if (qParam) {
	                queryInput.value = qParam;
	                search();
	            }
	        }
	        
	        init();
	    </script>
	</body>
	</html>
	'''
