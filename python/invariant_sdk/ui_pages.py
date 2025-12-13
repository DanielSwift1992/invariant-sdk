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
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            min-height: 100vh;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        h1 {
            font-size: 28px;
            margin-bottom: 8px;
            color: #58a6ff;
        }
        
        .subtitle {
            color: #8b949e;
            margin-bottom: 32px;
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
            color: #8b949e;
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
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            color: #e6edf3;
            cursor: pointer;
        }

        .doc-item:hover { border-color: #58a6ff; }

        .doc-item.active {
            border-color: #58a6ff;
            box-shadow: 0 0 0 1px rgba(88,166,255,0.25) inset;
        }

        .doc-item .name { font-weight: 600; font-size: 13px; }
        .doc-item .meta { color: #8b949e; font-size: 11px; margin-top: 4px; }

        .doc-empty {
            grid-column: 1 / -1;
            color: #8b949e;
            font-size: 12px;
            padding: 10px 12px;
            border: 1px dashed #30363d;
            border-radius: 10px;
            background: #0d1117;
        }

        .doc-link {
            font-size: 12px;
            color: #58a6ff;
            text-decoration: none;
        }

        .doc-link:hover { text-decoration: underline; }

        .graph-preview {
            margin-top: 16px;
            border: 1px solid #21262d;
            border-radius: 10px;
            overflow: hidden;
            background: #0d1117;
        }

        .graph-preview-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: #161b22;
            border-bottom: 1px solid #21262d;
            font-size: 12px;
            color: #8b949e;
        }

        .graph-preview-actions {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .mini-btn {
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            padding: 4px 8px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
        }

        .mini-btn.active { border-color: #58a6ff; }

        .graph-preview-header a {
            color: #58a6ff;
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
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            color: #e6edf3;
        }
        
        .search-input:focus {
            outline: none;
            border-color: #58a6ff;
        }
        
        .btn {
            padding: 14px 24px;
            font-size: 14px;
            font-weight: 500;
            background: #238636;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        
        .btn:hover { background: #2ea043; }
        .btn:disabled { background: #21262d; cursor: wait; }
        
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
            background: #161b22;
            border: 1px solid #30363d;
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
            background: #21262d;
        }
        
        .autocomplete-item.local {
            border-left: 3px solid #3fb950;
        }
        
        .autocomplete-item.global {
            border-left: 3px solid #58a6ff;
        }
        
        .autocomplete-source {
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .autocomplete-source.local {
            background: rgba(63, 185, 80, 0.2);
            color: #3fb950;
        }
        
        .autocomplete-source.global {
            background: rgba(88, 166, 255, 0.2);
            color: #58a6ff;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #8b949e;
        }
        
        .spinner {
            display: inline-block;
            width: 24px;
            height: 24px;
            border: 3px solid #30363d;
            border-top: 3px solid #58a6ff;
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
            background: #161b22;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid #21262d;
        }
        
        .result-header {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #21262d;
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
            background: rgba(88, 166, 255, 0.2);
            color: #58a6ff;
        }
        
        .phase-badge.gas {
            background: rgba(139, 148, 158, 0.2);
            color: #8b949e;
        }
        
        .result-meta {
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: #8b949e;
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
            background: #0d1117;
            cursor: pointer;
            transition: background 0.2s;
            border: 1px solid transparent;
        }
        
        .result-item:hover {
            background: #21262d;
            border-color: #30363d;
        }
        
        .result-item.local {
            border-left: 3px solid #3fb950;
        }
        
        .result-word {
            font-weight: 500;
            font-size: 14px;
        }
        
        .result-weight {
            color: #8b949e;
            font-size: 12px;
        }
        
        .badge {
            font-size: 10px;
            padding: 3px 6px;
            border-radius: 4px;
            font-weight: 600;
        }
        
        .badge-local {
            background: rgba(63, 185, 80, 0.2);
            color: #3fb950;
        }
        
        .badge-global {
            background: rgba(88, 166, 255, 0.2);
            color: #58a6ff;
        }
        
        .orbit-group {
            margin-top: 20px;
        }
        
        .orbit-group h4 {
            font-size: 13px;
            margin-bottom: 12px;
            color: #8b949e;
        }
        
        .empty {
            text-align: center;
            padding: 60px 20px;
            color: #8b949e;
        }
        
        .doc-section {
            margin-top: 40px;
            padding-top: 24px;
            border-top: 1px solid #21262d;
        }
        
        .doc-section h3 {
            font-size: 14px;
            color: #8b949e;
            margin-bottom: 16px;
        }
        
        .doc-upload {
            border: 2px dashed #30363d;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        
        .doc-upload:hover {
            border-color: #58a6ff;
        }
        
        .doc-upload input {
            display: none;
        }
        
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 8px 20px;
            background: #161b22;
            border-top: 1px solid #21262d;
            font-size: 12px;
            color: #8b949e;
            display: flex;
            justify-content: space-between;
        }
        
        .status-local {
            color: #3fb950;
        }
    </style>
</head>
<body>
	    <div class="container">
	        <h1>◆ Invariant</h1>
	        <p class="subtitle">Semantic Knowledge Explorer</p>
	        
	        <div class="toolbar">
	            <div class="toolbar-left">
	                <span class="toolbar-label">Documents</span>
	                <a id="docLink" class="doc-link" href="/doc">Open</a>
	            </div>
	        </div>

            <div class="doc-picker">
                <div id="docList" class="doc-list"></div>
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
            <div class="doc-upload" id="dropZone" onclick="document.getElementById('fileInput').click()"
                 ondragover="event.preventDefault(); this.style.borderColor='#58a6ff'; this.style.background='#161b22'"
                 ondragleave="this.style.borderColor='#30363d'; this.style.background=''"
                 ondrop="event.preventDefault(); this.style.borderColor='#30363d'; this.style.background=''; handleDrop(event)">
                <input type="file" id="fileInput" accept=".txt,.md" onchange="uploadFile(this)">
                <p>📄 Drag file here or click to upload</p>
                <p style="font-size: 12px; color: #8b949e; margin-top: 8px;">
                    Supports .txt and .md files (up to 500 unique words will be indexed)
                </p>
            </div>
        </div>
    </div>
    
	    <div class="status-bar">
	        <span>Crystal: <strong>$$CRYSTAL_ID$$</strong></span>
	        <span><a href="/doc" style="color:#58a6ff">📄 Docs</a> | <a href="/graph3d" style="color:#58a6ff">🧬 3D</a></span>
	        <span class="status-local">$$OVERLAY_STATUS$$</span>
	    </div>

	    <script>
	        const queryInput = document.getElementById('query');
	        const searchBtn = document.getElementById('searchBtn');
	        const content = document.getElementById('content');
	        const autocomplete = document.getElementById('autocomplete');
	        const docList = document.getElementById('docList');
	        const docLink = document.getElementById('docLink');
	        
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

	        function setSelectedDoc(doc) {
	            selectedDoc = (doc || '').trim();
	            try { localStorage.setItem('inv_doc', selectedDoc); } catch (e) {}
	            if (docLink) {
	                docLink.href = selectedDoc ? ('/doc?doc=' + encodeURIComponent(selectedDoc)) : '/doc';
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
                    const labelArg = JSON.stringify(label);
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
                    
                    // Build tooltip with snippet
                    let tooltip = isLocal ? 'Hover for context' : 'α-context from global crystal';
                    
                    // Add data attributes for lazy context loading
                    const dataAttrs = (n.doc && n.line) 
                        ? `data-doc="${escHtml(n.doc)}" data-line="${n.line}"`
                        : '';
                    
                    group += `
                        <li class="result-item ${isLocal ? 'local' : ''}" 
                            onclick="searchWord(${labelArg})"
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
            
            html += renderGroup(core, '◼ Core (synonyms, 70%+)', '#58a6ff');
            html += renderGroup(near, '◻ Near (associations, 50-70%)', '#8b949e');
            html += renderGroup(far, '○ Far (context, <50%)', '#484f58');
            
            html += '</div>';
            content.innerHTML = html;
            
            // Add hover handlers for lazy context loading
            document.querySelectorAll('.result-item.local').forEach(item => {
                item.addEventListener('mouseenter', async (e) => {
                    const doc = item.dataset.doc;
                    const line = item.dataset.line;
                    if (doc && line) {
                        await showContext(item, doc, line);
                    }
                });
            });
        }
        
        let contextCache = {};
        let contextTooltip = null;
        
        async function showContext(element, doc, line) {
            const key = doc + ':' + line;
            
            // Check cache
            if (!contextCache[key]) {
                try {
                    const url = '/api/context?doc=' + encodeURIComponent(doc) + '&line=' + encodeURIComponent(line);
                    const res = await fetch(url);
                    const data = await res.json();
                    if (data.content) {
                        contextCache[key] = data;
                    } else if (data.error) {
                        contextCache[key] = { content: 'Error: ' + data.error };
                    }
                } catch (e) {
                    contextCache[key] = { content: 'Could not load context' };
                }
            }
            
            const ctx = contextCache[key];
            if (!ctx || !ctx.content) return;
            
            // Create or update tooltip
            if (!contextTooltip) {
                contextTooltip = document.createElement('div');
                contextTooltip.className = 'context-tooltip';
                contextTooltip.style.cssText = `
                    position: fixed;
                    background: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 8px;
                    padding: 12px 16px;
                    max-width: 500px;
                    max-height: 200px;
                    overflow: auto;
                    font-family: monospace;
                    font-size: 12px;
                    color: #e6edf3;
                    white-space: pre-wrap;
                    word-break: break-word;
                    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
                    z-index: 9999;
                    pointer-events: none;
                `;
                document.body.appendChild(contextTooltip);
            }
            
            // Position tooltip
            const rect = element.getBoundingClientRect();
            contextTooltip.style.left = (rect.left + 20) + 'px';
            contextTooltip.style.top = (rect.bottom + 8) + 'px';
            
            // Show content with header
            const header = '📄 ' + doc + ':' + (ctx.block_start || line) + '-' + (ctx.block_end || line) + '\\n\\n';
            contextTooltip.textContent = header + ctx.content;
            contextTooltip.style.display = 'block';
            
            // Hide on mouse leave
            element.addEventListener('mouseleave', () => {
                if (contextTooltip) contextTooltip.style.display = 'none';
            }, { once: true });
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
	                    setSelectedDoc(file.name);
	                    content.innerHTML = `
	                        <div class="empty">
	                            <h3>✓ Document Added</h3>
	                            <p>${data.anchors} concepts extracted, ${data.edges} connections created</p>
	                            <p style="margin-top: 16px; color: #3fb950;">Selected: ${escHtml(file.name)}</p>
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

