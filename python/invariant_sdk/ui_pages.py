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
                justify-content: space-between;
                align-items: flex-start;
                gap: 12px;
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
                margin-top: 6px;
                color: var(--text-2);
                font-size: 12px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 240px;
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
                                <input type="file" id="fileInput" accept=".txt,.md" onchange="uploadFile(this)">
                                <p>📄 Drag file here or click to upload</p>
                                <p style="font-size: 12px; color: var(--text-3); margin-top: 8px;">
                                    Supports .txt and .md files (up to 500 unique words will be indexed)
                                </p>
                            </div>
                        </div>
                    </aside>

                    <main class="main">
		                <p class="subtitle" style="margin-top: 4px;">Semantic Knowledge Explorer</p>
                        <div class="hint">
                            Select a document to filter σ-edges. Hover <span style="color:var(--success);font-weight:600;">σ</span> results to preview source context and open the file.
                        </div>

                <!-- Mode Tabs -->
                <div class="mode-tabs">
                    <button class="mode-tab active" data-mode="search" onclick="setMode('search')">Explore</button>
                    <button class="mode-tab" data-mode="verify" onclick="setMode('verify')">Verify</button>
                    <button class="mode-tab" data-mode="conflicts" onclick="setMode('conflicts')">Conflicts</button>
                </div>

                <!-- Legend -->
                <div class="legend">
                    <div class="legend-item"><span class="legend-dot sigma"></span> σ = observation (documents)</div>
                    <div class="legend-item"><span class="legend-dot alpha"></span> α = context (crystal)</div>
                    <div class="legend-item"><span class="legend-dot lambda"></span> λ = navigation (ghost)</div>
                    <div class="legend-item"><span class="legend-dot eta"></span> η = hypothesis (unverified)</div>
                </div>
		        
		        <!-- Mode: Search -->
                <div class="mode-panel active" id="panel-search">
		            <div class="search-form">
	                    <div class="search-wrapper">
	                        <input type="text" class="search-input" id="query" 
	                               placeholder="Type to search... (suggestions will appear)" autofocus
                               oninput="handleInput(this.value)" autocomplete="off">
                        <div class="autocomplete" id="autocomplete"></div>
                    </div>
                    <button class="btn" id="searchBtn" onclick="search()">Search</button>
                </div>
        
                <div id="content">
                    <div class="empty">
                        <h3>Enter a word to explore</h3>
                        <p>See semantic connections from your documents + global knowledge</p>
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
	                let url = '/api/search?q=' + encodeURIComponent(q);
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
        
	        function renderResults(data) {
	            if (!data.neighbors || data.neighbors.length === 0) {
	                content.innerHTML = '<div class="empty"><h3>No connections found</h3><p>Try a different word</p></div>';
	                return;
	            }
	            
		            const localCount = data.neighbors.filter(n => n.source === 'local').length;
		            const globalCount = data.neighbors.length - localCount;
                    const ringCounts = { sigma: 0, lambda: 0, eta: 0, alpha: 0 };
                    data.neighbors.forEach(n => {
                        const r = String(n.ring || (n.source === 'local' ? 'sigma' : 'alpha'));
                        if (ringCounts[r] == null) ringCounts[r] = 0;
                        ringCounts[r] += 1;
                    });
                    const ringParts = [];
                    if (ringCounts.sigma) ringParts.push('σ ' + ringCounts.sigma);
                    if (ringCounts.lambda) ringParts.push('λ ' + ringCounts.lambda);
                    if (ringCounts.eta) ringParts.push('η ' + ringCounts.eta);
                    ringParts.push('α ' + ringCounts.alpha);
                    const ringSummary = ringParts.join(' • ');
		            const focus = Array.isArray(data.atoms) && data.atoms.length ? data.atoms[0] : '';
	            
	            let miniSrc = '/graph3d?embed=1';
	            if (selectedDoc) miniSrc += '&doc=' + encodeURIComponent(selectedDoc);
	            if (focus) miniSrc += '&focus=' + encodeURIComponent(focus) + '&radius=1&max_nodes=180';
                miniSrc += '&labels=' + (miniLabels ? '1' : '0');
	            
	            let fullHref = '/graph3d';
	            const qs = [];
	            if (selectedDoc) qs.push('doc=' + encodeURIComponent(selectedDoc));
	            if (focus) qs.push('focus=' + encodeURIComponent(focus) + '&radius=2');
                qs.push('labels=' + (miniLabels ? '1' : '0'));
	            if (qs.length) fullHref += '?' + qs.join('&');
	            
	            let html = `
	                <div class="results">
	                    <div class="result-header">
	                        <h2>
	                            ${data.phase === 'solid' ? '◆' : '○'} "${escHtml(data.query)}"
	                            <span class="phase-badge ${data.phase}">${data.phase === 'solid' ? 'ANCHOR' : 'common'}</span>
	                        </h2>
	                        <div class="result-meta">
	                            <span>Mode: ${data.mode}</span>
	                            <span>Mass: ${(data.mass || 0).toFixed(2)}</span>
                                <span>Doc: ${selectedDoc ? escHtml(selectedDoc) : 'all'}</span>
	                            <span>${ringSummary}</span>
	                        </div>
	                    </div>
	                    <div class="graph-preview">
	                        <div class="graph-preview-header">
	                            <span>3D molecule (overlay: ${selectedDoc ? escHtml(selectedDoc) : 'all'})</span>
                                <div class="graph-preview-actions">
                                    <button class="mini-btn ${miniLabels ? 'active' : ''}" id="miniLabelsBtn" onclick="toggleMiniLabels()">Labels</button>
	                                <a id="fullGraphLink" href="${fullHref}" target="_blank">Open full</a>
                                </div>
	                        </div>
	                        <iframe id="miniGraphFrame" class="graph-frame" src="${miniSrc}"></iframe>
	                    </div>
                        <div class="mentions" id="mentions">
                            <div class="mentions-header">
                                <div class="mentions-title">Mentions (σ)</div>
                                <div class="mentions-meta" id="mentionsMeta">—</div>
                            </div>
                            <div class="mentions-body">
                                <div class="mentions-actions">
                                    <button class="mini-btn" id="mentionsScanBtn" type="button">Scan all docs</button>
                                    <span style="color:var(--text-3);font-size:12px;">Click a mention to preview context</span>
                                </div>
                                <div id="mentionsBody"><div class="tree-empty">Select a document (left) to see uses, or scan all documents.</div></div>
                                <div id="mentionsContext" class="context-panel" style="display:none;"></div>
                            </div>
                        </div>
	            `;
            
            // Group by orbit (physics from INVARIANTS.md)
            const core = data.neighbors.filter(n => Math.abs(n.weight) >= 0.7);
            const near = data.neighbors.filter(n => Math.abs(n.weight) >= 0.5 && Math.abs(n.weight) < 0.7);
            const far = data.neighbors.filter(n => Math.abs(n.weight) < 0.5);
            
	            const renderGroup = (items, title, color) => {
	                if (items.length === 0) return '';
	                let group = `<div class="orbit-group"><h4 style="color:${color}">${title} (${items.length})</h4><ul class="result-list">`;
	                items.slice(0, 15).forEach(n => {
	                    const isLocal = n.source === 'local';
	                    const label = n.label || 'unknown';
	                    const labelText = escHtml(label);
                        const labelKey = encodeURIComponent(label);
	                    const weight = (n.weight * 100).toFixed(0) + '%';
                        const ring = String(n.ring || (isLocal ? 'sigma' : 'alpha'));
                        const ringLabel =
                            ring === 'sigma' ? 'σ' :
                            ring === 'lambda' ? 'λ' :
                            ring === 'eta' ? 'η' :
                            'α';
                        const ringTitle =
                            ring === 'sigma' ? 'σ: documentary observation (can prove with provenance)' :
                            ring === 'lambda' ? 'λ: derived/ghost edge (navigation, not proof)' :
                            ring === 'eta' ? 'η: hypothesis (unverified)' :
                            'α: global crystal context (not proof)';
                        const badgeClass =
                            ring === 'sigma' ? 'badge-sigma' :
                            ring === 'lambda' ? 'badge-lambda' :
                            ring === 'eta' ? 'badge-eta' :
                            'badge-alpha';
	                    const badge = `<span class="badge ${badgeClass}" title="${escHtml(ringTitle)}">${ringLabel}</span>`;
	                    
	                    // Build location info with a non-truncated line number.
	                    const docStr = n.doc ? String(n.doc) : '';
	                    const lineStr = (n.line != null) ? String(n.line) : '';
	                    let locHtml = '';
	                    if (docStr && lineStr) {
	                        locHtml = `<span class="result-loc" title="${escHtml(docStr + ':' + lineStr)}"><span class="loc-file">${escHtml(docStr)}</span><span class="loc-line">:${escHtml(lineStr)}</span></span>`;
	                    } else if (docStr) {
	                        locHtml = `<span class="result-loc" title="${escHtml(docStr)}">${escHtml(docStr)}</span>`;
	                    }
	                    
	                    let tooltip = ringTitle;
	                    
	                    // Add data attributes for lazy context loading
	                    const dataAttrs = (n.doc && n.line) 
	                        ? `data-doc="${escHtml(n.doc)}" data-line="${n.line}" data-ctx-hash="${escHtml(n.ctx_hash || '')}"`
	                        : '';
	                    
	                    group += `
	                        <li class="result-item ${isLocal ? 'local' : ''} ring-${ring}" 
                                data-word="${labelKey}"
	                            title="${escHtml(tooltip)}"
	                            ${dataAttrs}>
	                            <span class="result-word">${labelText}</span>
                                ${locHtml}
	                            <span class="result-weight">${weight}</span>
	                            ${badge}
	                        </li>
	                    `;
	                });
	                group += '</ul></div>';
	                return group;
	            };
            
            html += renderGroup(core, '◼ Core (synonyms, 70%+)', 'var(--accent)');
            html += renderGroup(near, '◻ Near (associations, 50-70%)', 'var(--text-2)');
            html += renderGroup(far, '○ Far (context, <50%)', 'var(--text-3)');
            
	            html += '</div>';
	            content.innerHTML = html;

                // Click handlers (avoid inline JS quoting issues)
                document.querySelectorAll('.result-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const w = safeDecode(item.dataset.word || '');
                        if (w) searchWord(w);
                    });
                });
	            
		            // Add hover handlers for lazy context loading
		            document.querySelectorAll('.result-item.local').forEach(item => {
		                item.addEventListener('mouseenter', async (e) => {
		                    const doc = item.dataset.doc;
		                    const line = item.dataset.line;
	                        const ctxHash = item.dataset.ctxHash;
                                const wEl = item.querySelector('.result-word');
	                            const word = safeDecode(item.dataset.word || '') || (wEl ? (wEl.textContent || '') : '');
                            const query = String(data.query || queryInput.value || '').trim();
		                    if (doc && line) {
		                        await showContext(item, doc, line, ctxHash, word, query);
		                    }
		                });
		            });

                    // Mentions: where this concept appears in σ sources (doc/line).
                    setupMentions(data);
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
	        
	        async function showContext(element, doc, line, ctxHash, word, query) {
	            const key = doc + ':' + line + ':' + (ctxHash || '');
	            
	            // Check cache
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
	            
	            const ctx = contextCache[key];
	            if (!ctx) return;
            
            // Create or update tooltip
	            if (!contextTooltip) {
	                contextTooltip = document.createElement('div');
	                contextTooltip.className = 'context-tooltip';
	                contextTooltip.style.cssText = `
	                    position: fixed;
	                    background: var(--surface);
	                    border: 1px solid var(--border);
	                    border-radius: 8px;
	                    padding: 12px 16px;
	                    max-width: 500px;
	                    max-height: 200px;
	                    overflow: auto;
	                    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
	                    font-size: 12px;
	                    color: var(--text);
	                    white-space: pre-wrap;
	                    word-break: break-word;
	                    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
	                    z-index: 9999;
	                    pointer-events: auto;
	                `;
                    contextTooltip.addEventListener('mouseenter', () => {
                        if (ctxHideTimer) clearTimeout(ctxHideTimer);
                    });
                    contextTooltip.addEventListener('mouseleave', () => {
                        hideContextTooltip();
                    });
	                document.body.appendChild(contextTooltip);
	            }
            
	            // Position tooltip
	            const rect = element.getBoundingClientRect();
	            contextTooltip.style.left = (rect.left + 20) + 'px';
	            contextTooltip.style.top = (rect.bottom + 8) + 'px';
	            
	            // Show content with header
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
                        // Standard JS escape for use inside RegExp
                        // Note: double-escaped so the generated HTML contains `/[.*+?^${}()|[\\]\\\\]/g` correctly.
                        return String(s).replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                    }

                    function highlightContent(text, needle) {
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
                    const searched = Array.isArray(ctx.searched) ? ctx.searched.slice(0, 6) : [];
                    const searchedHtml = searched.length
                        ? ('<div style=\"margin-top:10px;color:var(--text-3);font-size:11px;\">Tried:\\n' + escHtml(searched.join('\\n')) + '</div>')
                        : '';

	                const headerHtml = `
	                    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:8px;">
	                        <div style="min-width:0;">
                                <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                                    ${escHtml(anchor || word || 'σ-context')}
                                </div>
                                <div style="color:var(--text-3);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                                    ${escHtml('📄 ' + doc + ':' + lineInfo)}
                                </div>
	                        </div>
	                        <div style="display:flex;gap:6px;flex-shrink:0;">
	                            <button type="button" data-open="vscode" style="background:rgba(255,255,255,0.03);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:4px 8px;font-size:11px;cursor:pointer;">VS Code</button>
	                            <button type="button" data-open="open" style="background:rgba(255,255,255,0.03);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:4px 8px;font-size:11px;cursor:pointer;">Open</button>
	                            <button type="button" data-open="reveal" style="background:rgba(255,255,255,0.03);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:4px 8px;font-size:11px;cursor:pointer;">Reveal</button>
	                        </div>
	                    </div>
	                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px;">
                            <div style="color:${statusColor};font-size:11px;">${escHtml(statusText)}</div>
                            <div style="color:var(--text-3);font-size:11px;">${escHtml(edgeInfo)}</div>
                        </div>
	                `;

	                const bodyHtml = `<div style="white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;line-height:1.45;">${highlightContent(bodyText, anchor || word)}</div>${searchedHtml}`;
		            contextTooltip.innerHTML = headerHtml + bodyHtml;
		            contextTooltip.style.display = 'block';

                contextTooltip.querySelectorAll('button[data-open]').forEach(btn => {
                    btn.onclick = async (e) => {
                        e.stopPropagation();
                        const mode = btn.dataset.open;
                        await openDoc(mode, doc, line, ctxHash);
                    };
                });
	            
	            // Hide on mouse leave
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
