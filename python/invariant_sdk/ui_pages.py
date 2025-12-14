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

        .toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 14px;
        }

        .toolbar-left {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .toolbar-label {
            font-size: 12px;
            color: var(--text-3);
        }

        .doc-picker {
            margin-bottom: 18px;
        }

        .doc-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 10px;
            max-height: 240px;
            overflow: auto;
            padding-right: 6px;
        }

        .doc-item {
            text-align: left;
            padding: 10px 12px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            cursor: pointer;
        }
        
        .doc-item:hover { border-color: rgba(59, 130, 246, 0.6); background: rgba(59, 130, 246, 0.06); }

        .doc-item.active {
            border-color: var(--accent);
            box-shadow: 0 0 0 1px rgba(59,130,246,0.25) inset;
        }

        .doc-item .name { font-weight: 600; font-size: 13px; }
        .doc-item .meta { color: var(--text-3); font-size: 11px; margin-top: 4px; font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }

        .doc-empty {
            grid-column: 1 / -1;
            color: var(--text-2);
            font-size: 12px;
            padding: 10px 12px;
            border: 1px dashed var(--border-2);
            border-radius: 10px;
            background: rgba(255,255,255,0.03);
        }

        .doc-link {
            font-size: 12px;
            color: var(--accent);
            text-decoration: none;
        }

	        .doc-link:hover { text-decoration: underline; }

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
        
        .result-item.local {
            border-left: 3px solid var(--success);
        }
        
        .result-word {
            font-weight: 500;
            font-size: 14px;
        }
        
        .result-weight {
            color: var(--text-2);
            font-size: 12px;
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        
        .badge {
            font-size: 10px;
            padding: 3px 6px;
            border-radius: 4px;
            font-weight: 600;
        }
        
        .badge-local {
            background: rgba(34, 197, 94, 0.15);
            color: var(--success);
        }
        
        .badge-global {
            background: var(--accent-dim);
            color: var(--accent);
        }
        
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
            margin-top: 40px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
        }
        
        .doc-section h3 {
            font-size: 14px;
            color: var(--text-2);
            margin-bottom: 16px;
        }
        
        .doc-upload {
            border: 1px dashed var(--border-2);
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: border-color 0.2s;
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
		        <p class="subtitle" style="margin-top: 4px;">Semantic Knowledge Explorer</p>
	        
	        <div class="toolbar">
		            <div class="toolbar-left">
		                <span class="toolbar-label">Documents</span>
		                <a id="docLink" class="doc-link" href="/doc">Open</a>
		                <button id="reindexBtn" class="doc-action" type="button" disabled>Reindex</button>
		            </div>
		        </div>

	            <div class="doc-picker">
	                <div id="docList" class="doc-list"></div>
	            </div>

                <div class="hint">
                    Select a document to filter σ-edges. Hover <span style="color:var(--success);font-weight:600;">📄 σ</span> results to preview source context and open the file.
                </div>
		        
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
        
        <div class="doc-section">
            <h3>ADD DOCUMENT</h3>
            <div class="doc-upload" id="dropZone">
                <input type="file" id="fileInput" accept=".txt,.md" onchange="uploadFile(this)">
                <p>📄 Drag file here or click to upload</p>
                <p style="font-size: 12px; color: var(--text-3); margin-top: 8px;">
                    Supports .txt and .md files (up to 500 unique words will be indexed)
                </p>
            </div>
        </div>
    </div>
    
		    <script>
	        const queryInput = document.getElementById('query');
	        const searchBtn = document.getElementById('searchBtn');
	        const content = document.getElementById('content');
		        const autocomplete = document.getElementById('autocomplete');
		        const docList = document.getElementById('docList');
		        const docLink = document.getElementById('docLink');
                const reindexBtn = document.getElementById('reindexBtn');
	            const dropZone = document.getElementById('dropZone');
	            const fileInput = document.getElementById('fileInput');
	        
	        let selectedDoc = '';
            let miniLabels = true;
	        
	        let debounceTimer;

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

	        function setSelectedDoc(doc) {
		            selectedDoc = (doc || '').trim();
		            try { localStorage.setItem('inv_doc', selectedDoc); } catch (e) {}
		            if (docLink) {
		                docLink.href = selectedDoc ? ('/doc?doc=' + encodeURIComponent(selectedDoc)) : '/doc';
		            }
                    if (reindexBtn) {
                        reindexBtn.disabled = !selectedDoc;
                        reindexBtn.title = selectedDoc ? ('Reindex ' + selectedDoc + ' (adds provenance)') : 'Select a document to reindex';
                    }
                if (docList) {
                    docList.querySelectorAll('.doc-item').forEach(el => {
                        el.classList.toggle('active', safeDecode(el.dataset.doc || '') === selectedDoc);
                    });
                }
                try {
                    const url = new URL(window.location.href);
                    if (selectedDoc) url.searchParams.set('doc', selectedDoc);
                    else url.searchParams.delete('doc');
                    history.replaceState({}, '', url.toString());
                } catch (e) {}
	        }

	        async function loadDocs() {
	            try {
	                const res = await fetch('/api/docs');
	                const data = await res.json();
	                const docs = (data.docs || []).slice();
                    if (!docList) return;
                    docs.sort((a, b) => (b.edges || 0) - (a.edges || 0) || String(a.doc).localeCompare(String(b.doc)));
                    const totalEdges = docs.reduce((s, d) => s + (+d.edges || 0), 0);

                    let html = '';
                    html += `
                        <button type="button" class="doc-item ${selectedDoc ? '' : 'active'}" data-doc="">
                            <div class="name">All documents</div>
                            <div class="meta">${docs.length} docs • ${totalEdges} edges</div>
                        </button>
                    `;

                    if (docs.length === 0) {
                        html += `<div class="doc-empty">No local documents yet — upload one below to build an overlay.</div>`;
                        docList.innerHTML = html;
                        setSelectedDoc(selectedDoc);
                        return;
                    }

                    docs.forEach(d => {
                        const name = String(d.doc || '');
                        const key = encodeURIComponent(name);
                        const edges = +d.edges || 0;
                        const nodes = +d.nodes || 0;
                        const active = name === selectedDoc ? ' active' : '';
                        html += `
                            <button type="button" class="doc-item${active}" data-doc="${key}">
                                <div class="name">${escHtml(name)}</div>
                                <div class="meta">${edges} edges • ${nodes} nodes</div>
                            </button>
                        `;
                    });
                    docList.innerHTML = html;
                    setSelectedDoc(selectedDoc);
	            } catch (e) {
	                // ignore
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

            if (docList) {
                docList.addEventListener('click', (e) => {
                    const btn = e.target.closest('.doc-item');
                    if (!btn) return;
                    setSelectedDoc(safeDecode(btn.dataset.doc || ''));
                    if (queryInput.value.trim()) search();
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
	                            <span>${localCount} local, ${globalCount} global</span>
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
	                    const badge = isLocal 
	                        ? '<span class="badge badge-local" title="From local documents (σ-fact)">📄 σ</span>'
	                        : '<span class="badge badge-global" title="From global crystal (α-context)">🌐 α</span>';
	                    
	                    // Build location info with line number
	                    let locInfo = '';
	                    if (n.doc) {
	                        locInfo = n.doc;
	                        if (n.line) {
	                            locInfo += ':' + n.line;
	                        }
	                    }
	                    
	                    let tooltip = isLocal
                            ? ((n.doc && n.line) ? 'Hover for context' : 'σ-edge (no provenance yet)')
                            : 'α-context from global crystal';
	                    
	                    // Add data attributes for lazy context loading
	                    const dataAttrs = (n.doc && n.line) 
	                        ? `data-doc="${escHtml(n.doc)}" data-line="${n.line}" data-ctx-hash="${escHtml(n.ctx_hash || '')}"`
	                        : '';
	                    
	                    group += `
	                        <li class="result-item ${isLocal ? 'local' : ''}" 
                                data-word="${labelKey}"
	                            title="${escHtml(tooltip)}"
	                            ${dataAttrs}>
	                            <span class="result-word">${labelText}</span>
	                            <span class="result-weight">${weight}${locInfo ? ' • ' + escHtml(locInfo) : ''}</span>
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
                            const word = safeDecode(item.dataset.word || '') || (item.querySelector('.result-word')?.textContent || '');
                            const query = String(data.query || queryInput.value || '').trim();
		                    if (doc && line) {
		                        await showContext(item, doc, line, ctxHash, word, query);
		                    }
		                });
		            });
	        }
        
	        let contextCache = {};
	        let contextTooltip = null;
            let ctxHideTimer = null;
	        
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
