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
                "<title>Docs — Invariant</title>"
                "<style>"
                "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px;}"
                "h1{margin:0 0 8px;color:#58a6ff;font-size:22px;}"
                ".sub{color:#8b949e;margin:0 0 18px;font-size:13px;}"
                ".list{display:flex;flex-direction:column;gap:10px;max-width:720px;}"
                ".item{display:flex;justify-content:space-between;gap:12px;align-items:center;"
                "padding:12px 14px;border:1px solid #21262d;border-radius:10px;background:#161b22;text-decoration:none;color:#e6edf3;}"
                ".item:hover{border-color:#58a6ff;}"
                ".name{font-weight:600;}"
                ".meta{color:#8b949e;font-size:12px;white-space:nowrap;}"
                "a.back{color:#58a6ff;text-decoration:none;font-size:13px;}"
                "a.back:hover{text-decoration:underline;}"
                "</style></head><body>"
                f"<h1>Docs</h1><p class='sub'>Crystal: <strong>{crystal}</strong> • choose a document overlay</p>"
                "<p><a class='back' href='/'>← Back to search</a></p>"
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
            "<title>Doc — Invariant</title>"
            "<style>"
            "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px;}"
            "h1{margin:0 0 8px;color:#58a6ff;font-size:22px;}"
            ".sub{color:#8b949e;margin:0 0 18px;font-size:13px;}"
            ".row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:10px 0 16px;}"
            "a.back,a.link{color:#58a6ff;text-decoration:none;font-size:13px;}"
            "a.back:hover,a.link:hover{text-decoration:underline;}"
            ".frame{width:100%;height:70vh;border:1px solid #21262d;border-radius:12px;overflow:hidden;background:#0d1117;}"
            "iframe{width:100%;height:100%;border:0;}"
            ".pills{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px;}"
            ".pill{padding:6px 10px;border:1px solid #21262d;border-radius:999px;background:#161b22;"
            "text-decoration:none;color:#e6edf3;font-size:12px;}"
            ".pill:hover{border-color:#58a6ff;}"
            "</style></head><body>"
            f"<h1>{html.escape(doc)}</h1>"
            f"<p class='sub'>Crystal: <strong>{crystal}</strong> • {d['edges']} edges • {len(d['nodes'])} nodes</p>"
            "<div class='row'>"
            f"<a class='back' href='/'>← Back</a>"
            f"<a class='link' href='{graph_href}' target='_blank'>Open 3D</a>"
            f"<a class='link' href='/doc'>All docs</a>"
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
  <script src="https://unpkg.com/3d-force-graph"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0d1117; color: #e6edf3; overflow: hidden; }
    #graph { position: absolute; inset: 0; }
    #labels { position: absolute; inset: 0; pointer-events: none; }
    .lbl {
      position: absolute;
      padding: 2px 6px;
      border-radius: 6px;
      background: rgba(13, 17, 23, 0.65);
      border: 1px solid rgba(48, 54, 61, 0.7);
      font: 12px/1.3 -apple-system, BlinkMacSystemFont, sans-serif;
      color: #e6edf3;
      white-space: nowrap;
      transform: translate(-50%, -135%);
    }
    .lbl.solid { border-color: rgba(88, 166, 255, 0.55); }
    #hud {
      position: fixed;
      top: 14px;
      left: 14px;
      width: 360px;
      background: rgba(22, 27, 34, 0.95);
      border: 1px solid #30363d;
      border-radius: 10px;
      padding: 12px 12px;
      z-index: 10;
      backdrop-filter: blur(6px);
    }
    #hud h1 { font-size: 12px; color: #58a6ff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }
    #hud .row { font: 12px/1.4 -apple-system, BlinkMacSystemFont, sans-serif; color: #8b949e; margin: 3px 0; }
    #hud .row span { color: #e6edf3; }
    #hud .btns { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
    #hud button {
      background: #21262d; color: #e6edf3; border: 1px solid #30363d;
      padding: 6px 8px; border-radius: 8px; cursor: pointer;
      font-size: 12px;
    }
    #hud button.active { border-color: #58a6ff; }
    #hud a { color: #58a6ff; text-decoration: none; }
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
      graphEl.innerHTML = '<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:#8b949e;font:14px -apple-system;">No local graph</div>';
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
      .backgroundColor('#0d1117')
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
                is_local = 'doc' in n  # overlay edges include doc field
                doc = n.get('doc') if is_local else None
                line = n.get('line') if is_local else None
                snippet = n.get('snippet') if is_local else None
                
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
                if snippet:
                    neighbor_data['snippet'] = snippet
                
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
        import hashlib
        import re
        
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
        
        # Find the document file
        doc_path = None
        candidates = [
            Path(doc),
            Path('.') / doc,
            Path('.invariant') / doc,
            Path('docs') / doc,
        ]
        
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                doc_path = candidate
                break
        
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
            
            # Default status
            status = 'unchecked'
            actual_line = target_line
            
            # If ctx_hash provided, verify integrity
            if ctx_hash:
                # Get all hashes for tokens on target line
                line_hashes = self._compute_hash_at_line(tokens, target_line)
                
                if ctx_hash in line_hashes:
                    status = 'fresh'
                else:
                    # Hash doesn't match - try to find it nearby (self-healing)
                    scan_radius = 50
                    found_line = None
                    
                    for offset in range(1, scan_radius + 1):
                        # Check above
                        check_line = target_line - offset
                        if check_line >= 1:
                            hashes = self._compute_hash_at_line(tokens, check_line)
                            if ctx_hash in hashes:
                                found_line = check_line
                                break
                        
                        # Check below
                        check_line = target_line + offset
                        if check_line <= len(lines):
                            hashes = self._compute_hash_at_line(tokens, check_line)
                            if ctx_hash in hashes:
                                found_line = check_line
                                break
                    
                    if found_line:
                        status = 'relocated'
                        actual_line = found_line
                    else:
                        status = 'broken'
            
            # Extract semantic block from actual_line
            block_start, block_end, block_lines = self._extract_semantic_block(lines, actual_line)
            
            self.send_json({
                'doc': doc,
                'doc_path': str(doc_path.absolute()),
                'requested_line': target_line,
                'actual_line': actual_line,
                'status': status,
                'block_start': block_start,
                'block_end': block_end,
                'content': '\n'.join(block_lines),
                'lines': block_lines,
                'total_lines': len(lines)
            })
            
        except Exception as e:
            self.send_json({'error': str(e), 'status': 'broken'}, 500)
    
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
    
    def _compute_hash_at_line(self, tokens: list, target_line: int, k: int = 2) -> list:
        """
        Compute all possible ctx_hashes for tokens at given line.
        
        Returns list of hashes (one per token on that line).
        This is needed because we don't know which token was the anchor.
        """
        import hashlib
        
        # Find all tokens on this line
        line_tokens = [(i, t) for i, t in enumerate(tokens) if t[1] == target_line]
        
        if not line_tokens:
            return []
        
        hashes = []
        for anchor_idx, _ in line_tokens:
            # Get window
            start = max(0, anchor_idx - k)
            end = min(len(tokens), anchor_idx + k + 1)
            
            window_words = [tokens[i][0] for i in range(start, end)]
            normalized = ' '.join(w.lower() for w in window_words)
            
            h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8]
            hashes.append(h)
        
        return hashes
    
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
