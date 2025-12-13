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
        }
        
        .autocomplete-source.local {
            background: rgba(63, 185, 80, 0.2);
            color: #3fb950;
        }
        
        .autocomplete-source.global {
            background: rgba(88, 166, 255, 0.2);
            color: #58a6ff;
        }
        
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
            display: flex;
            gap: 16px;
        }
        
        .phase-badge {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 12px;
            margin-left: 8px;
            vertical-align: middle;
        }
        
        .phase-badge.solid {
            background: rgba(88, 166, 255, 0.2);
            color: #58a6ff;
        }
        
        .phase-badge.gas {
            background: rgba(139, 148, 158, 0.2);
            color: #8b949e;
        }
        
        .orbit-group {
            margin-top: 20px;
        }
        
        .orbit-group h4 {
            font-size: 14px;
            margin-bottom: 10px;
            font-weight: 500;
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
        <span><a href="/cloud" style="color:#58a6ff">☁️ Cloud</a> | <a href="/graph" style="color:#58a6ff">📊 2D</a> | <a href="/graph3d" style="color:#58a6ff">🌐 3D</a></span>
        <span class="status-local">$$OVERLAY_STATUS$$</span>
    </div>

    <script>
        const queryInput = document.getElementById('query');
        const searchBtn = document.getElementById('searchBtn');
        const content = document.getElementById('content');
        const autocomplete = document.getElementById('autocomplete');
        
        let debounceTimer;
        
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
                    <div class="autocomplete-item ${s.source}" onclick="selectSuggestion('${s.word}')">
                        <span>${s.word}</span>
                        <span class="autocomplete-source ${s.source}">${s.source}</span>
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
                        <h2>
                            ${data.phase === 'solid' ? '◆' : '○'} "${data.query}"
                            <span class="phase-badge ${data.phase}">${data.phase === 'solid' ? 'ANCHOR' : 'common'}</span>
                        </h2>
                        <div class="result-meta">
                            <span>Mode: ${data.mode}</span>
                            <span>Mass: ${(data.mass || 0).toFixed(2)}</span>
                            <span>${localCount} local, ${globalCount} global</span>
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
                    const weight = (n.weight * 100).toFixed(0) + '%';
                    const badge = isLocal 
                        ? '<span class="badge badge-local">LOCAL</span>'
                        : '<span class="badge badge-global">global</span>';
                    const docInfo = n.doc ? ' • ' + n.doc : '';
                    
                    group += `
                        <li class="result-item ${isLocal ? 'local' : ''}" onclick="searchWord('${label}')">
                            <span class="result-word">${label}</span>
                            <span class="result-weight">${weight}${docInfo}</span>
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
        
        function handleDrop(e) {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const fakeInput = { files: files };
                uploadFile(fakeInput);
            }
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
    
    _graph_cache_key: Optional[tuple] = None
    _graph_cache_value: Optional[dict] = None
    
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
        elif parsed.path == '/graph':
            self.serve_graph_page()
        elif parsed.path == '/graph3d':
            self.serve_gravity3d_page()
        elif parsed.path == '/cloud':
            self.serve_cloud2d_page()
        elif parsed.path == '/cloud3d':
            self.serve_cloud_page()
        elif parsed.path == '/api/search':
            self.api_search(parsed.query)
        elif parsed.path == '/api/suggest':
            self.api_suggest(parsed.query)
        elif parsed.path == '/api/graph':
            self.api_graph()
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
    
    def serve_graph_page(self):
        """Serve full graph visualization page with D3.js."""
        overlay = UIHandler.overlay
        physics = UIHandler.physics
        
        node_count = len(overlay.labels) if overlay else 0
        edge_count = overlay.n_edges if overlay else 0
        
        graph_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Graph — Invariant</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: -apple-system, sans-serif; 
            background: #0d1117; 
            color: #e6edf3;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        .node {{ cursor: pointer; }}
        .node:hover {{ stroke: #58a6ff; stroke-width: 3px; }}
        .link {{ stroke: #30363d; }}
        .label {{ font-size: 10px; fill: #8b949e; pointer-events: none; }}
        #info {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(22, 27, 34, 0.95);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #30363d;
            max-width: 300px;
            z-index: 100;
        }}
        #info h2 {{ color: #58a6ff; margin-bottom: 12px; }}
        #info p {{ font-size: 13px; color: #8b949e; margin: 4px 0; }}
        #controls {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(22, 27, 34, 0.95);
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #30363d;
            z-index: 100;
        }}
        #controls button {{
            padding: 8px 12px;
            margin: 4px;
            background: #21262d;
            border: 1px solid #30363d;
            color: #e6edf3;
            border-radius: 4px;
            cursor: pointer;
        }}
        #controls button:hover {{ background: #30363d; }}
        #tooltip {{
            position: fixed;
            background: #161b22;
            border: 1px solid #30363d;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            display: none;
            z-index: 200;
        }}
        .legend {{
            display: flex;
            gap: 16px;
            margin-top: 12px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; }}
        .legend-circle {{ width: 12px; height: 12px; border-radius: 50%; }}
    </style>
</head>
<body>
    <div id="info">
        <h2>◆ Knowledge Graph</h2>
        <p>Nodes: <strong id="nodeCount">{node_count}</strong></p>
        <p>Edges: <strong id="edgeCount">{edge_count}</strong></p>
        <p style="margin-top: 8px; font-size: 11px; color: #484f58;">
            Size = Mass (information)<br>
            Color = Phase (blue=anchor, gray=common)
        </p>
        <div class="legend">
            <div class="legend-item"><div class="legend-circle" style="background:#58a6ff"></div> Solid</div>
            <div class="legend-item"><div class="legend-circle" style="background:#484f58"></div> Gas</div>
        </div>
        <p style="margin-top: 12px;"><a href="/" style="color:#58a6ff">← Back to Search</a></p>
    </div>
    
    <div id="controls">
        <button onclick="zoomIn()">+ Zoom</button>
        <button onclick="zoomOut()">− Zoom</button>
        <button onclick="resetZoom()">Reset</button>
        <button onclick="toggleLabels()">Labels</button>
    </div>
    
    <div id="tooltip"></div>
    <svg id="graph"></svg>
    
    <script>
        let showLabels = true;
        let simulation, svg, g, link, node, label;
        let zoom;
        
        async function loadGraph() {{
            const res = await fetch('/api/graph');
            const data = await res.json();
            
            document.getElementById('nodeCount').textContent = data.nodes.length;
            document.getElementById('edgeCount').textContent = data.edges.length;
            
            const width = window.innerWidth;
            const height = window.innerHeight;
            
            svg = d3.select('#graph')
                .attr('width', width)
                .attr('height', height);
            
            zoom = d3.zoom()
                .scaleExtent([0.1, 10])
                .on('zoom', (e) => g.attr('transform', e.transform));
            
            svg.call(zoom);
            
            g = svg.append('g');
            
            // Force simulation with physics
            simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.edges).id(d => d.id).distance(80).strength(d => d.weight * 0.5))
                .force('charge', d3.forceManyBody().strength(d => -d.mass * 300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collide', d3.forceCollide().radius(d => Math.sqrt(d.mass) * 25 + 5));
            
            // Edges
            link = g.append('g')
                .selectAll('line')
                .data(data.edges)
                .join('line')
                .attr('class', 'link')
                .attr('stroke-opacity', d => 0.2 + d.weight * 0.6)
                .attr('stroke-width', d => 1 + d.weight * 2);
            
            // Nodes
            node = g.append('g')
                .selectAll('circle')
                .data(data.nodes)
                .join('circle')
                .attr('class', 'node')
                .attr('r', d => Math.sqrt(d.mass) * 20 + 5)
                .attr('fill', d => d.phase === 'solid' ? '#58a6ff' : '#484f58')
                .call(drag(simulation))
                .on('click', (e, d) => {{
                    window.location.href = '/?q=' + encodeURIComponent(d.label);
                }})
                .on('mouseover', (e, d) => {{
                    const tooltip = document.getElementById('tooltip');
                    tooltip.innerHTML = `<strong>${{d.label}}</strong><br>Mass: ${{d.mass.toFixed(3)}}<br>Phase: ${{d.phase}}<br>Degree: ${{d.degree}}`;
                    tooltip.style.display = 'block';
                    tooltip.style.left = (e.pageX + 10) + 'px';
                    tooltip.style.top = (e.pageY + 10) + 'px';
                }})
                .on('mouseout', () => {{
                    document.getElementById('tooltip').style.display = 'none';
                }});
            
            // Labels
            label = g.append('g')
                .selectAll('text')
                .data(data.nodes)
                .join('text')
                .attr('class', 'label')
                .text(d => d.label)
                .attr('dx', d => Math.sqrt(d.mass) * 20 + 8)
                .attr('dy', 4);
            
            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);
                
                label
                    .attr('x', d => d.x)
                    .attr('y', d => d.y);
            }});
        }}
        
        function drag(simulation) {{
            return d3.drag()
                .on('start', (e, d) => {{
                    if (!e.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                }})
                .on('drag', (e, d) => {{
                    d.fx = e.x;
                    d.fy = e.y;
                }})
                .on('end', (e, d) => {{
                    if (!e.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }});
        }}
        
        function zoomIn() {{ svg.transition().call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().call(zoom.scaleBy, 0.7); }}
        function resetZoom() {{ svg.transition().call(zoom.transform, d3.zoomIdentity); }}
        function toggleLabels() {{
            showLabels = !showLabels;
            label.style('display', showLabels ? 'block' : 'none');
        }}
        
        loadGraph();
    </script>
</body>
</html>'''
        self.send_html(graph_html)
    
    def api_graph(self):
        """Return graph data for visualization."""
        import math
        
        overlay = UIHandler.overlay
        physics = UIHandler.physics
        mean_mass = physics.mean_mass if physics else 0.26
        
        if not overlay:
            self.send_json({'nodes': [], 'edges': [], 'mean_mass': mean_mass})
            return
        
        overlay_mtime_ns = None
        if UIHandler.overlay_path and UIHandler.overlay_path.exists():
            try:
                overlay_mtime_ns = UIHandler.overlay_path.stat().st_mtime_ns
            except OSError:
                overlay_mtime_ns = None
        
        cache_key = (
            physics.crystal_id if physics else None,
            overlay_mtime_ns,
            overlay.n_edges,
            len(overlay.labels),
        )
        if cache_key == UIHandler._graph_cache_key and UIHandler._graph_cache_value is not None:
            self.send_json(UIHandler._graph_cache_value)
            return
        
        node_set: set[str] = set()
        nodes_base: list[dict] = []
        for h8, label in overlay.labels.items():
            if label:
                node_set.add(h8)
                nodes_base.append({'id': h8, 'label': label})
        
        edges: list[dict] = []
        degree_local: dict[str, int] = {h8: 0 for h8 in node_set}
        for src, edge_list in overlay.edges.items():
            if src not in node_set:
                continue
            for edge in edge_list:
                tgt = edge.tgt
                if tgt in node_set:
                    w = abs(edge.weight)
                    edges.append({'source': src, 'target': tgt, 'weight': w})
                    # Treat as undirected for degree/temperature visualization.
                    degree_local[src] = degree_local.get(src, 0) + 1
                    degree_local[tgt] = degree_local.get(tgt, 0) + 1
        
        # Degree_total (HALO_SPEC): required for deterministic Mass.
        degree_total: dict[str, int] = {}
        if physics and node_set:
            try:
                results = physics._client.get_halo_pages(node_set, limit=0)
                for h8, result in results.items():
                    meta = result.get('meta') or {}
                    try:
                        degree_total[h8] = int(meta.get('degree_total') or 0)
                    except Exception:
                        degree_total[h8] = 0
            except Exception:
                degree_total = {}
        
        nodes: list[dict] = []
        for base in nodes_base:
            h8 = base['id']
            deg_total = degree_total.get(h8)
            if deg_total is None:
                deg_total = degree_local.get(h8, 0)
            try:
                mass = 1.0 / math.log(2 + max(0, int(deg_total)))
            except Exception:
                mass = 0.0
            phase = 'solid' if mass > mean_mass else 'gas'
            nodes.append({
                'id': h8,
                'label': base['label'],
                'mass': mass,
                'phase': phase,
                'degree': degree_local.get(h8, 0),
                'degree_total': int(deg_total),
            })
        
        payload = {'nodes': nodes, 'edges': edges, 'mean_mass': mean_mass}
        UIHandler._graph_cache_key = cache_key
        UIHandler._graph_cache_value = payload
        self.send_json(payload)

    def serve_cloud2d_page(self):
        """Classic 2D tag cloud (text-only, physics-based)."""
        cloud_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Tag Cloud — Invariant</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            overflow: hidden;
        }
        #cloud {
            position: relative;
            width: 100vw;
            height: 100vh;
        }
        .word {
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
            font-weight: 600;
            text-shadow: 0 2px 12px rgba(0,0,0,0.85);
            transition: transform 0.12s, opacity 0.12s;
        }
        .word:hover {
            transform: translate(-50%, -50%) scale(1.35);
            z-index: 1000;
        }
        .word.dim { opacity: 0.15; }
        .word.anchor {
            font-weight: 800;
            text-shadow: 0 0 18px currentColor, 0 2px 12px rgba(0,0,0,0.85);
        }
        #hud {
            position: fixed;
            top: 16px;
            left: 16px;
            background: rgba(22, 27, 34, 0.95);
            padding: 14px;
            border-radius: 8px;
            border: 1px solid #30363d;
            width: 340px;
            z-index: 2000;
        }
        #hud h1 {
            font-size: 12px;
            color: #58a6ff;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin: 0 0 10px;
        }
        #hud .row { font-size: 12px; color: #8b949e; margin: 4px 0; }
        #hud .row span { color: #e6edf3; }
        #hud a { color: #58a6ff; }
        #tooltip {
            position: fixed;
            background: rgba(22, 27, 34, 0.95);
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid #58a6ff;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.1s;
            z-index: 3000;
            max-width: 360px;
        }
        #tooltip.visible { opacity: 1; }
        #tooltip .t { color: #58a6ff; font-weight: 700; margin-bottom: 6px; }
        #tooltip .s { color: #8b949e; margin: 2px 0; }
    </style>
</head>
<body>
    <div id="hud">
        <h1>Tag Cloud</h1>
        <div class="row">Size: <span>Mass</span> = 1/log(2+degree_total)</div>
        <div class="row">Color: <span>Temperature</span> ∝ log(2+degree_total)</div>
        <div class="row">Hover: neighborhood highlight</div>
        <div class="row" style="margin-top: 8px;"><a href="/">Search</a> | <a href="/graph">Graph</a> | <a href="/graph3d">3D</a> | <a href="/cloud3d">Cloud 3D (legacy)</a></div>
    </div>
    <div id="cloud"></div>
    <div id="tooltip"></div>
    <script>
    (async function () {
        const res = await fetch('/api/graph');
        const data = await res.json();
        const nodes = (data.nodes || []).map(n => ({...n}));
        const links = (data.edges || []).map(e => ({ source: e.source, target: e.target, weight: +e.weight || 0 }));

        const cloud = document.getElementById('cloud');
        const tooltip = document.getElementById('tooltip');

        if (!nodes.length) {
            cloud.innerHTML = '<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:#8b949e;">No local graph loaded</div>';
            return;
        }

        const neigh = new Map(nodes.map(n => [n.id, new Set()]));
        links.forEach(l => {
            if (neigh.has(l.source)) neigh.get(l.source).add(l.target);
            if (neigh.has(l.target)) neigh.get(l.target).add(l.source);
        });

        const degs = nodes.map(n => Math.max(0, +n.degree_total || +n.degree || 0));
        const logDegs = degs.map(d => Math.log(2 + d));
        const minLog = Math.min(...logDegs);
        const maxLog = Math.max(...logDegs);
        function normTemp(n) {
            const d = Math.max(0, +n.degree_total || +n.degree || 0);
            const v = Math.log(2 + d);
            if (maxLog <= minLog) return 0;
            return (v - minLog) / (maxLog - minLog);
        }
        const cold = [121, 192, 255]; // #79c0ff
        const hot = [255, 123, 114]; // #ff7b72
        function tempColor(t) {
            t = Math.max(0, Math.min(1, t));
            const r = Math.round(cold[0] + (hot[0] - cold[0]) * t);
            const g = Math.round(cold[1] + (hot[1] - cold[1]) * t);
            const b = Math.round(cold[2] + (hot[2] - cold[2]) * t);
            return `rgb(${r},${g},${b})`;
        }

        const els = new Map();
        nodes.forEach(n => {
            const el = document.createElement('div');
            el.className = 'word';
            el.textContent = n.label || n.id.slice(0, 8);
            if (n.phase === 'solid') el.classList.add('anchor');

            const mass = Math.max(0, +n.mass || 0);
            el.style.fontSize = (12 + mass * 40) + 'px';
            el.style.color = tempColor(normTemp(n));

            el.addEventListener('mousemove', (e) => {
                tooltip.style.left = (e.clientX + 14) + 'px';
                tooltip.style.top = (e.clientY + 14) + 'px';
            });
            el.addEventListener('mouseenter', () => {
                const nb = neigh.get(n.id) || new Set();
                els.forEach((otherEl, id) => {
                    if (id === n.id || nb.has(id)) otherEl.classList.remove('dim');
                    else otherEl.classList.add('dim');
                });
                tooltip.innerHTML = `
                    <div class="t">${n.label}</div>
                    <div class="s">mass: ${(n.mass || 0).toFixed(4)} | phase: ${n.phase}</div>
                    <div class="s">degree_total: ${n.degree_total} | degree_local: ${n.degree}</div>
                    <div class="s">temp: ${normTemp(n).toFixed(3)}</div>
                `;
                tooltip.classList.add('visible');
            });
            el.addEventListener('mouseleave', () => {
                tooltip.classList.remove('visible');
                els.forEach(otherEl => otherEl.classList.remove('dim'));
            });
            el.addEventListener('click', () => {
                window.location.href = '/?q=' + encodeURIComponent(n.label || '');
            });

            cloud.appendChild(el);
            els.set(n.id, el);
        });

        function layout() {
            const width = window.innerWidth;
            const height = window.innerHeight;

            const simulation = d3.forceSimulation(nodes)
                .force('link', d3.forceLink(links).id(d => d.id)
                    .distance(l => 120 + (1 - Math.max(0, Math.min(1, l.weight))) * 180)
                    .strength(l => Math.max(0.05, Math.min(1, l.weight)))
                )
                .force('charge', d3.forceManyBody().strength(n => -30 - (Math.max(0, +n.mass || 0) * 220)))
                .force('center', d3.forceCenter(0, 0))
                .force('collide', d3.forceCollide(n => 10 + (Math.max(0, +n.mass || 0) * 20)).strength(0.7))
                .alpha(1)
                .alphaDecay(0.03);

            simulation.on('tick', () => {
                nodes.forEach(n => {
                    const el = els.get(n.id);
                    if (!el) return;
                    el.style.transform = `translate(${(width/2 + n.x)}px, ${(height/2 + n.y)}px) translate(-50%, -50%)`;
                });
            });
        }

        layout();
    })();
    </script>
</body>
</html>'''
        self.send_html(cloud_html)

    def serve_cloud_page(self):
        """3D rotatable tag cloud with CSS3D transforms."""
        cloud_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>3D Tag Cloud — Invariant</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
            color: #e6edf3;
            min-height: 100vh;
            overflow: hidden;
            perspective: 1000px;
        }}
        #scene {{
            width: 100vw;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        #cloud {{
            position: relative;
            width: 600px;
            height: 600px;
            transform-style: preserve-3d;
            transition: transform 0.1s;
        }}
        .word {{
            position: absolute;
            cursor: pointer;
            white-space: nowrap;
            font-weight: 600;
            transform-style: preserve-3d;
            transition: transform 0.3s, text-shadow 0.3s;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }}
        .word:hover {{
            transform: scale(1.5) translateZ(50px) !important;
            text-shadow: 0 0 30px currentColor, 0 0 60px currentColor;
            z-index: 1000;
        }}
        #tooltip {{
            position: fixed;
            background: rgba(22, 27, 34, 0.95);
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #58a6ff;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            z-index: 2000;
        }}
        #tooltip.visible {{ opacity: 1; }}
        #tooltip h3 {{ color: #58a6ff; margin-bottom: 6px; font-size: 16px; }}
        #tooltip .stat {{ color: #8b949e; margin: 2px 0; }}
        #info {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(22, 27, 34, 0.95);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #30363d;
            z-index: 1000;
        }}
        #info h2 {{ color: #58a6ff; margin-bottom: 8px; font-size: 18px; }}
        #info p {{ font-size: 12px; color: #8b949e; margin: 4px 0; }}
        #info a {{ color: #58a6ff; }}
        .legend {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 10px;
            font-size: 11px;
        }}
        .gradient {{
            width: 80px;
            height: 8px;
            border-radius: 4px;
            background: linear-gradient(90deg, hsl(240,80%,60%), hsl(150,80%,60%), hsl(30,100%,65%));
        }}
    </style>
</head>
<body>
    <div id="info">
        <h2>☁️ 3D Tag Cloud</h2>
        <p id="stats">Loading...</p>
        <p style="margin-top: 8px; font-size: 11px; color: #484f58;">
            🖱️ Drag to rotate<br>
            Size = Mass • Color = Temperature
        </p>
        <div class="legend">
            <span>🥶</span>
            <div class="gradient"></div>
            <span>🔥</span>
        </div>
        <p style="margin-top: 12px;">
            <a href="/">Search</a> | <a href="/graph">2D Graph</a>
        </p>
    </div>
    
    <div id="tooltip">
        <h3 id="tt-label">word</h3>
        <div class="stat">📊 Mass: <span id="tt-mass">0</span></div>
        <div class="stat">🔗 Degree: <span id="tt-deg">0</span></div>
        <div class="stat">🌡️ Temperature: <span id="tt-temp">cold</span></div>
    </div>
    
    <div id="scene">
        <div id="cloud"></div>
    </div>
    
    <script>
        const cloud = document.getElementById('cloud');
        const tooltip = document.getElementById('tooltip');
        let rotX = 0, rotY = 0;
        let isDragging = false;
        let lastX, lastY;
        
        // Drag to rotate
        document.addEventListener('mousedown', e => {{
            isDragging = true;
            lastX = e.clientX;
            lastY = e.clientY;
        }});
        document.addEventListener('mouseup', () => isDragging = false);
        document.addEventListener('mousemove', e => {{
            if (!isDragging) return;
            rotY += (e.clientX - lastX) * 0.3;
            rotX -= (e.clientY - lastY) * 0.3;
            cloud.style.transform = `rotateX(${{rotX}}deg) rotateY(${{rotY}}deg)`;
            lastX = e.clientX;
            lastY = e.clientY;
        }});
        
        // Auto-rotate
        let autoRotate = true;
        setInterval(() => {{
            if (!isDragging && autoRotate) {{
                rotY += 0.2;
                cloud.style.transform = `rotateX(${{rotX}}deg) rotateY(${{rotY}}deg)`;
            }}
        }}, 30);
        
        fetch('/api/graph')
            .then(res => res.json())
            .then(data => {{
                document.getElementById('stats').innerHTML = 
                    `<strong>${{data.nodes.length}}</strong> words`;
                
                const radius = 250;
                const count = data.nodes.length;
                
                data.nodes.forEach((n, i) => {{
                    const el = document.createElement('div');
                    el.className = 'word';
                    el.textContent = n.label;
                    
                    // SIZE: Font = mass
                    const fontSize = 10 + n.mass * 35;
                    el.style.fontSize = fontSize + 'px';
                    
                    // COLOR: Temperature
                    const temp = Math.min(1, n.degree / 12);
                    const hue = 240 - temp * 210;
                    const sat = 70 + temp * 30;
                    const light = 55 + temp * 15;
                    el.style.color = `hsl(${{hue}}, ${{sat}}%, ${{light}}%)`;
                    
                    // 3D POSITION: Fibonacci sphere
                    const phi = Math.acos(1 - 2 * (i + 0.5) / count);
                    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
                    const x = radius * Math.sin(phi) * Math.cos(theta);
                    const y = radius * Math.sin(phi) * Math.sin(theta);
                    const z = radius * Math.cos(phi);
                    
                    el.style.left = '50%';
                    el.style.top = '50%';
                    el.style.transform = `translate3d(${{x}}px, ${{y}}px, ${{z}}px) translate(-50%, -50%)`;
                    
                    // HOVER: Show tooltip
                    el.addEventListener('mouseenter', e => {{
                        document.getElementById('tt-label').textContent = n.label;
                        document.getElementById('tt-mass').textContent = n.mass.toFixed(4);
                        document.getElementById('tt-deg').textContent = n.degree;
                        document.getElementById('tt-temp').textContent = temp < 0.3 ? 'cold 🥶' : temp < 0.6 ? 'warm 🌡️' : 'hot 🔥';
                        tooltip.classList.add('visible');
                    }});
                    el.addEventListener('mouseleave', () => {{
                        tooltip.classList.remove('visible');
                    }});
                    el.addEventListener('mousemove', e => {{
                        tooltip.style.left = (e.clientX + 15) + 'px';
                        tooltip.style.top = (e.clientY + 15) + 'px';
                    }});
                    
                    // CLICK: Search
                    el.onclick = () => {{
                        window.location.href = '/?q=' + encodeURIComponent(n.label);
                    }};
                    
                    cloud.appendChild(el);
                }});
            }});
    </script>
</body>
</html>'''
        self.send_html(cloud_html)
    
    def serve_gravity3d_page(self):
        """3D tag-cloud: positions from forces, words stay readable (billboard)."""
        gravity_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Semantic Gravity — Invariant</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/d3-force-3d"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            overflow: hidden;
        }
        #scene {
            position: relative;
            width: 100vw;
            height: 100vh;
            perspective: 950px;
            overflow: hidden;
        }
        #cloud {
            position: absolute;
            left: 50%;
            top: 50%;
            transform-style: preserve-3d;
            will-change: transform;
            --invrx: 0deg;
            --invry: 0deg;
        }
        .word {
            position: absolute;
            left: 0;
            top: 0;
            transform-style: preserve-3d;
            white-space: nowrap;
            cursor: pointer;
            user-select: none;
            font-weight: 600;
            text-shadow: 0 2px 12px rgba(0,0,0,0.85);
            transition: opacity 0.12s;
            will-change: transform;
            transform: translate3d(var(--x, 0px), var(--y, 0px), var(--z, 0px)) translate(-50%, -50%);
        }
        .word.anchor {
            font-weight: 800;
            text-shadow: 0 0 18px currentColor, 0 2px 12px rgba(0,0,0,0.85);
        }
        #cloud.focus .word { opacity: 0.12; }
        #cloud.focus .word.active { opacity: 1; }
        .label {
            display: inline-block;
            transform: rotateY(var(--invry)) rotateX(var(--invrx));
            transform-origin: center;
            will-change: transform;
        }
        .word:hover .label {
            transform: rotateY(var(--invry)) rotateX(var(--invrx)) scale(1.25);
        }
        #hud {
            position: fixed;
            top: 16px;
            left: 16px;
            background: rgba(22, 27, 34, 0.95);
            padding: 14px;
            border-radius: 8px;
            border: 1px solid #30363d;
            width: 380px;
            z-index: 2000;
        }
        #hud h1 {
            font-size: 12px;
            color: #58a6ff;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin: 0 0 10px;
        }
        #hud .row { font-size: 12px; color: #8b949e; margin: 4px 0; }
        #hud .row span { color: #e6edf3; }
        #hud button {
            margin-top: 10px;
            margin-right: 8px;
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            padding: 6px 8px;
            border-radius: 6px;
            cursor: pointer;
        }
        #hud button.active { border-color: #58a6ff; }
        #hud a { color: #58a6ff; }
        #tooltip {
            position: fixed;
            background: rgba(22, 27, 34, 0.95);
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid #58a6ff;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.1s;
            z-index: 3000;
            max-width: 380px;
        }
        #tooltip.visible { opacity: 1; }
        #tooltip .t { color: #58a6ff; font-weight: 700; margin-bottom: 6px; }
        #tooltip .s { color: #8b949e; margin: 2px 0; }
    </style>
</head>
<body>
    <div id="scene"><div id="cloud"></div></div>
    <div id="hud">
        <h1>Semantic Gravity</h1>
        <div class="row">Nodes: <span id="nNodes">0</span> | Edges: <span id="nEdges">0</span></div>
        <div class="row">Mean mass μ: <span id="meanMass">—</span></div>
        <div class="row">Hover: <span id="hoverLabel">—</span></div>
        <div class="row">Mass: <span id="hoverMass">—</span> | Degree: <span id="hoverDeg">—</span></div>
        <div class="row">Temp: <span id="hoverTemp">—</span> | Phase: <span id="hoverPhase">—</span></div>
        <button id="toggleRotate" class="active">Auto-Rotate</button>
        <button id="resetView">Reset</button>
        <div class="row" style="margin-top: 10px;">
            <span>Size</span>=Mass • <span>Color</span>=Temperature • <span>Distance</span>=Gravity
        </div>
        <div class="row" style="margin-top: 8px;"><a href="/">Search</a> | <a href="/cloud">Cloud</a> | <a href="/graph">Graph</a></div>
    </div>
    <div id="tooltip"></div>
    <script>
    (async function () {
        const res = await fetch('/api/graph');
        const data = await res.json();
        const nodes = (data.nodes || []).map(n => ({...n}));
        const links = (data.edges || []).map(e => ({ source: e.source, target: e.target, weight: +e.weight || 0 }));

        document.getElementById('nNodes').textContent = nodes.length;
        document.getElementById('nEdges').textContent = links.length;
        if (data.mean_mass != null) document.getElementById('meanMass').textContent = (+data.mean_mass).toFixed(4);

        const cloud = document.getElementById('cloud');
        const tooltip = document.getElementById('tooltip');

        if (!nodes.length) {
            cloud.innerHTML = '<div style="position:absolute;left:0;top:0;transform:translate(-50%,-50%);color:#8b949e;">No local graph loaded</div>';
            return;
        }

        const byId = new Map(nodes.map(n => [n.id, n]));
        const neigh = new Map(nodes.map(n => [n.id, new Set()]));
        links.forEach(l => {
            if (neigh.has(l.source)) neigh.get(l.source).add(l.target);
            if (neigh.has(l.target)) neigh.get(l.target).add(l.source);
        });

        // Temperature is monotonic with log-degree_total (Gas hot, Anchors cold).
        const degs = nodes.map(n => Math.max(0, +n.degree_total || +n.degree || 0));
        const logDegs = degs.map(d => Math.log(2 + d));
        const minLog = Math.min(...logDegs);
        const maxLog = Math.max(...logDegs);
        function normTemp(n) {
            const d = Math.max(0, +n.degree_total || +n.degree || 0);
            const v = Math.log(2 + d);
            if (maxLog <= minLog) return 0;
            return (v - minLog) / (maxLog - minLog);
        }
        const cold = [121, 192, 255]; // #79c0ff
        const hot = [255, 123, 114]; // #ff7b72
        function tempColor(t) {
            t = Math.max(0, Math.min(1, t));
            const r = Math.round(cold[0] + (hot[0] - cold[0]) * t);
            const g = Math.round(cold[1] + (hot[1] - cold[1]) * t);
            const b = Math.round(cold[2] + (hot[2] - cold[2]) * t);
            return `rgb(${r},${g},${b})`;
        }

        const els = new Map();
        nodes.forEach(n => {
            const el = document.createElement('div');
            el.className = 'word';
            const labelEl = document.createElement('span');
            labelEl.className = 'label';
            labelEl.textContent = n.label || n.id.slice(0, 8);
            el.appendChild(labelEl);
            if (n.phase === 'solid') el.classList.add('anchor');

            const mass = Math.max(0, +n.mass || 0);
            labelEl.style.fontSize = (12 + mass * 40) + 'px';
            labelEl.style.color = tempColor(normTemp(n));

            el.addEventListener('mousemove', (e) => {
                tooltip.style.left = (e.clientX + 14) + 'px';
                tooltip.style.top = (e.clientY + 14) + 'px';
            });
            el.addEventListener('mouseenter', (e) => onHover(n.id, e));
            el.addEventListener('mouseleave', () => onHover(null));
            el.addEventListener('click', () => {
                window.location.href = '/?q=' + encodeURIComponent(n.label || '');
            });

            cloud.appendChild(el);
            els.set(n.id, el);
        });

        // View transform (camera): rotate + pan + zoom.
        let rotX = -18;
        let rotY = 24;
        let panX = 0;
        let panY = 0;
        let zoomZ = 0;
        let pointerId = null;
        let dragMode = null; // 'rotate' | 'pan'
        let lastX = 0;
        let lastY = 0;
        let autoRotate = true;
        let lastInteractionAt = 0;
        const scene = document.getElementById('scene');

        function noteInteraction() {
            lastInteractionAt = performance.now();
        }

        function updateView() {
            cloud.style.transform = `translate3d(${panX}px, ${panY}px, ${zoomZ}px) rotateX(${rotX}deg) rotateY(${rotY}deg)`;
            cloud.style.setProperty('--invrx', (-rotX) + 'deg');
            cloud.style.setProperty('--invry', (-rotY) + 'deg');
        }
        updateView();

        function setHud(n) {
            const set = (id, v) => document.getElementById(id).textContent = v;
            if (!n) {
                set('hoverLabel', '—');
                set('hoverMass', '—');
                set('hoverDeg', '—');
                set('hoverTemp', '—');
                set('hoverPhase', '—');
                return;
            }
            const deg = Math.max(0, +n.degree_total || +n.degree || 0);
            set('hoverLabel', n.label || n.id);
            set('hoverMass', (+n.mass || 0).toFixed(4));
            set('hoverDeg', String(deg));
            set('hoverTemp', normTemp(n).toFixed(3));
            set('hoverPhase', n.phase || '—');
        }

        function positionTooltip(e) {
            tooltip.style.left = (e.clientX + 14) + 'px';
            tooltip.style.top = (e.clientY + 14) + 'px';
        }

        let hovered = null;
        let activeIds = new Set();
        function setActive(newIds) {
            activeIds.forEach(id => {
                const el = els.get(id);
                if (el) el.classList.remove('active');
            });
            activeIds = newIds;
            activeIds.forEach(id => {
                const el = els.get(id);
                if (el) el.classList.add('active');
            });
        }
        function onHover(id, e) {
            noteInteraction();
            hovered = id ? byId.get(id) : null;
            setHud(hovered);
            if (!hovered) {
                tooltip.classList.remove('visible');
                cloud.classList.remove('focus');
                setActive(new Set());
                return;
            }
            cloud.classList.add('focus');
            const nb = neigh.get(id) || new Set();
            const next = new Set([id]);
            nb.forEach(x => next.add(x));
            setActive(next);

            tooltip.innerHTML = `
                <div class="t">${hovered.label}</div>
                <div class="s">mass: ${(hovered.mass || 0).toFixed(4)} | phase: ${hovered.phase}</div>
                <div class="s">degree_total: ${hovered.degree_total} | degree_local: ${hovered.degree}</div>
                <div class="s">temp: ${normTemp(hovered).toFixed(3)}</div>
            `;
            tooltip.classList.add('visible');
            if (e) positionTooltip(e);
        }

        // Force simulation (3D): weight controls spring (gravity), mass controls repulsion.
        const simNodes = nodes.map(n => ({...n}));
        const simLinks = links.map(l => ({...l}));

        const spread = 360;
        simNodes.forEach(n => {
            n.x = (Math.random() - 0.5) * spread;
            n.y = (Math.random() - 0.5) * spread;
            n.z = (Math.random() - 0.5) * spread;
        });

        const linkDist = (l) => {
            const w = Math.max(0, Math.min(1, +l.weight || 0));
            return 80 + (1 - w) * 220;
        };
        const linkStrength = (l) => Math.max(0.05, Math.min(1, +l.weight || 0));
        const chargeStrength = (n) => -30 - (Math.max(0, +n.mass || 0) * 240);
        const collideRadius = (n) => 10 + (Math.max(0, +n.mass || 0) * 22);

        const simulation = d3.forceSimulation(simNodes)
            .force('link', d3.forceLink(simLinks).id(d => d.id).distance(linkDist).strength(linkStrength))
            .force('charge', d3.forceManyBody().strength(chargeStrength))
            .force('center', d3.forceCenter(0, 0, 0))
            .force('collide', d3.forceCollide(collideRadius).strength(0.7))
            .alpha(1)
            .alphaDecay(0.03);

        // Render node positions only when physics updates (not every frame).
        let posRaf = null;
        function schedulePosRender() {
            if (posRaf) return;
            posRaf = requestAnimationFrame(() => {
                posRaf = null;
                simNodes.forEach(n => {
                    const el = els.get(n.id);
                    if (!el) return;
                    el.style.setProperty('--x', `${n.x.toFixed(2)}px`);
                    el.style.setProperty('--y', `${n.y.toFixed(2)}px`);
                    el.style.setProperty('--z', `${n.z.toFixed(2)}px`);
                });
            });
        }
        simulation.on('tick', () => {
            schedulePosRender();
            // Stop when cold to reduce CPU.
            if (simulation.alpha() < 0.035) simulation.stop();
        });
        schedulePosRender();

        function animate() {
            const now = performance.now();
            const idle = (now - lastInteractionAt) > 900;
            const canAutoRotate = autoRotate && idle && !hovered && pointerId === null;
            if (canAutoRotate) {
                rotY += 0.08;
                updateView();
            }
            requestAnimationFrame(animate);
        }
        requestAnimationFrame(animate);

        // Pointer controls: left drag = rotate, right/shift drag = pan, wheel = zoom.
        scene.addEventListener('contextmenu', (e) => e.preventDefault());
        scene.addEventListener('pointerdown', (e) => {
            noteInteraction();
            pointerId = e.pointerId;
            dragMode = (e.button === 2 || e.button === 1 || e.shiftKey) ? 'pan' : 'rotate';
            lastX = e.clientX;
            lastY = e.clientY;
            scene.setPointerCapture(pointerId);
        });
        scene.addEventListener('pointerup', (e) => {
            if (pointerId !== e.pointerId) return;
            pointerId = null;
            dragMode = null;
        });
        scene.addEventListener('pointermove', (e) => {
            if (tooltip.classList.contains('visible')) positionTooltip(e);
            if (pointerId !== e.pointerId || !dragMode) {
                noteInteraction();
                return;
            }
            noteInteraction();
            const dx = e.clientX - lastX;
            const dy = e.clientY - lastY;
            lastX = e.clientX;
            lastY = e.clientY;
            if (dragMode === 'rotate') {
                rotY += dx * 0.25;
                rotX -= dy * 0.25;
                rotX = Math.max(-85, Math.min(85, rotX));
            } else {
                panX += dx;
                panY += dy;
            }
            updateView();
        });
        scene.addEventListener('wheel', (e) => {
            e.preventDefault();
            noteInteraction();
            zoomZ += (-e.deltaY) * 0.8;
            zoomZ = Math.max(-2000, Math.min(800, zoomZ));
            updateView();
        }, { passive: false });

        document.getElementById('toggleRotate').onclick = () => {
            autoRotate = !autoRotate;
            document.getElementById('toggleRotate').classList.toggle('active', autoRotate);
            noteInteraction();
        };
        document.getElementById('resetView').onclick = () => {
            rotX = -18;
            rotY = 24;
            panX = 0;
            panY = 0;
            zoomZ = 0;
            autoRotate = true;
            document.getElementById('toggleRotate').classList.add('active');
            updateView();
            noteInteraction();
        };

    })();
    </script>
</body>
</html>'''
        self.send_html(gravity_html)

    def serve_graph3d_page(self):
        """Serve 3D Force Graph - Semantic Gravity (Pure Physics)."""
        graph3d_html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Neural Topology — Invariant</title>
    <!-- ForceGraph bundles THREE and d3 -->
    <script src="//unpkg.com/3d-force-graph"></script>
    <style>
        body { margin: 0; background: #000; overflow: hidden; font-family: monospace; }
        #overlay {
            position: fixed; top: 20px; left: 20px; z-index: 100;
            color: #666; font-size: 11px; pointer-events: none;
            text-shadow: 0 0 3px #000;
        }
        h1 { color: #fff; font-size: 13px; letter-spacing: 2px; margin: 0 0 10px; }
        .legend { margin-top: 12px; }
        .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>NEURAL TOPOLOGY</h1>
        <div>ATOM: Star (hover=info)</div>
        <div>SIZE: Mass (1/log(2+d))</div>
        <div>SYNAPSE: Conductivity</div>
        <div class="legend">
            <div><span class="dot" style="background:#79c0ff;box-shadow:0 0 8px #79c0ff"></span>SOLID (Anchor)</div>
            <div><span class="dot" style="background:#444"></span>GAS (Noise)</div>
        </div>
        <div style="margin-top:15px;color:#444">
            Scroll=Zoom | Drag=Rotate | Click=Search
        </div>
    </div>
    
    <div id="graph"></div>
    
    <script>
        fetch('/api/graph')
            .then(r => r.json())
            .then(data => {
                // Store original node data in lookup map (3d-force-graph mutates nodes)
                const nodeMap = {};
                data.nodes.forEach(n => { nodeMap[n.id] = n; });
                
                ForceGraph3D()
                    (document.getElementById('graph'))
                    .backgroundColor('#000000')
                    .showNavInfo(false)
                    .nodeId('id')  // Ensure we use 'id' as node identifier
                    .graphData({
                        nodes: data.nodes,
                        links: data.edges.map(e => ({source: e.source, target: e.target, value: e.weight}))
                    })
                    
                    // ═══════════════════════════════════════
                    // PHYSICS (INVARIANT LAWS)
                    // ═══════════════════════════════════════
                    
                    // GRAVITY: Weight → Distance
                    // Strong connection (0.9) → close together
                    // Weak connection (0.1) → far apart
                    .d3Force('link', d3.forceLink().id(d => d.id)
                        .distance(link => 300 * (1 - link.value))
                        .strength(link => link.value * 0.5)
                    )
                    
                    // REPULSION: Mass → Space
                    // Heavy words push neighbors away
                    .d3Force('charge', d3.forceManyBody()
                        .strength(node => -100 - (node.mass * 1000))
                    )
                    
                    // ═══════════════════════════════════════
                    // MATTER (Stars as Atoms)
                    // ═══════════════════════════════════════
                    
                    // SIZE = Mass (Information density)
                    .nodeVal(node => {
                        const n = nodeMap[node.id];
                        return n ? (2 + n.mass * 25) : 5;
                    })
                    
                    // COLOR = Phase (Temperature)
                    // Solid (Ice/Anchor) = Bright Blue
                    // Gas (Noise) = Dim Grey
                    .nodeColor(node => {
                        const n = nodeMap[node.id];
                        if (!n) return '#888888';
                        return n.phase === 'solid' ? '#79c0ff' : '#555555';
                    })
                    .nodeOpacity(0.9)
                    
                    // LABEL = Plain text tooltip
                    .nodeLabel(node => {
                        const n = nodeMap[node.id];
                        if (!n) return node.id;
                        return n.label + ' | mass:' + n.mass.toFixed(3) + ' | deg:' + n.degree + ' | ' + n.phase;
                    })
                    
                    // ═══════════════════════════════════════
                    // SYNAPSES (Conductivity)
                    // ═══════════════════════════════════════
                    
                    // Faint lines showing the connectome structure
                    .linkWidth(link => 0.5 + link.value * 1.5)
                    .linkOpacity(0.08)  // Very faint - just "dust" in space
                    .linkColor(() => '#333333')
                    
                    // IMPULSES (Particles showing potential)
                    .linkDirectionalParticles(1)
                    .linkDirectionalParticleSpeed(link => link.value * 0.003)
                    .linkDirectionalParticleWidth(1.5)
                    .linkDirectionalParticleColor(() => '#555555')
                    
                    // INTERACTION
                    .onNodeClick(node => {
                        window.location.href = '/?q=' + encodeURIComponent(node.label);
                    });
            });
    </script>
</body>
</html>'''
        self.send_html(graph3d_html)
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
    
    def api_suggest(self, query_string: str):
        """Autocomplete suggestions from local + global."""
        params = urllib.parse.parse_qs(query_string)
        q = params.get('q', [''])[0].strip().lower()
        
        if len(q) < 2:
            self.send_json({'suggestions': []})
            return
        
        physics = UIHandler.physics
        overlay = UIHandler.overlay
        suggestions = []
        
        # 1. Local words (from overlay labels) — highest priority
        if overlay:
            for h8, label in overlay.labels.items():
                if label and label.lower().startswith(q):
                    suggestions.append({
                        'word': label,
                        'source': 'local',
                        'hash8': h8
                    })
        
        # 2. Global suggestions via halo lookup
        if physics and len(suggestions) < 10:
            try:
                # Try to resolve the prefix and get neighbors
                h8 = hash8_hex(f"Ġ{q}")
                result = physics._client.get_halo_page(h8, limit=20)
                if result.get('exists') or result.get('neighbors'):
                    # Add the word itself
                    if not any(s['word'].lower() == q for s in suggestions):
                        suggestions.append({
                            'word': q,
                            'source': 'global',
                            'hash8': h8
                        })
                    # Add top neighbors as suggestions
                    neighbor_hashes = [n['hash8'] for n in result.get('neighbors', [])[:10]]
                    if neighbor_hashes:
                        labels = physics._client.get_labels_batch(neighbor_hashes)
                        for h8, label in labels.items():
                            if label and label.lower().startswith(q[:2]):
                                suggestions.append({
                                    'word': label,
                                    'source': 'global',
                                    'hash8': h8
                                })
            except Exception:
                pass
        
        # Dedupe and limit
        seen = set()
        unique = []
        for s in suggestions:
            key = s['word'].lower()
            if key not in seen:
                seen.add(key)
                unique.append(s)
        
        # Sort: local first, then alphabetically
        unique.sort(key=lambda x: (0 if x['source'] == 'local' else 1, x['word'].lower()))
        
        self.send_json({'suggestions': unique[:10]})
    
    def api_ingest(self):
        """Ingest document via POST."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            import math
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
            unique_words = list(dict.fromkeys(words))[:500]  # Process up to 500 unique words
            
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
            
            # Mass filter (INVARIANTS.md): keep Solid anchors (mass > mean_mass)
            mean_mass = physics.mean_mass
            candidates: list[tuple[str, str, float]] = []
            for word in unique_words:
                h8 = word_to_hash.get(word)
                if not h8:
                    continue
                result = batch_results.get(h8) or {}
                if not result.get('exists'):
                    continue
                meta = result.get('meta') or {}
                try:
                    degree_total = int(meta.get('degree_total') or 0)
                except Exception:
                    degree_total = 0
                try:
                    mass = 1.0 / math.log(2 + max(0, degree_total))
                except Exception:
                    mass = 0.0
                candidates.append((word, h8, mass))
            
            solid = [(w, h8) for (w, h8, m) in candidates if m > mean_mass]
            
            # Fallback: if too few anchors, take top-N by mass (preserve original order).
            if len(solid) >= 2:
                anchors = solid
            else:
                top = sorted(candidates, key=lambda x: x[2], reverse=True)[:64]
                top_set = {h8 for (_, h8, _) in top}
                anchors = [(w, h8) for (w, h8, _) in candidates if h8 in top_set]
            
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
            
            # Clear caches (graph depends on overlay contents).
            UIHandler._graph_cache_key = None
            UIHandler._graph_cache_value = None
            
            self.send_json({
                'success': True,
                'filename': filename,
                'scanned_words': len(unique_words),
                'candidates': len(candidates),
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
