#!/usr/bin/env python3
"""
ui.py — Invariant Web UI (v2 - Efficient)

Principles (Bisection Law):
1. Every action provides ≥1 bit of information
2. Minimal clicks to result
3. Human words, not hashes
4. Clear loading states
"""

from __future__ import annotations

import html
import json
import os
import re
import socket
import subprocess
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional

try:
    from .halo import hash8_hex
    from .overlay import OverlayGraph, find_overlays
    from .physics import HaloPhysics
except ImportError:
    from invariant_sdk.halo import hash8_hex
    from invariant_sdk.overlay import OverlayGraph, find_overlays
    from invariant_sdk.physics import HaloPhysics


DEFAULT_SERVER = "http://165.22.145.158:8080"


# =============================================================================
# Simpler HTML - focused on usability
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
        
        .btn-secondary {
            background: #21262d;
            border: 1px solid #30363d;
        }
        
        .btn-secondary:hover { background: #30363d; }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #8b949e;
        }
        
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #30363d;
            border-top-color: #58a6ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .results {
            margin-top: 24px;
        }
        
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid #21262d;
        }
        
        .result-header h2 {
            font-size: 18px;
            font-weight: 500;
        }
        
        .result-meta {
            font-size: 13px;
            color: #8b949e;
        }
        
        .result-list {
            list-style: none;
        }
        
        .result-item {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        
        .result-item:hover {
            border-color: #58a6ff;
        }
        
        .result-item.local {
            border-left: 3px solid #3fb950;
        }
        
        .result-word {
            flex: 1;
            font-weight: 500;
        }
        
        .result-weight {
            font-family: monospace;
            font-size: 13px;
            color: #8b949e;
            margin-right: 12px;
        }
        
        .badge {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 12px;
            font-weight: 500;
        }
        
        .badge-local {
            background: #238636;
            color: white;
        }
        
        .badge-global {
            background: #21262d;
            color: #8b949e;
        }
        
        .empty {
            text-align: center;
            padding: 60px 20px;
            color: #8b949e;
        }
        
        .empty h3 {
            color: #e6edf3;
            margin-bottom: 8px;
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
        
        <div class="search-form">
            <input type="text" class="search-input" id="query" 
                   placeholder="Type a word or concept..." autofocus>
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
            <div class="doc-upload" onclick="document.getElementById('fileInput').click()">
                <input type="file" id="fileInput" accept=".txt,.md" onchange="uploadFile(this)">
                <p>Click to upload .txt or .md file</p>
                <p style="font-size: 12px; color: #8b949e; margin-top: 8px;">
                    Document will be processed and added to your local knowledge
                </p>
            </div>
        </div>
    </div>
    
    <div class="status-bar">
        <span>Crystal: <strong>$$CRYSTAL_ID$$</strong></span>
        <span class="status-local">$$OVERLAY_STATUS$$</span>
    </div>

    <script>
        const queryInput = document.getElementById('query');
        const searchBtn = document.getElementById('searchBtn');
        const content = document.getElementById('content');
        
        queryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') search();
        });
        
        async function search() {
            const q = queryInput.value.trim();
            if (!q) return;
            
            searchBtn.disabled = true;
            content.innerHTML = '<div class="loading"><span class="spinner"></span>Searching...</div>';
            
            try {
                const res = await fetch('/api/search?q=' + encodeURIComponent(q));
                const data = await res.json();
                
                if (data.error) {
                    content.innerHTML = '<div class="empty"><h3>Error</h3><p>' + data.error + '</p></div>';
                    return;
                }
                
                renderResults(data);
            } catch (err) {
                content.innerHTML = '<div class="empty"><h3>Connection Error</h3><p>' + err.message + '</p></div>';
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
            
            let html = `
                <div class="results">
                    <div class="result-header">
                        <h2>Connections for "${data.query}"</h2>
                        <span class="result-meta">${localCount} local, ${globalCount} global</span>
                    </div>
                    <ul class="result-list">
            `;
            
            data.neighbors.slice(0, 30).forEach(n => {
                const isLocal = n.source === 'local';
                const label = n.label || 'unknown';
                const weight = (n.weight * 100).toFixed(0) + '%';
                const badge = isLocal 
                    ? '<span class="badge badge-local">LOCAL</span>'
                    : '<span class="badge badge-global">global</span>';
                const docInfo = n.doc ? ' • ' + n.doc : '';
                
                html += `
                    <li class="result-item ${isLocal ? 'local' : ''}" onclick="searchWord('${label}')">
                        <span class="result-word">${label}</span>
                        <span class="result-weight">${weight}${docInfo}</span>
                        ${badge}
                    </li>
                `;
            });
            
            html += '</ul></div>';
            content.innerHTML = html;
        }
        
        function searchWord(word) {
            queryInput.value = word;
            search();
        }
        
        async function uploadFile(input) {
            if (!input.files || !input.files[0]) return;
            
            const file = input.files[0];
            content.innerHTML = '<div class="loading"><span class="spinner"></span>Processing ' + file.name + '...</div>';
            
            try {
                const text = await file.text();
                const res = await fetch('/api/ingest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: file.name, text: text })
                });
                const data = await res.json();
                
                if (data.error) {
                    content.innerHTML = '<div class="empty"><h3>Error</h3><p>' + data.error + '</p></div>';
                } else {
                    content.innerHTML = `
                        <div class="empty">
                            <h3>✓ Document Added</h3>
                            <p>${data.anchors} concepts extracted, ${data.edges} connections created</p>
                            <p style="margin-top: 16px; color: #3fb950;">Reload page to see updated results</p>
                        </div>
                    `;
                }
            } catch (err) {
                content.innerHTML = '<div class="empty"><h3>Upload Error</h3><p>' + err.message + '</p></div>';
            }
            
            input.value = '';
        }
    </script>
</body>
</html>
'''


class UIHandler(BaseHTTPRequestHandler):
    """HTTP handler for Invariant UI."""
    
    physics: Optional[HaloPhysics] = None
    overlay: Optional[OverlayGraph] = None
    overlay_path: Optional[Path] = None
    
    def log_message(self, format, *args):
        pass  # Suppress logging
    
    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def send_html(self, content: str):
        body = content.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path in ('/', '/index.html'):
            self.serve_page()
        elif parsed.path == '/api/search':
            self.api_search(parsed.query)
        elif parsed.path == '/api/status':
            self.api_status()
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/api/ingest':
            self.api_ingest()
        else:
            self.send_error(404)
    
    def serve_page(self):
        physics = UIHandler.physics
        overlay = UIHandler.overlay
        
        crystal_id = physics.crystal_id if physics else "Not connected"
        overlay_status = f"{overlay.n_edges} local edges" if overlay else "No local documents"
        
        page = HTML_PAGE.replace('$$CRYSTAL_ID$$', html.escape(crystal_id))
        page = page.replace('$$OVERLAY_STATUS$$', overlay_status)
        
        self.send_html(page)
    
    def api_search(self, query_string: str):
        params = urllib.parse.parse_qs(query_string)
        q = params.get('q', [''])[0].strip()
        
        if not q:
            self.send_json({'error': 'No query'}, 400)
            return
        
        physics = UIHandler.physics
        overlay = UIHandler.overlay
        
        if not physics:
            self.send_json({'error': 'Not connected'}, 500)
            return
        
        try:
            # Multi-word query: try interference first (Bisection Law)
            # If interference is empty (no shared neighborhood), fallback to blend
            words = q.split()
            search_mode = 'single' if len(words) == 1 else 'interference'
            
            concept = physics.resolve(q, mode='interference')
            
            # Physics fallback: if interference empty and multi-word, try blend
            if len(words) > 1 and not concept.halo:
                concept = physics.resolve(q, mode='blend')
                search_mode = 'blend'  # Honestly report we used blend
            
            # Collect all neighbor hashes
            raw_neighbors = concept.halo[:50]
            all_hashes = [n.get('hash8', '') for n in raw_neighbors if n.get('hash8')]
            
            # Batch lookup labels from server (for global words)
            global_labels = {}
            if all_hashes:
                try:
                    global_labels = physics._client.get_labels_batch(all_hashes)
                except Exception:
                    pass
            
            neighbors = []
            for n in raw_neighbors:
                h8 = n.get('hash8', '')
                weight = n.get('weight', 0)
                doc = n.get('doc')
                
                # Get human-readable label: LOCAL overlay first, then global server
                label = None
                source = 'global'
                
                if overlay:
                    label = overlay.get_label(h8)
                    for src_edges in overlay.edges.values():
                        for edge in src_edges:
                            if edge.tgt == h8:
                                source = 'local'
                                if edge.doc:
                                    doc = edge.doc
                                break
                
                # Fallback: use global server label
                if not label:
                    label = global_labels.get(h8)
                
                # Final fallback: hash prefix
                if not label:
                    label = h8[:12] + '...'
                
                neighbors.append({
                    'hash8': h8,
                    'label': label,
                    'weight': weight,
                    'source': source,
                    'doc': doc
                })
            
            # Sort: local first, then by weight
            neighbors.sort(key=lambda x: (0 if x['source'] == 'local' else 1, -x['weight']))
            
            # Response includes physics properties
            self.send_json({
                'query': q,
                'mode': search_mode,  # Honest: tells user what mode was used
                'phase': concept.phase,  # solid/gas
                'mass': concept.mass,  # information content
                'mean_mass': physics.mean_mass,  # phase boundary
                'atoms': len(concept.atoms),  # number of resolved words
                'neighbors': neighbors
            })
            
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def api_ingest(self):
        """Ingest document via POST."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
            filename = data.get('filename', 'document.txt')
            text = data.get('text', '')
            
            if not text:
                self.send_json({'error': 'No text provided'}, 400)
                return
            
            physics = UIHandler.physics
            overlay = UIHandler.overlay
            overlay_path = UIHandler.overlay_path
            
            if not physics:
                self.send_json({'error': 'Not connected'}, 500)
                return
            
            # Simple tokenization
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            unique_words = list(dict.fromkeys(words))[:100]
            
            # Find anchors using single BATCH API call (O(1) network round-trip)
            # Server now properly supports limit=0 for meta-only checks
            word_to_hash = {w: hash8_hex(f"Ġ{w}") for w in unique_words}
            hash_to_word = {h: w for w, h in word_to_hash.items()}
            
            # Single HTTP call - meta only (no neighbors, just existence check)
            try:
                batch_results = physics._client.get_halo_pages(word_to_hash.values(), limit=0)
            except Exception as e:
                self.send_json({'error': f'Server error: {e}'}, 500)
                return
            
            anchors = []
            for h8, result in batch_results.items():
                if result.get('exists'):
                    word = hash_to_word.get(h8)
                    if word:
                        anchors.append((word, h8))
            
            if len(anchors) < 2:
                self.send_json({'error': 'Too few concepts found in document'}, 400)
                return
            
            # Create edges
            if overlay is None:
                overlay = OverlayGraph()
                UIHandler.overlay = overlay
            
            edges_added = 0
            for i in range(len(anchors) - 1):
                src_word, src_h8 = anchors[i]
                tgt_word, tgt_h8 = anchors[i + 1]
                
                overlay.add_edge(src_h8, tgt_h8, weight=1.0, doc=filename)
                overlay.define_label(src_h8, src_word)
                overlay.define_label(tgt_h8, tgt_word)
                edges_added += 1
            
            # Save
            if overlay_path:
                overlay.save(overlay_path)
            else:
                default_path = Path('./.invariant/overlay.jsonl')
                default_path.parent.mkdir(parents=True, exist_ok=True)
                overlay.save(default_path)
                UIHandler.overlay_path = default_path
            
            self.send_json({
                'success': True,
                'filename': filename,
                'anchors': len(anchors),
                'edges': edges_added
            })
            
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def api_status(self):
        physics = UIHandler.physics
        overlay = UIHandler.overlay
        
        self.send_json({
            'crystal': physics.crystal_id if physics else None,
            'edges': overlay.n_edges if overlay else 0,
            'labels': len(overlay.labels) if overlay else 0
        })


class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True
    
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def run_ui(port: int = 8080, server: str = DEFAULT_SERVER, overlay_path: Optional[Path] = None):
    """Start UI server."""
    print("Invariant UI")
    print("=" * 40)
    print()
    
    # Kill existing
    try:
        subprocess.run(f"lsof -ti:{port} | xargs kill -9 2>/dev/null", shell=True, capture_output=True)
        time.sleep(0.3)
    except:
        pass
    
    # Connect
    print(f"Connecting to: {server}")
    try:
        physics = HaloPhysics(server, auto_discover_overlay=True)
        UIHandler.physics = physics
        print(f"  Crystal: {physics.crystal_id}")
    except Exception as e:
        print(f"  Error: {e}")
        return
    
    # Load overlay
    if overlay_path:
        overlay = OverlayGraph.load(overlay_path)
        UIHandler.overlay_path = overlay_path
    elif physics._overlay:
        overlay = physics._overlay
    else:
        overlays = find_overlays()
        overlay = OverlayGraph.load_cascade(overlays) if overlays else None
        if overlays:
            UIHandler.overlay_path = overlays[-1]
    
    UIHandler.overlay = overlay
    
    if overlay:
        print(f"  Local: {overlay.n_edges} edges, {len(overlay.labels)} labels")
    
    print()
    print(f"→ Open http://localhost:{port}")
    print("  Ctrl+C to stop")
    print()
    
    httpd = ReuseHTTPServer(('localhost', port), UIHandler)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        httpd.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', '-p', type=int, default=8080)
    parser.add_argument('--server', '-s', default=DEFAULT_SERVER)
    parser.add_argument('--overlay', '-o', type=Path)
    args = parser.parse_args()
    run_ui(args.port, args.server, args.overlay)


if __name__ == '__main__':
    main()
