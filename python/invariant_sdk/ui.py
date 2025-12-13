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
        <span><a href="/graph" style="color:#58a6ff">📊 2D</a> | <a href="/graph3d" style="color:#58a6ff">🌐 3D</a></span>
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
            self.serve_graph3d_page()
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
        """Return graph data for D3.js visualization."""
        import math
        overlay = UIHandler.overlay
        physics = UIHandler.physics
        mean_mass = physics.mean_mass if physics else 0.26
        
        nodes = []
        edges = []
        node_set = set()
        
        if overlay:
            # Collect all nodes
            for h8, label in overlay.labels.items():
                if label:
                    # Calculate mass from degree
                    degree = 0
                    if h8 in overlay.edges:
                        degree = len(overlay.edges[h8])
                    mass = 1.0 / math.log(2 + degree) if degree > 0 else 0.3
                    phase = 'solid' if mass > mean_mass else 'gas'
                    
                    nodes.append({
                        'id': h8,
                        'label': label,
                        'mass': mass,
                        'phase': phase,
                        'degree': degree
                    })
                    node_set.add(h8)
            
            # Collect edges (only between known nodes)
            for src, edge_list in overlay.edges.items():
                for edge in edge_list:
                    if src in node_set and edge.tgt in node_set:
                        edges.append({
                            'source': src,
                            'target': edge.tgt,
                            'weight': abs(edge.weight)
                        })
        
        self.send_json({'nodes': nodes, 'edges': edges})
    
    def serve_graph3d_page(self):
        """Serve 3D graph visualization page with Three.js."""
        overlay = UIHandler.overlay
        node_count = len(overlay.labels) if overlay else 0
        edge_count = overlay.n_edges if overlay else 0
        
        graph3d_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>3D Graph — Invariant</title>
    <script src="https://unpkg.com/3d-force-graph@1"></script>
    <style>
        * {{ margin: 0; padding: 0; }}
        body {{ 
            font-family: -apple-system, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            overflow: hidden;
        }}
        #graph3d {{ width: 100vw; height: 100vh; }}
        #info {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(22, 27, 34, 0.95);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #30363d;
            z-index: 100;
            max-width: 320px;
        }}
        #info h2 {{ color: #58a6ff; margin-bottom: 8px; font-size: 18px; }}
        #info p {{ font-size: 12px; color: #8b949e; margin: 4px 0; }}
        #info a {{ color: #58a6ff; }}
        .controls {{ margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; }}
        .controls button {{
            padding: 6px 10px;
            font-size: 11px;
            background: #21262d;
            border: 1px solid #30363d;
            color: #e6edf3;
            border-radius: 4px;
            cursor: pointer;
        }}
        .controls button:hover {{ background: #30363d; }}
        .controls button.active {{ background: #238636; border-color: #238636; }}
        .legend {{ display: flex; gap: 12px; margin-top: 10px; font-size: 11px; }}
        .legend span {{ display: flex; align-items: center; gap: 4px; }}
        .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        .stats {{ font-size: 11px; color: #484f58; margin-top: 8px; padding-top: 8px; border-top: 1px solid #21262d; }}
    </style>
</head>
<body>
    <div id="info">
        <h2>◆ 3D Knowledge Graph</h2>
        <p id="stats">Loading...</p>
        
        <div class="controls">
            <button onclick="toggleAnchorsOnly()" id="btnAnchors">◆ Anchors Only</button>
            <button onclick="toggleLabels()" id="btnLabels" class="active">📝 Labels</button>
            <button onclick="toggleRotate()" id="btnRotate" class="active">🔄 Rotate</button>
            <button onclick="resetView()">⟳ Reset</button>
        </div>
        
        <div class="legend">
            <span><div class="dot" style="background:#58a6ff"></div> Large = High Mass (anchor)</span>
        </div>
        <div class="legend">
            <span><div class="dot" style="background:#484f58"></div> Small = Low Mass (common)</span>
        </div>
        
        <p style="margin-top: 12px;">
            <a href="/graph">2D View</a> | <a href="/">Search</a>
        </p>
        
        <div class="stats">
            💡 Size = Information Content (Mass)<br>
            📐 Position = Semantic Similarity
        </div>
    </div>
    
    <div id="graph3d"></div>
    
    <script>
        let Graph;
        let allData;
        let showAnchorsOnly = false;
        let showLabels = true;
        let autoRotate = true;
        
        fetch('/api/graph')
            .then(res => res.json())
            .then(data => {{
                allData = data;
                
                // Stats
                const solidCount = data.nodes.filter(n => n.phase === 'solid').length;
                const gasCount = data.nodes.length - solidCount;
                document.getElementById('stats').innerHTML = 
                    `<strong>${{data.nodes.length}}</strong> nodes (<span style="color:#58a6ff">${{solidCount}} anchors</span>, ${{gasCount}} common) | <strong>${{data.edges.length}}</strong> edges`;
                
                renderGraph(data);
            }});
        
        function renderGraph(data) {{
            const container = document.getElementById('graph3d');
            container.innerHTML = '';
            
            Graph = ForceGraph3D()
                (container)
                .backgroundColor('#0d1117')
                .graphData({{
                    nodes: data.nodes,
                    links: data.edges.map(e => ({{
                        source: e.source,
                        target: e.target,
                        value: e.weight
                    }}))
                }})
                // SIZE: Mass determines size (bigger = more information)
                .nodeVal(n => {{
                    const baseSize = n.phase === 'solid' ? 8 : 2;
                    return baseSize + (n.mass * 15);
                }})
                // COLOR: Phase + degree for cluster hint
                .nodeColor(n => {{
                    if (n.phase === 'solid') {{
                        // Anchors: blue intensity by degree
                        const intensity = Math.min(255, 100 + n.degree * 10);
                        return `rgb(${{50}}, ${{intensity}}, 255)`;
                    }} else {{
                        // Gas: gray, dimmer
                        return '#484f58';
                    }}
                }})
                .nodeOpacity(n => n.phase === 'solid' ? 1 : 0.6)
                // LABELS: Only for solid nodes (anchors)
                .nodeThreeObject(n => {{
                    if (!showLabels || n.phase !== 'solid') return null;
                    
                    const sprite = new SpriteText(n.label);
                    sprite.color = '#e6edf3';
                    sprite.textHeight = 3 + n.mass * 5;
                    sprite.backgroundColor = 'rgba(13, 17, 23, 0.8)';
                    sprite.padding = 1;
                    sprite.borderRadius = 2;
                    return sprite;
                }})
                .nodeThreeObjectExtend(true)
                // LINKS
                .linkWidth(l => 0.5 + l.value * 1.5)
                .linkOpacity(0.3)
                .linkColor(() => '#30363d')
                // INTERACTION
                .onNodeClick(n => {{
                    window.location.href = '/?q=' + encodeURIComponent(n.label);
                }})
                .onNodeHover(n => {{
                    container.style.cursor = n ? 'pointer' : 'default';
                }})
                // PHYSICS: Mass affects repulsion (information spreads)
                .d3Force('charge', d3.forceManyBody().strength(n => {{
                    return n.phase === 'solid' ? -n.mass * 300 : -50;
                }}))
                .d3Force('link', d3.forceLink().distance(60).strength(l => l.value * 0.4));
            
            // Auto-rotate
            Graph.controls().autoRotate = autoRotate;
            Graph.controls().autoRotateSpeed = 0.3;
        }}
        
        function toggleAnchorsOnly() {{
            showAnchorsOnly = !showAnchorsOnly;
            document.getElementById('btnAnchors').classList.toggle('active', showAnchorsOnly);
            
            if (showAnchorsOnly) {{
                const solidNodes = allData.nodes.filter(n => n.phase === 'solid');
                const solidIds = new Set(solidNodes.map(n => n.id));
                const filteredEdges = allData.edges.filter(e => 
                    solidIds.has(e.source) && solidIds.has(e.target)
                );
                renderGraph({{ nodes: solidNodes, edges: filteredEdges }});
            }} else {{
                renderGraph(allData);
            }}
        }}
        
        function toggleLabels() {{
            showLabels = !showLabels;
            document.getElementById('btnLabels').classList.toggle('active', showLabels);
            Graph.nodeThreeObject(Graph.nodeThreeObject()); // Refresh
        }}
        
        function toggleRotate() {{
            autoRotate = !autoRotate;
            document.getElementById('btnRotate').classList.toggle('active', autoRotate);
            Graph.controls().autoRotate = autoRotate;
        }}
        
        function resetView() {{
            Graph.cameraPosition({{ x: 0, y: 0, z: 500 }}, {{ x: 0, y: 0, z: 0 }}, 1000);
        }}
    </script>
    <script src="https://unpkg.com/three-spritetext"></script>
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
