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
    from .ui_pages import render_main_page
except ImportError:
    from invariant_sdk.halo import hash8_hex
    from invariant_sdk.overlay import OverlayGraph, find_overlays
    from invariant_sdk.physics import HaloPhysics
    from invariant_sdk.ui_pages import render_main_page


DEFAULT_SERVER = "http://165.22.145.158:8080"


class UIHandler(BaseHTTPRequestHandler):
    """HTTP handler for Invariant UI."""
    
    physics: Optional[HaloPhysics] = None
    overlay: Optional[OverlayGraph] = None
    overlay_path: Optional[Path] = None
    
    _graph_cache_key: Optional[tuple] = None
    _graph_cache_value: Optional[dict] = None
    
    _degree_total_cache: Dict[str, int] = {}
    _degree_total_crystal_id: Optional[str] = None

    _ANCHOR_SCAN_RADIUS = 50
    
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
        elif parsed.path == '/graph3d':
            self.serve_graph3d_page(parsed.query)
        elif parsed.path == '/doc':
            self.serve_doc_page(parsed.query)
        elif parsed.path == '/api/search':
            self.api_search(parsed.query)
        elif parsed.path == '/api/suggest':
            self.api_suggest(parsed.query)
        elif parsed.path == '/api/graph':
            self.api_graph(parsed.query)
        elif parsed.path == '/api/docs':
            self.api_docs()
        elif parsed.path == '/api/status':
            self.api_status()
        elif parsed.path == '/api/verify':
            self.api_verify(parsed.query)
        elif parsed.path == '/api/context':
            self.api_context(parsed.query)
        elif parsed.path == '/api/open':
            self.api_open(parsed.query)
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/api/ingest':
            self.api_ingest()
        elif self.path == '/api/reindex':
            self.api_reindex()
        else:
            self.send_error(404)
    
    def serve_page(self):
        physics = UIHandler.physics
        overlay = UIHandler.overlay
        
        crystal_id = physics.crystal_id if physics else "Not connected"
        overlay_status = f"{overlay.n_edges} local edges" if overlay else "No local documents"

        self.send_html(
            render_main_page(
                crystal_id=crystal_id,
                overlay_status=overlay_status,
            )
        )

    def serve_doc_page(self, query_string: str = ""):
        """Document chooser + per-document view (local overlay)."""
        overlay = UIHandler.overlay
        physics = UIHandler.physics
        params = urllib.parse.parse_qs(query_string or "")
        doc = (params.get('doc', [''])[0] or '').strip()

        ui_font_links = (
            "<link rel='preconnect' href='https://fonts.googleapis.com'/>"
            "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin/>"
            "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'/>"
        )
        ui_css = (
            ":root{--bg:#0a0a0b;--surface:#111113;--surface2:#18181b;"
            "--border:rgba(255,255,255,0.08);--border2:rgba(255,255,255,0.12);"
            "--text:#fafafa;--text2:#a1a1aa;--text3:#71717a;"
            "--accent:#3b82f6;--accentDim:rgba(59,130,246,0.15);--success:#22c55e;}"
            "body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;"
            "background:radial-gradient(900px circle at 15% -10%, rgba(59,130,246,0.14), transparent 55%), var(--bg);"
            "color:var(--text);margin:0;padding:28px;-webkit-font-smoothing:antialiased;}"
            "h1{margin:0 0 10px;color:var(--text);font-size:22px;letter-spacing:-0.02em;}"
            ".sub{color:var(--text2);margin:0 0 18px;font-size:13px;font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;}"
            "a{color:var(--accent);text-decoration:none;}"
            "a:hover{text-decoration:underline;}"
        )
        
        if not overlay:
            self.send_html(
                "<!doctype html><html><body style='font-family:-apple-system;padding:24px;'>"
                "<h1>Docs</h1><p>No local documents yet.</p><p><a href='/'>Back</a></p>"
                "</body></html>"
            )
            return
        
        # Build doc stats
        docs: dict[str, dict] = {}
        for src, edge_list in overlay.edges.items():
            for edge in edge_list:
                if not edge.doc:
                    continue
                d = docs.get(edge.doc)
                if d is None:
                    d = {'doc': edge.doc, 'edges': 0, 'nodes': set()}
                    docs[edge.doc] = d
                d['edges'] += 1
                d['nodes'].add(src)
                d['nodes'].add(edge.tgt)
        
        if not doc:
            items = []
            for name, d in sorted(docs.items(), key=lambda kv: (-kv[1]['edges'], kv[0].lower())):
                items.append(
                    f"<a class='item' href='/doc?doc={urllib.parse.quote(name)}'>"
                    f"<span class='name'>{html.escape(name)}</span>"
                    f"<span class='meta'>{d['edges']} edges • {len(d['nodes'])} nodes</span>"
                    f"</a>"
                )
            crystal = html.escape(physics.crystal_id if physics else "unknown")
            page = (
                "<!doctype html><html><head><meta charset='utf-8'/>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                + ui_font_links +
                "<title>Docs — Invariant</title>"
                "<style>"
                + ui_css +
                ".list{display:flex;flex-direction:column;gap:10px;max-width:760px;}"
                ".item{display:flex;justify-content:space-between;gap:12px;align-items:center;"
                "padding:12px 14px;border:1px solid var(--border);border-radius:12px;background:rgba(17,17,19,0.85);"
                "text-decoration:none;color:var(--text);}"
                ".item:hover{border-color:rgba(59,130,246,0.65);background:var(--accentDim);}"
                ".name{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}"
                ".meta{color:var(--text3);font-size:12px;white-space:nowrap;"
                "font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;}"
                "</style></head><body>"
                f"<h1>Docs</h1><p class='sub'>Crystal: <strong>{crystal}</strong> • choose a document overlay</p>"
                "<p><a href='/'>← Back to search</a></p>"
                "<div class='list'>"
                + "".join(items)
                + "</div></body></html>"
            )
            self.send_html(page)
            return
        
        if doc not in docs:
            self.send_error(404, "Unknown document")
            return
        
        d = docs[doc]
        doc_q = urllib.parse.quote(doc)
        graph_href = f"/graph3d?doc={doc_q}"
        graph_embed = f"/graph3d?embed=1&doc={doc_q}"
        
        # Collect nodes in this doc (sorted by label)
        nodes = sorted((overlay.labels.get(h8) or h8[:8], h8) for h8 in d['nodes'])
        node_links = []
        for label, _h8 in nodes[:400]:
            q = urllib.parse.quote(label)
            node_links.append(
                f"<a class='pill' href='/?q={q}&doc={doc_q}'>{html.escape(label)}</a>"
            )
        
        crystal = html.escape(physics.crystal_id if physics else "unknown")
        page = (
            "<!doctype html><html><head><meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
            + ui_font_links +
            "<title>Doc — Invariant</title>"
            "<style>"
            + ui_css +
            ".row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:10px 0 16px;}"
            ".row a{font-size:13px;}"
            ".frame{width:100%;height:70vh;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:rgba(255,255,255,0.02);}"
            "iframe{width:100%;height:100%;border:0;}"
            ".pills{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px;max-width:1100px;}"
            ".pill{padding:6px 10px;border:1px solid var(--border);border-radius:999px;background:rgba(17,17,19,0.85);"
            "text-decoration:none;color:var(--text);font-size:12px;font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;}"
            ".pill:hover{border-color:rgba(59,130,246,0.65);background:var(--accentDim);}"
            "</style></head><body>"
            f"<h1>{html.escape(doc)}</h1>"
            f"<p class='sub'>Crystal: <strong>{crystal}</strong> • {d['edges']} edges • {len(d['nodes'])} nodes</p>"
            "<div class='row'>"
            f"<a href='/'>← Back</a>"
            f"<a href='{graph_href}' target='_blank'>Open 3D</a>"
            f"<a href='/doc'>All docs</a>"
            "</div>"
            f"<div class='frame'><iframe src='{graph_embed}'></iframe></div>"
            "<div class='pills'>"
            + "".join(node_links)
            + "</div>"
            "</body></html>"
        )
        self.send_html(page)
    
    def api_graph(self, query_string: str = ""):
        """Return (optionally filtered) local overlay graph with physics fields."""
        import math
        
        overlay = UIHandler.overlay
        physics = UIHandler.physics
        mean_mass = physics.mean_mass if physics else 0.26
        
        if not overlay:
            self.send_json({'nodes': [], 'edges': [], 'mean_mass': mean_mass})
            return
        
        params = urllib.parse.parse_qs(query_string or "")
        doc_filter = (params.get('doc', [''])[0] or '').strip()
        focus = (params.get('focus', [''])[0] or '').strip()
        try:
            radius = int(params.get('radius', ['0'])[0])
        except Exception:
            radius = 0
        try:
            max_nodes = int(params.get('max_nodes', ['0'])[0])
        except Exception:
            max_nodes = 0
        
        # Resolve focus (hash8 or label) -> hash8
        focus_id: Optional[str] = None
        if focus:
            if re.fullmatch(r'[0-9a-fA-F]{16}', focus):
                focus_id = focus.lower()
            else:
                needle = focus.strip().lower()
                for h8, label in overlay.labels.items():
                    if label and label.strip().lower() == needle:
                        focus_id = h8
                        break
        
        # Build filtered edge list (doc filter applies only to local edges).
        edge_rows: list[tuple[str, str, float]] = []
        node_set: set[str] = set()
        for src, edge_list in overlay.edges.items():
            for edge in edge_list:
                if doc_filter and edge.doc != doc_filter:
                    continue
                node_set.add(src)
                node_set.add(edge.tgt)
                edge_rows.append((src, edge.tgt, abs(edge.weight)))
        
        if not node_set:
            self.send_json({'nodes': [], 'edges': [], 'mean_mass': mean_mass, 'doc': doc_filter or None})
            return
        
        # Focused subgraph (BFS radius) to keep embedded views small.
        if focus_id and radius > 0 and focus_id in node_set:
            adj: dict[str, set[str]] = {h8: set() for h8 in node_set}
            for a, b, _w in edge_rows:
                if a in adj:
                    adj[a].add(b)
                if b in adj:
                    adj[b].add(a)
            keep = {focus_id}
            frontier = {focus_id}
            for _ in range(radius):
                nxt = set()
                for u in frontier:
                    nxt.update(adj.get(u, ()))
                nxt -= keep
                keep |= nxt
                frontier = nxt
                if not frontier:
                    break
            node_set = keep
            edge_rows = [(a, b, w) for (a, b, w) in edge_rows if a in node_set and b in node_set]
        
        # Optional hard cap (only meaningful with focus).
        if max_nodes and focus_id and len(node_set) > max_nodes:
            # Keep closest nodes by BFS order (already in keep), just trim deterministically.
            trimmed = list(node_set)
            trimmed.sort()
            node_set = set(trimmed[:max_nodes])
            if focus_id not in node_set:
                node_set.add(focus_id)
            edge_rows = [(a, b, w) for (a, b, w) in edge_rows if a in node_set and b in node_set]
        
        degree_local: dict[str, int] = {h8: 0 for h8 in node_set}
        edges: list[dict] = []
        for a, b, w in edge_rows:
            edges.append({'source': a, 'target': b, 'weight': w})
            degree_local[a] = degree_local.get(a, 0) + 1
            degree_local[b] = degree_local.get(b, 0) + 1
        
        # Degree_total cache (HALO_SPEC): required for deterministic Mass.
        if physics:
            if UIHandler._degree_total_crystal_id != physics.crystal_id:
                UIHandler._degree_total_crystal_id = physics.crystal_id
                UIHandler._degree_total_cache = {}
        
        degree_total: dict[str, int] = {}
        if physics and node_set:
            missing = [h8 for h8 in node_set if h8 not in UIHandler._degree_total_cache]
            if missing:
                try:
                    results = physics._client.get_halo_pages(missing, limit=0)
                    for h8, result in results.items():
                        meta = result.get('meta') or {}
                        try:
                            UIHandler._degree_total_cache[h8] = int(meta.get('degree_total') or 0)
                        except Exception:
                            UIHandler._degree_total_cache[h8] = 0
                except Exception:
                    pass
            for h8 in node_set:
                if h8 in UIHandler._degree_total_cache:
                    degree_total[h8] = UIHandler._degree_total_cache[h8]
        
        nodes: list[dict] = []
        for h8 in sorted(node_set):
            label = overlay.labels.get(h8) or h8[:8]
            deg_total = degree_total.get(h8, degree_local.get(h8, 0))
            try:
                mass = 1.0 / math.log(2 + max(0, int(deg_total)))
            except Exception:
                mass = 0.0
            phase = 'solid' if mass > mean_mass else 'gas'
            nodes.append({
                'id': h8,
                'label': label,
                'mass': mass,
                'phase': phase,
                'degree': degree_local.get(h8, 0),
                'degree_total': int(deg_total),
            })
        
        self.send_json({
            'nodes': nodes,
            'edges': edges,
            'mean_mass': mean_mass,
            'doc': doc_filter or None,
            'focus': focus_id,
            'radius': radius,
        })

    def serve_graph3d_page(self, query_string: str = ""):
        """3D molecule view (WebGL) with doc/focus filtering."""
        graph3d_html = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>3D Molecule — Invariant</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/3d-force-graph"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0a0a0b;
      --surface: #111113;
      --surface-2: #18181b;
      --border: rgba(255,255,255,0.08);
      --border-2: rgba(255,255,255,0.12);
      --text: #fafafa;
      --text-2: #a1a1aa;
      --text-3: #71717a;
      --accent: #3b82f6;
      --accent-dim: rgba(59,130,246,0.15);
      --success: #22c55e;
      --warning: #f59e0b;
      --danger: #ef4444;
    }
    body {
      background: radial-gradient(900px circle at 15% -10%, rgba(59,130,246,0.14), transparent 55%), var(--bg);
      color: var(--text);
      overflow: hidden;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    #graph { position: absolute; inset: 0; }
    #labels { position: absolute; inset: 0; pointer-events: none; }
    .lbl {
      position: absolute;
      padding: 2px 6px;
      border-radius: 6px;
      background: rgba(10, 10, 11, 0.72);
      border: 1px solid rgba(255,255,255,0.10);
      font: 12px/1.3 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      white-space: nowrap;
      transform: translate(-50%, -135%);
    }
    .lbl.solid { border-color: rgba(59,130,246,0.55); }
    #hud {
      position: fixed;
      top: 14px;
      left: 14px;
      width: 360px;
      background: rgba(17, 17, 19, 0.92);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 12px;
      z-index: 10;
      backdrop-filter: blur(6px);
    }
    #hud h1 { font-size: 12px; color: var(--accent); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px; }
    #hud .row { font: 12px/1.4 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; color: var(--text-3); margin: 3px 0; }
    #hud .row span { color: var(--text); }
    #hud .btns { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
    #hud button {
      background: rgba(255,255,255,0.03); color: var(--text); border: 1px solid var(--border);
      padding: 6px 8px; border-radius: 8px; cursor: pointer;
      font-size: 12px;
    }
    #hud button.active { border-color: rgba(59,130,246,0.7); background: var(--accent-dim); }
    #hud a { color: var(--accent); text-decoration: none; }
    body.embed #hud { display: none; }
    .graph-tooltip { display: none !important; }
  </style>
</head>
<body>
  <div id="graph"></div>
  <div id="labels"></div>
  <div id="hud">
    <h1>3D Molecule</h1>
    <div class="row">Doc: <span id="docName">—</span></div>
    <div class="row">Nodes: <span id="nNodes">0</span> • Edges: <span id="nEdges">0</span></div>
    <div class="row">Focus: <span id="focusName">—</span></div>
    <div class="row">Hover: <span id="hoverName">—</span></div>
    <div class="row">Size = <span>Mass</span> • Color = <span>Temperature</span> • Distance = <span>Weight</span></div>
    <div class="row">Drag=Rotate • Right/Shift=Pan • Wheel=Zoom</div>
    <div class="btns">
      <button id="btnLabels" class="active">Labels</button>
      <button id="btnAnchors">Anchors</button>
      <button id="btnFit">Fit</button>
      <a id="backLink" href="/">Back</a>
    </div>
  </div>
  <script>
  (async function () {
    const params = new URLSearchParams(window.location.search);
    const embed = params.get('embed') === '1';
    if (embed) document.body.classList.add('embed');

    const doc = (params.get('doc') || '').trim();
    const focusParam = (params.get('focus') || '').trim();
    const radius = (params.get('radius') || (embed ? '1' : '0')).trim();
    const maxNodes = (params.get('max_nodes') || (embed ? '180' : '0')).trim();

    const api = new URL('/api/graph', window.location.origin);
    if (doc) api.searchParams.set('doc', doc);
    if (focusParam) api.searchParams.set('focus', focusParam);
    if (radius && radius !== '0') api.searchParams.set('radius', radius);
    if (maxNodes && maxNodes !== '0') api.searchParams.set('max_nodes', maxNodes);

    const graphEl = document.getElementById('graph');
    const labelsEl = document.getElementById('labels');

    const res = await fetch(api.toString());
    const data = await res.json();
    const nodes = (data.nodes || []).map(n => ({ ...n }));
    const edges = (data.edges || []).map(e => ({ ...e }));

    document.getElementById('docName').textContent = data.doc || (doc ? doc : 'all');
    document.getElementById('nNodes').textContent = String(nodes.length);
    document.getElementById('nEdges').textContent = String(edges.length);

    if (!nodes.length) {
      document.getElementById('focusName').textContent = '—';
      graphEl.innerHTML = '<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:rgba(255,255,255,0.55);font:14px Inter, -apple-system;">No local graph</div>';
      return;
    }

    const links = edges.map(e => ({ source: e.source, target: e.target, value: +e.weight || 0 }));

    // Temperature: monotonic with log-degree_total.
    const degLogs = nodes.map(n => Math.log(2 + Math.max(0, +n.degree_total || 0)));
    const minLog = Math.min(...degLogs);
    const maxLog = Math.max(...degLogs);
    const cold = [121, 192, 255]; // #79c0ff
    const hot = [255, 123, 114];  // #ff7b72
    const clamp01 = (x) => Math.max(0, Math.min(1, x));
    const temp01 = (n) => {
      const v = Math.log(2 + Math.max(0, +n.degree_total || 0));
      if (maxLog <= minLog) return 0;
      return clamp01((v - minLog) / (maxLog - minLog));
    };
    const tempColor = (t) => {
      t = clamp01(t);
      const r = Math.round(cold[0] + (hot[0] - cold[0]) * t);
      const g = Math.round(cold[1] + (hot[1] - cold[1]) * t);
      const b = Math.round(cold[2] + (hot[2] - cold[2]) * t);
      return `rgb(${r},${g},${b})`;
    };

    const byId = new Map(nodes.map(n => [n.id, n]));
    const adj = new Map(nodes.map(n => [n.id, new Set()]));
    links.forEach(l => {
      adj.get(l.source)?.add(l.target);
      adj.get(l.target)?.add(l.source);
    });

    const focusId = data.focus || (focusParam && byId.has(focusParam) ? focusParam : null);
    const focusNode = focusId ? byId.get(focusId) : null;
    document.getElementById('focusName').textContent = focusNode ? focusNode.label : (focusParam || '—');

    let showLabels = params.get('labels') !== '0';
    let anchorsOnly = false;
    let hoveredId = null;

    const Graph = ForceGraph3D()(graphEl)
      .backgroundColor('#0a0a0b')
      .showNavInfo(false)
      .nodeId('id')
      .graphData({ nodes, links })
      .nodeVal(n => 2 + (Math.max(0, +n.mass || 0) * 10))
      .nodeColor(n => tempColor(temp01(n)))
      .nodeOpacity(0.95)
      .linkWidth(l => 0.3 + (clamp01(+l.value || 0) * 1.6))
      .linkOpacity(embed ? 0.25 : 0.16)
      .linkColor(() => '#30363d')
      .onNodeHover(n => {
        const nid = n ? n.id : null;
        if (nid === hoveredId) return;
        hoveredId = nid;
        document.getElementById('hoverName').textContent = n ? n.label : '—';
        scheduleLabels();
      })
      .onNodeClick(n => {
        if (embed) return;
        const url = new URL('/', window.location.origin);
        url.searchParams.set('q', n.label);
        if (doc) url.searchParams.set('doc', doc);
        window.location.href = url.toString();
      })
      // Disable built-in hover tooltip (it can interfere with navigation); HUD + labels are enough.
      .nodeLabel(() => '');

    // Physics mapping: weight affects distance/strength; mass affects charge (space).
    Graph.d3Force('link')
      .distance(l => 80 + (1 - clamp01(+l.value || 0)) * 220)
      .strength(l => Math.max(0.05, clamp01(+l.value || 0)));
    Graph.d3Force('charge')
      .strength(n => -40 - (Math.max(0, +n.mass || 0) * 160));

    const controls = Graph.controls();
    if (controls && controls.addEventListener) {
      // Disable default zoom: we implement cursor-centered zoom ourselves.
      try { controls.enableZoom = false; } catch (e) {}
      controls.addEventListener('change', () => scheduleLabels());
    }
    window.addEventListener('resize', () => scheduleLabels());

    // Cursor-centered zoom (zoom towards mouse pointer, not scene center).
    // This matches the UI expectation: wheel zoom should move into the point under the cursor.
    graphEl.addEventListener('wheel', (e) => {
      if (!controls || typeof Graph.screen2GraphCoords !== 'function') return;
      e.preventDefault();
      e.stopPropagation();

      const rect = graphEl.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;

      const cam = Graph.camera();
      if (!cam) return;

      const target = controls.target.clone();
      const dist = cam.position.distanceTo(target);
      if (!isFinite(dist) || dist <= 0) return;

      // Exponential zoom feels natural across mouse wheels and trackpads.
      const scale = Math.exp(e.deltaY * 0.0012);
      const minDist = 18;
      const maxDist = 8000;
      const nextDist = Math.max(minDist, Math.min(maxDist, dist * scale));

      // Approximate the world point under cursor at the current target depth.
      const cursor = Graph.screen2GraphCoords(sx, sy, dist);
      const dir = cam.position.clone().sub(cursor).normalize();
      if (!isFinite(dir.length()) || dir.length() === 0) return;

      cam.position.copy(cursor.clone().add(dir.multiplyScalar(nextDist)));
      controls.target.copy(cursor);
      controls.update();
      scheduleLabels();
    }, { passive: false });

    // HTML labels (caption near sphere)
    const labelEls = new Map();
    nodes.forEach(n => {
      const el = document.createElement('div');
      el.className = 'lbl' + (n.phase === 'solid' ? ' solid' : '');
      el.textContent = n.label;
      labelsEl.appendChild(el);
      labelEls.set(n.id, el);
    });

    function labelVisible(nid) {
      if (!showLabels) return false;
      const n = byId.get(nid);
      if (!n) return false;
      if (anchorsOnly && !(n.mass > (data.mean_mass || 0.26))) return false;
      if (embed) {
        if (hoveredId) return nid === hoveredId || adj.get(hoveredId)?.has(nid);
        if (focusId) return nid === focusId || adj.get(focusId)?.has(nid);
        return n.mass > (data.mean_mass || 0.26);
      }
      if (hoveredId) return nid === hoveredId || adj.get(hoveredId)?.has(nid);
      if (focusId) return nid === focusId || adj.get(focusId)?.has(nid);
      return n.mass > (data.mean_mass || 0.26);
    }

    let lastLbl = 0;
    let lblRaf = null;
    function updateLabels() {
      lblRaf = null;
      const now = performance.now();
      if (now - lastLbl < 25) return;
      lastLbl = now;
      const rect = graphEl.getBoundingClientRect();
      nodes.forEach(n => {
        const el = labelEls.get(n.id);
        if (!el) return;
        if (!labelVisible(n.id) || n.x == null) {
          el.style.display = 'none';
          return;
        }
        const c = Graph.graph2ScreenCoords(n.x, n.y, n.z);
        if (c.x < -50 || c.y < -50 || c.x > rect.width + 50 || c.y > rect.height + 50) {
          el.style.display = 'none';
          return;
        }
        el.style.display = 'block';
        el.style.left = c.x + 'px';
        el.style.top = c.y + 'px';
      });
    }
    function scheduleLabels() {
      if (lblRaf) return;
      lblRaf = requestAnimationFrame(updateLabels);
    }
    Graph.onEngineTick(scheduleLabels);
    Graph.onEngineStop(scheduleLabels);

    // Fit/focus
    setTimeout(() => {
      try {
        if (focusId) {
          Graph.zoomToFit(700, 80, n => n.id === focusId || adj.get(focusId)?.has(n.id));
        } else {
          Graph.zoomToFit(700, 80);
        }
      } catch (e) {}
    }, 600);

    // HUD controls
    const btnLabels = document.getElementById('btnLabels');
    const btnAnchors = document.getElementById('btnAnchors');
    const btnFit = document.getElementById('btnFit');
    const backLink = document.getElementById('backLink');
    if (embed) {
      // no-op
    } else {
      if (doc) {
        const url = new URL('/', window.location.origin);
        url.searchParams.set('doc', doc);
        backLink.href = url.toString();
      }
      btnLabels.classList.toggle('active', showLabels);
      btnLabels.onclick = () => {
        showLabels = !showLabels;
        btnLabels.classList.toggle('active', showLabels);
        scheduleLabels();
      };
      btnAnchors.onclick = () => {
        anchorsOnly = !anchorsOnly;
        btnAnchors.classList.toggle('active', anchorsOnly);
        scheduleLabels();
      };
      btnFit.onclick = () => {
        try { Graph.zoomToFit(700, 80); } catch (e) {}
      };
    }
  })();
  </script>
</body>
</html>'''
        self.send_html(graph3d_html)
    def api_search(self, query_string: str):
        params = urllib.parse.parse_qs(query_string)
        q = params.get('q', [''])[0].strip()
        doc_filter = (params.get('doc', [''])[0] or '').strip()
        
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
                is_local = (n.get('source') == 'local') or (doc is not None)
                line = n.get('line') if is_local else None
                ctx_hash = n.get('ctx_hash') if is_local else None
                
                if is_local and doc_filter and doc != doc_filter:
                    continue
                
                # Get human-readable label: LOCAL overlay first, then global server
                source = 'local' if is_local else 'global'
                label = overlay.get_label(h8) if (is_local and overlay) else None
                
                # Fallback: use global server label
                if not label:
                    label = global_labels.get(h8)
                
                # Final fallback: hash prefix
                if not label:
                    label = h8[:12] + '...'
                
                neighbor_data = {
                    'hash8': h8,
                    'label': label,
                    'weight': weight,
                    'source': source,
                    'doc': doc
                }
                # Include provenance if available
                if line is not None:
                    neighbor_data['line'] = line
                if ctx_hash:
                    neighbor_data['ctx_hash'] = ctx_hash
                
                neighbors.append(neighbor_data)
            
            # Sort: local first, then by weight
            neighbors.sort(key=lambda x: (0 if x['source'] == 'local' else 1, -abs(x['weight'])))
            
            # Response includes physics properties
            self.send_json({
                'query': q,
                'doc': doc_filter or None,
                'mode': search_mode,  # Honest: tells user what mode was used
                'phase': concept.phase,  # solid/gas
                'mass': concept.mass,  # information content
                'mean_mass': physics.mean_mass,  # phase boundary
                'atoms': concept.atoms,  # resolved hash8 atoms
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
            
            # Import uploaded doc into local storage (so it can be opened / used for context later).
            # This does not duplicate the overlay — it creates the σ-source file itself.
            safe_name = Path(str(filename)).name or "document.txt"
            stored_doc = safe_name
            try:
                uploads_dir = Path('./.invariant/uploads')
                uploads_dir.mkdir(parents=True, exist_ok=True)
                save_path = uploads_dir / safe_name
                save_path.write_text(text, encoding='utf-8')
                stored_doc = str(Path('uploads') / safe_name)
            except Exception:
                stored_doc = safe_name
            
            physics = UIHandler.physics
            overlay = UIHandler.overlay
            overlay_path = UIHandler.overlay_path
            
            if not physics:
                self.send_json({'error': 'Not connected'}, 500)
                return
            
            # Tokenize with line positions (Anchor Integrity Protocol needs stable coordinates).
            tokens: list[tuple[str, int]] = []
            lines = text.split('\n')
            for line_num, line in enumerate(lines, 1):
                for match in re.finditer(r'\b[a-zA-Z]{3,}\b', line):
                    tokens.append((match.group().lower(), line_num))
            
            words = [w for (w, _ln) in tokens]
            unique_words = list(dict.fromkeys(words))[:500]  # limit network + processing
            
            # Find anchors using single BATCH API call (O(1) network round-trip)
            # Server now properly supports limit=0 for meta-only checks
            word_to_hash = {w: hash8_hex(f"Ġ{w}") for w in unique_words}
            
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
            
            anchor_words = {w for (w, _h8) in anchors}
            
            # Anchor Integrity Protocol: ctx_hash for anchor window (±2 words)
            import hashlib
            def compute_ctx_hash_at(idx: int, k: int = 2) -> str:
                start = max(0, idx - k)
                end = min(len(tokens), idx + k + 1)
                window_words = [tokens[i][0] for i in range(start, end)]
                normalized = ' '.join(w.lower() for w in window_words)
                return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
            
            # Collect anchor occurrences in original order for edge construction.
            occurrences: list[tuple[str, str, int, str]] = []
            for idx, (word, line_no) in enumerate(tokens):
                if word not in anchor_words:
                    continue
                h8 = word_to_hash.get(word) or hash8_hex(f"Ġ{word}")
                occurrences.append((word, h8, line_no, compute_ctx_hash_at(idx)))
            
            if len(occurrences) < 2:
                self.send_json({'error': 'Too few anchor occurrences found'}, 400)
                return
            
            # Create edges
            if overlay is None:
                overlay = OverlayGraph()
                UIHandler.overlay = overlay
            
            edges_added = 0
            for i in range(len(occurrences) - 1):
                src_word, src_h8, _src_line, _src_ctx = occurrences[i]
                tgt_word, tgt_h8, tgt_line, tgt_ctx = occurrences[i + 1]
                
                overlay.add_edge(
                    src_h8,
                    tgt_h8,
                    weight=1.0,
                    doc=stored_doc,
                    line=tgt_line,
                    ctx_hash=tgt_ctx,
                )
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
                'filename': stored_doc,
                'scanned_words': len(unique_words),
                'candidates': len(candidates),
                'anchors': len(anchor_words),
                'edges': edges_added
            })
            
        except json.JSONDecodeError:
            self.send_json({'error': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def api_reindex(self):
        """
        Re-index an existing local document (replace σ-edges for that doc).
        
        Motivation:
        - Older overlays may lack line/ctx_hash provenance.
        - Reindex rebuilds σ-edges with Anchor Integrity Protocol fields so UI can show context + open file.
        """
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            import math
            data = json.loads(body)
            doc = (data.get('doc') or '').strip()
            if not doc:
                self.send_json({'error': 'Missing doc'}, 400)
                return
            
            physics = UIHandler.physics
            overlay = UIHandler.overlay
            overlay_path = UIHandler.overlay_path
            
            if not physics or not overlay:
                self.send_json({'error': 'No overlay loaded. Ingest documents first.'}, 400)
                return
            
            doc_path, searched = self._resolve_doc_path(doc)
            if not doc_path:
                self.send_json({'error': f'Document not found: {doc}', 'searched': [str(c) for c in searched]}, 404)
                return
            
            text = doc_path.read_text(encoding='utf-8')
            if not text.strip():
                self.send_json({'error': 'Document is empty'}, 400)
                return
            
            # Remove existing edges for this doc (replace)
            removed = 0
            for src in list(overlay.edges.keys()):
                before = len(overlay.edges[src])
                overlay.edges[src] = [e for e in overlay.edges[src] if e.doc != doc]
                removed += before - len(overlay.edges[src])
                if not overlay.edges[src]:
                    del overlay.edges[src]
            
            # Tokenize with line positions
            tokens: list[tuple[str, int]] = []
            lines = text.split('\n')
            for line_num, line in enumerate(lines, 1):
                for match in re.finditer(r'\b[a-zA-Z]{3,}\b', line):
                    tokens.append((match.group().lower(), line_num))
            
            words = [w for (w, _ln) in tokens]
            unique_words = list(dict.fromkeys(words))[:500]
            word_to_hash = {w: hash8_hex(f"Ġ{w}") for w in unique_words}
            
            try:
                batch_results = physics._client.get_halo_pages(word_to_hash.values(), limit=0)
            except Exception as e:
                self.send_json({'error': f'Server error: {e}'}, 500)
                return
            
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
            if len(solid) >= 2:
                anchors = solid
            else:
                top = sorted(candidates, key=lambda x: x[2], reverse=True)[:64]
                top_set = {h8 for (_, h8, _) in top}
                anchors = [(w, h8) for (w, h8, _) in candidates if h8 in top_set]
            
            if len(anchors) < 2:
                self.send_json({'error': 'Too few concepts found in document'}, 400)
                return
            
            anchor_words = {w for (w, _h8) in anchors}
            
            import hashlib
            def compute_ctx_hash_at(idx: int, k: int = 2) -> str:
                start = max(0, idx - k)
                end = min(len(tokens), idx + k + 1)
                window_words = [tokens[i][0] for i in range(start, end)]
                normalized = ' '.join(w.lower() for w in window_words)
                return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
            
            occurrences: list[tuple[str, str, int, str]] = []
            for idx, (word, line_no) in enumerate(tokens):
                if word not in anchor_words:
                    continue
                h8 = word_to_hash.get(word) or hash8_hex(f"Ġ{word}")
                occurrences.append((word, h8, line_no, compute_ctx_hash_at(idx)))
            
            if len(occurrences) < 2:
                self.send_json({'error': 'Too few anchor occurrences found'}, 400)
                return
            
            edges_added = 0
            for i in range(len(occurrences) - 1):
                src_word, src_h8, _src_line, _src_ctx = occurrences[i]
                tgt_word, tgt_h8, tgt_line, tgt_ctx = occurrences[i + 1]
                overlay.add_edge(
                    src_h8,
                    tgt_h8,
                    weight=1.0,
                    doc=doc,
                    line=tgt_line,
                    ctx_hash=tgt_ctx,
                )
                overlay.define_label(src_h8, src_word)
                overlay.define_label(tgt_h8, tgt_word)
                edges_added += 1
            
            if overlay_path:
                overlay.save(overlay_path)
            else:
                default_path = Path('./.invariant/overlay.jsonl')
                default_path.parent.mkdir(parents=True, exist_ok=True)
                overlay.save(default_path)
                UIHandler.overlay_path = default_path
            
            UIHandler._graph_cache_key = None
            UIHandler._graph_cache_value = None
            
            self.send_json({
                'success': True,
                'doc': doc,
                'removed_edges': removed,
                'edges': edges_added,
                'anchors': len(anchor_words),
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

    def api_docs(self):
        """List ingested documents with simple stats (local overlay only)."""
        overlay = UIHandler.overlay
        if not overlay:
            self.send_json({'docs': []})
            return
        
        docs: dict[str, dict] = {}
        for src, edge_list in overlay.edges.items():
            for edge in edge_list:
                if not edge.doc:
                    continue
                d = docs.get(edge.doc)
                if d is None:
                    d = {'doc': edge.doc, 'edges': 0, 'nodes_set': set()}
                    docs[edge.doc] = d
                d['edges'] += 1
                d['nodes_set'].add(src)
                d['nodes_set'].add(edge.tgt)
        
        out = []
        for doc, d in docs.items():
            out.append({'doc': doc, 'edges': d['edges'], 'nodes': len(d['nodes_set'])})
        
        out.sort(key=lambda x: (-x['edges'], x['doc'].lower()))
        self.send_json({'docs': out})
    
    def api_verify(self, query_string: str):
        """Verify if an assertion has σ-proof (documentary evidence)."""
        physics = UIHandler.physics
        overlay = UIHandler.overlay
        
        params = urllib.parse.parse_qs(query_string or "")
        subject = (params.get('subject', [''])[0] or '').strip()
        obj = (params.get('object', [''])[0] or '').strip()
        
        if not subject or not obj:
            self.send_json({'error': 'Missing subject or object parameter'}, 400)
            return
        
        if not overlay:
            self.send_json({
                'proven': False,
                'message': 'No overlay loaded. Ingest documents first.',
                'subject': subject,
                'object': obj,
                'path': [],
                'sources': [],
                'conflicts': []
            })
            return
        
        if not physics:
            self.send_json({'error': 'Physics engine not initialized'}, 500)
            return
        
        try:
            result = physics.verify(subject, obj)
            
            self.send_json({
                'proven': result.proven,
                'message': result.message,
                'subject': subject,
                'object': obj,
                'subject_hash': result.subject_hash,
                'object_hash': result.object_hash,
                'path': result.path,
                'sources': result.sources,
                'conflicts': result.conflicts
            })
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def api_context(self, query_string: str):
        """
        Lazy load context from source file with integrity verification.
        
        Anchor Integrity Protocol (see INVARIANTS.md):
        - Reads file on demand (MDL-compliant)
        - Verifies ctx_hash if provided (drift detection)
        - Attempts self-healing if hash not at expected line
        
        Query params:
            doc: document filename
            line: line number (1-indexed)
            ctx_hash: optional semantic checksum for verification
        
        Returns:
            status: 'fresh' | 'relocated' | 'broken' | 'unchecked'
        """
        params = urllib.parse.parse_qs(query_string or "")
        doc = (params.get('doc', [''])[0] or '').strip()
        line_str = (params.get('line', [''])[0] or '').strip()
        ctx_hash = (params.get('ctx_hash', [''])[0] or '').strip()
        
        if not doc or not line_str:
            self.send_json({'error': 'Missing doc or line parameter'}, 400)
            return
        
        try:
            target_line = int(line_str)
        except ValueError:
            self.send_json({'error': 'Invalid line number'}, 400)
            return
        
        doc_path, candidates = self._resolve_doc_path(doc)
        
        if not doc_path:
            self.send_json({
                'error': f'Document not found: {doc}',
                'searched': [str(c) for c in candidates],
                'status': 'broken'
            }, 404)
            return
        
        try:
            text = doc_path.read_text(encoding='utf-8')
            lines = text.split('\n')
            
            if target_line < 1 or target_line > len(lines):
                self.send_json({
                    'error': f'Line {target_line} out of range (1-{len(lines)})',
                    'status': 'broken'
                }, 400)
                return
            
            # Tokenize entire file for hash computation
            tokens = self._tokenize_file(text)
            
            status, actual_line, anchor_word = self._resolve_anchor_coordinate(
                lines=lines,
                tokens=tokens,
                requested_line=target_line,
                ctx_hash=ctx_hash or None,
            )
            
            # Extract semantic block from actual_line
            block_start, block_end, block_lines = self._extract_semantic_block(lines, actual_line)
            
            self.send_json({
                'doc': doc,
                'doc_path': str(doc_path.absolute()),
                'requested_line': target_line,
                'actual_line': actual_line,
                'status': status,
                'anchor_word': anchor_word,
                'block_start': block_start,
                'block_end': block_end,
                'content': '\n'.join(block_lines),
                'lines': block_lines,
                'total_lines': len(lines)
            })
            
        except Exception as e:
            self.send_json({'error': str(e), 'status': 'broken'}, 500)

    def _resolve_anchor_coordinate(
        self,
        *,
        lines: list[str],
        tokens: list[tuple[str, int]],
        requested_line: int,
        ctx_hash: Optional[str],
    ) -> tuple[str, int, Optional[str]]:
        """
        Anchor Integrity Protocol (docs/INVARIANTS.md):
        - fresh: ctx_hash matches at requested line
        - relocated: ctx_hash found within scan radius
        - broken: ctx_hash not found nearby
        - unchecked: no ctx_hash provided
        """
        status = 'unchecked'
        actual_line = requested_line
        anchor_word: Optional[str] = None

        if not ctx_hash:
            return status, actual_line, anchor_word

        for h, w in self._compute_hashes_at_line(tokens, requested_line):
            if h == ctx_hash:
                return 'fresh', requested_line, w

        scan_radius = UIHandler._ANCHOR_SCAN_RADIUS
        for offset in range(1, scan_radius + 1):
            up = requested_line - offset
            if up >= 1:
                for h, w in self._compute_hashes_at_line(tokens, up):
                    if h == ctx_hash:
                        return 'relocated', up, w

            down = requested_line + offset
            if down <= len(lines):
                for h, w in self._compute_hashes_at_line(tokens, down):
                    if h == ctx_hash:
                        return 'relocated', down, w

        return 'broken', requested_line, None

    def _project_root(self) -> Path:
        """Determine project root from overlay location when possible (robust to running from subdirs)."""
        overlay_path = UIHandler.overlay_path
        if overlay_path:
            try:
                p = Path(overlay_path).resolve()
                if p.parent.name == '.invariant':
                    return p.parent.parent
            except Exception:
                pass
        return Path('.').resolve()

    def _resolve_doc_path(self, doc: str) -> tuple[Optional[Path], list[Path]]:
        """
        Resolve a document path within project roots.

        Theory: pointer-to-reality can drift (files move). We try exact resolution first (O(1)),
        then a bounded search inside the project root (still deterministic; never guess ambiguously).
        """
        project_root = self._project_root()
        doc_rel = Path(doc)
        candidates: list[Path] = []

        # Cache (doc -> resolved path) to avoid repeated filesystem work.
        cache: dict[str, str] = getattr(UIHandler, "_doc_path_cache", {}) or {}
        cached = cache.get(doc)
        if cached:
            try:
                p = Path(cached)
                if p.exists() and p.is_file():
                    return p, [p]
            except Exception:
                cache.pop(doc, None)
                UIHandler._doc_path_cache = cache

        if doc_rel.is_absolute():
            try:
                resolved = doc_rel.resolve()
                if project_root in resolved.parents or resolved == project_root:
                    candidates.append(resolved)
            except Exception:
                pass
        else:
            for base in (
                project_root,
                project_root / '.invariant',
                project_root / 'docs',
                project_root / 'data',
                project_root / 'archive',
            ):
                try:
                    resolved = (base / doc_rel).resolve()
                except Exception:
                    continue
                if project_root in resolved.parents or resolved == project_root:
                    candidates.append(resolved)

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                cache[doc] = str(candidate)
                UIHandler._doc_path_cache = cache
                return candidate, candidates

        # Fallback: locate by suffix/name within project_root (path drift).
        try:
            target_suffix = doc_rel.as_posix()
            basename = doc_rel.name
            if basename:
                found: list[tuple[str, Path]] = []
                skip_dirs = {
                    '.git', '.venv', 'node_modules', 'dist', 'build',
                    '__pycache__', '.pytest_cache', '.mypy_cache',
                }
                for root, dirs, files in os.walk(project_root):
                    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
                    if basename in files:
                        p = Path(root) / basename
                        if not p.is_file():
                            continue
                        try:
                            rel = p.relative_to(project_root).as_posix()
                        except Exception:
                            rel = p.as_posix()
                        found.append((rel, p))
                        if len(found) >= 30:
                            break

                if found:
                    suffix_matches = [p for (rel, p) in found if rel.endswith(target_suffix)]
                    if len(suffix_matches) == 1:
                        cache[doc] = str(suffix_matches[0])
                        UIHandler._doc_path_cache = cache
                        candidates.extend([p for (_rel, p) in found[:10]])
                        return suffix_matches[0], candidates

                    if len(found) == 1:
                        cache[doc] = str(found[0][1])
                        UIHandler._doc_path_cache = cache
                        candidates.append(found[0][1])
                        return found[0][1], candidates

                    # Ambiguous: include a few matches for debugging, but don't guess.
                    candidates.extend([p for (_rel, p) in found[:10]])
        except Exception:
            pass

        return None, candidates

    def api_open(self, query_string: str):
        """
        Open/reveal a local σ-source file at a given line (macOS).
        
        This is a UX bridge: UI -> Reality, without duplicating content (Invariant III).
        Supports Anchor Integrity Protocol via ctx_hash (self-healing line relocation).
        
        Query params:
            mode: 'open' | 'reveal' | 'vscode'
            doc: document filename/path (relative to project / .invariant / docs)
            line: line number (1-indexed)
            ctx_hash: optional semantic checksum (for relocation)
        """
        import platform
        import subprocess
        
        params = urllib.parse.parse_qs(query_string or "")
        mode = (params.get('mode', ['open'])[0] or 'open').strip().lower()
        doc = (params.get('doc', [''])[0] or '').strip()
        line_str = (params.get('line', [''])[0] or '').strip()
        ctx_hash = (params.get('ctx_hash', [''])[0] or '').strip()
        
        if not doc or not line_str:
            self.send_json({'error': 'Missing doc or line parameter'}, 400)
            return
        
        try:
            target_line = int(line_str)
        except ValueError:
            self.send_json({'error': 'Invalid line number'}, 400)
            return
        
        doc_path, candidates = self._resolve_doc_path(doc)
        
        if not doc_path:
            self.send_json({'error': f'Document not found: {doc}', 'searched': [str(c) for c in candidates]}, 404)
            return
        
        # Determine actual line via ctx_hash (self-healing)
        status = 'unchecked'
        actual_line = target_line
        try:
            text = doc_path.read_text(encoding='utf-8')
            lines = text.split('\n')
            tokens = self._tokenize_file(text)
            status, actual_line, _anchor_word = self._resolve_anchor_coordinate(
                lines=lines,
                tokens=tokens,
                requested_line=target_line,
                ctx_hash=ctx_hash or None,
            )
        except Exception:
            status = 'broken'
            actual_line = target_line
        
        # Execute open (macOS only for now)
        if platform.system().lower() != 'darwin':
            self.send_json({'error': 'Open is only implemented for macOS', 'status': status}, 501)
            return
        
        try:
            run = None
            if mode == 'reveal':
                run = subprocess.run(['open', '-R', str(doc_path)], check=False)
            elif mode == 'vscode':
                target = f"{doc_path}:{actual_line}"
                run = subprocess.run(['open', '-a', 'Visual Studio Code', '--args', '-g', target], check=False)
            else:
                run = subprocess.run(['open', str(doc_path)], check=False)
            
            self.send_json({
                'ok': (run.returncode == 0) if run else True,
                'returncode': run.returncode if run else None,
                'mode': mode,
                'doc': doc,
                'doc_path': str(doc_path),
                'requested_line': target_line,
                'actual_line': actual_line,
                'status': status,
            })
        except Exception as e:
            self.send_json({'error': str(e), 'status': status}, 500)
    
    def _tokenize_file(self, text: str) -> list:
        """Tokenize text with position info for hash computation."""
        import re
        results = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for match in re.finditer(r'\b[a-zA-Z]{3,}\b', line):
                word = match.group().lower()
                results.append((word, line_num))
        
        return results
    
    def _compute_hashes_at_line(self, tokens: list, target_line: int, k: int = 2) -> list[tuple[str, str]]:
        """
        Compute all possible ctx_hashes for tokens at given line.
        
        Returns list of (ctx_hash, anchor_word) (one per token on that line).
        This is needed because we don't know which token was the anchor.
        """
        import hashlib
        
        # Find all tokens on this line
        line_tokens = [(i, t) for i, t in enumerate(tokens) if t[1] == target_line]
        
        if not line_tokens:
            return []
        
        out: list[tuple[str, str]] = []
        for anchor_idx, token in line_tokens:
            # Get window
            start = max(0, anchor_idx - k)
            end = min(len(tokens), anchor_idx + k + 1)
            
            window_words = [tokens[i][0] for i in range(start, end)]
            normalized = ' '.join(w.lower() for w in window_words)
            
            h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
            out.append((h, token[0]))
        
        return out
    
    def _extract_semantic_block(self, lines: list, target_line: int, max_lines: int = 10):
        """
        Extract semantic block around target line.
        
        Uses phase boundary detection:
        - Empty lines = paragraph boundary
        - Lines starting with # = section boundary
        - Lines with only whitespace = boundary
        
        Returns: (start_line, end_line, block_lines)
        """
        n = len(lines)
        target_idx = target_line - 1  # 0-indexed
        
        def is_boundary(line: str) -> bool:
            stripped = line.strip()
            if not stripped:  # Empty line
                return True
            if stripped.startswith('#'):  # Markdown header
                return True
            if stripped.startswith('---'):  # Horizontal rule
                return True
            return False
        
        # Find block start (go up until boundary)
        start_idx = target_idx
        while start_idx > 0 and (target_idx - start_idx) < max_lines // 2:
            if is_boundary(lines[start_idx - 1]):
                break
            start_idx -= 1
        
        # Find block end (go down until boundary)
        end_idx = target_idx
        while end_idx < n - 1 and (end_idx - target_idx) < max_lines // 2:
            if is_boundary(lines[end_idx + 1]):
                break
            end_idx += 1
        
        # Extract block
        block_lines = lines[start_idx:end_idx + 1]
        
        return start_idx + 1, end_idx + 1, block_lines  # Return 1-indexed


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
