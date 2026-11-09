#!/usr/bin/env python3
"""Live Markdown + KaTeX preview (Overleaf-style).

Edit the .md in Cursor; the browser re-renders when the *content* changes
(not just mtime — uses SHA-1 so atomic saves are always detected).

Usage:
  python3 tools/md_live_preview.py theory/00_theory_derivation_en.md
  python3 tools/md_live_preview.py theory/00_theory_derivation_en.md --port 8765
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]

VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MD Live Preview</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"/>
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
    background: #1e1e1e; color: #ddd; line-height: 1.55;
  }
  #bar {
    position: sticky; top: 0; z-index: 10;
    display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
    padding: 8px 16px; background: #252525; border-bottom: 1px solid #333;
    font-size: 12px; color: #aaa;
  }
  #bar.flash { background: #1a3d1a; border-bottom-color: #3c3; }
  #bar strong { color: #eee; font-weight: 600; }
  #dot { width: 8px; height: 8px; border-radius: 50%; background: #3c3; display: inline-block; }
  #dot.stale { background: #c93; }
  #content { max-width: 920px; margin: 0 auto; padding: 28px 24px 80px; }
  h1,h2,h3 { color: #fff; line-height: 1.25; }
  h1 { font-size: 1.8rem; border-bottom: 1px solid #333; padding-bottom: .4em; }
  h2 { font-size: 1.35rem; margin-top: 2em; }
  h3 { font-size: 1.1rem; margin-top: 1.5em; }
  a { color: #6cb6ff; }
  code { background: #2a2a2a; padding: .1em .35em; border-radius: 4px; font-size: .92em; }
  pre { background: #2a2a2a; padding: 12px 14px; border-radius: 8px; overflow: auto; }
  pre code { background: none; padding: 0; }
  blockquote { border-left: 3px solid #555; margin: 1em 0; padding: .2em 1em; color: #bbb; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .92em; }
  th, td { border: 1px solid #444; padding: 6px 10px; vertical-align: top; }
  th { background: #2a2a2a; text-align: left; }
  hr { border: none; border-top: 1px solid #333; margin: 2em 0; }
  .katex-display { overflow-x: auto; overflow-y: hidden; padding: .4em 0; }
  #err { color: #f88; white-space: pre-wrap; }
</style>
</head>
<body>
<div id="bar">
  <span id="dot"></span>
  <strong id="filelabel"></strong>
  <span id="status">connecting…</span>
  <span id="rev"></span>
</div>
<div id="content"><div id="err">Loading…</div></div>
<script src="https://cdn.jsdelivr.net/npm/marked@13.0.3/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<script>
const params = new URLSearchParams(location.search);
const file = params.get('file');
const bar = document.getElementById('bar');
const filelabel = document.getElementById('filelabel');
const status = document.getElementById('status');
const revEl = document.getElementById('rev');
const dot = document.getElementById('dot');
const content = document.getElementById('content');
filelabel.textContent = file || '(no file)';

marked.setOptions({ gfm: true, breaks: false });

function neutralizeUri(url) {
  const raw = String(url || '').trim();
  const lower = raw.toLowerCase();
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('vbscript:')
  ) {
    return '#';
  }
  return raw;
}

function escapeAttr(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

const renderer = new marked.Renderer();
renderer.link = function (href, title, text) {
  const safeHref = escapeAttr(neutralizeUri(href));
  const titleAttr = title ? ` title="${escapeAttr(title)}"` : '';
  return `<a href="${safeHref}"${titleAttr} rel="noopener noreferrer">${text}</a>`;
};
renderer.image = function (href, title, text) {
  const safeHref = escapeAttr(neutralizeUri(href));
  const titleAttr = title ? ` title="${escapeAttr(title)}"` : '';
  return `<img src="${safeHref}" alt="${escapeAttr(text)}"${titleAttr} />`;
};
marked.setOptions({ renderer });

// marked.js treats \\ as escapes, so \\, becomes a literal comma before KaTeX runs.
// Stash $...$ / $$...$$ first, restore after HTML conversion.
function protectMath(md) {
  const slots = [];
  const stash = (m) => {
    const i = slots.length;
    slots.push(m);
    return '@@MATH' + i + '@@';
  };
  md = md.replace(/\$\$[\s\S]+?\$\$/g, stash);
  md = md.replace(/\$[^$\n]+?\$/g, stash);
  return { md, slots };
}

function showError(err) {
  content.replaceChildren();
  const box = document.createElement('div');
  box.id = 'err';
  box.textContent = String(err);
  content.appendChild(box);
}

function render(md) {
  const { md: stripped, slots } = protectMath(md);
  // This is a documentation preview, not an HTML runner. Escape raw HTML
  // before Markdown parsing so repository documents cannot execute scripts.
  const safeMarkdown = stripped
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  let html = marked.parse(safeMarkdown);
  // Escape <>& so browser innerHTML doesn't eat math like $c_B<r$ as a tag.
  html = html.replace(/@@MATH(\d+)@@/g, (_, i) =>
    slots[Number(i)]
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  );
  content.innerHTML = html;
  // Defense in depth: neutralize any residual active URI schemes.
  content.querySelectorAll('a[href], img[src]').forEach((el) => {
    const attr = el.hasAttribute('href') ? 'href' : 'src';
    el.setAttribute(attr, neutralizeUri(el.getAttribute(attr)));
  });
  renderMathInElement(content, {
    delimiters: [
      {left: '$$', right: '$$', display: true},
      {left: '$', right: '$', display: false},
      {left: '\\(', right: '\\)', display: false},
      {left: '\\[', right: '\\]', display: true}
    ],
    throwOnError: false
  });
}

let lastHash = null;
let nUpdates = 0;
let busy = false;

async function pull(force) {
  if (!file || busy) return;
  busy = true;
  try {
    const meta = await fetch('/api/meta?file=' + encodeURIComponent(file) + '&_=' + Date.now(), {cache: 'no-store'})
      .then(r => { if (!r.ok) throw new Error('meta ' + r.status); return r.json(); });
    if (!force && meta.hash === lastHash) {
      status.textContent = 'watching · ' + meta.bytes + ' B';
      dot.classList.remove('stale');
      return;
    }
    const y = window.scrollY;
    const text = await fetch('/api/raw?file=' + encodeURIComponent(file) + '&h=' + meta.hash, {cache: 'no-store'})
      .then(r => { if (!r.ok) throw new Error('raw ' + r.status); return r.text(); });
    lastHash = meta.hash;
    render(text);
    requestAnimationFrame(() => window.scrollTo(0, y));
    nUpdates += 1;
    revEl.textContent = 'rev #' + nUpdates + ' · ' + meta.hash.slice(0, 8);
    status.textContent = 'updated ' + new Date().toLocaleTimeString();
    dot.classList.remove('stale');
    bar.classList.add('flash');
    setTimeout(() => bar.classList.remove('flash'), 600);
  } finally {
    busy = false;
  }
}

async function loop() {
  try {
    await pull(false);
  } catch (e) {
    status.textContent = String(e);
    dot.classList.add('stale');
  }
  setTimeout(loop, 300);
}

pull(true).catch(e => {
  showError(e);
  status.textContent = String(e);
  dot.classList.add('stale');
});
loop();
</script>
</body>
</html>
"""


def resolve_file(rel: str, *, markdown_only: bool = False) -> Path:
    if not rel or "\x00" in rel:
        raise FileNotFoundError(rel or "<empty>")
    p = Path(unquote(rel))
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    else:
        p = p.resolve()
    if not p.is_relative_to(ROOT):
        raise PermissionError(f"path outside project: {p}")
    if ".git" in p.parts:
        raise PermissionError(f"path inside .git: {p}")
    if markdown_only and p.suffix.lower() != ".md":
        raise PermissionError(f"only markdown files are served: {p}")
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


def file_meta(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "hash": hashlib.sha1(data).hexdigest(),
        "bytes": len(data),
        "mtime": path.stat().st_mtime,
    }


def make_handler(default_rel: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # only log non-meta noise-reduced
            msg = fmt % args
            if "/api/meta" in msg:
                return
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), msg))

        def _send(self, code: int, body: bytes, content_type: str):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'; "
                "font-src https://cdn.jsdelivr.net; img-src data:",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            try:
                host_header = self.headers.get("Host", "")
                host = (
                    host_header[1:].split("]", 1)[0]
                    if host_header.startswith("[")
                    else host_header.rsplit(":", 1)[0]
                ).lower()
                if host not in {"127.0.0.1", "localhost", "::1"}:
                    self._send(403, b"invalid host", "text/plain")
                    return
                if parsed.path in ("/", "/index.html"):
                    rel = qs.get("file", [default_rel])[0]
                    if "file" not in qs:
                        self.send_response(302)
                        self.send_header("Location", "/?file=" + rel.replace("\\", "/"))
                        self.end_headers()
                        return
                    self._send(200, VIEWER_HTML.encode("utf-8"), "text/html; charset=utf-8")
                    return

                if parsed.path == "/api/meta":
                    rel = qs.get("file", [default_rel])[0]
                    path = resolve_file(rel, markdown_only=True)
                    payload = json.dumps({"file": rel, **file_meta(path)}).encode()
                    self._send(200, payload, "application/json")
                    return

                # back-compat
                if parsed.path == "/api/mtime":
                    rel = qs.get("file", [default_rel])[0]
                    path = resolve_file(rel, markdown_only=True)
                    payload = json.dumps({"file": rel, **file_meta(path)}).encode()
                    self._send(200, payload, "application/json")
                    return

                if parsed.path == "/api/raw":
                    rel = qs.get("file", [default_rel])[0]
                    path = resolve_file(rel, markdown_only=True)
                    self._send(200, path.read_bytes(), "text/markdown; charset=utf-8")
                    return

                self._send(404, b"not found", "text/plain")
            except PermissionError as e:
                self._send(403, str(e).encode(), "text/plain; charset=utf-8")
            except FileNotFoundError as e:
                self._send(404, str(e).encode(), "text/plain; charset=utf-8")
            except Exception as e:
                self._send(500, str(e).encode(), "text/plain; charset=utf-8")

    return Handler


def main():
    ap = argparse.ArgumentParser(description="Live Markdown + KaTeX preview")
    ap.add_argument("file", help="Markdown file relative to project root")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    path = resolve_file(args.file, markdown_only=True)
    rel = str(path.relative_to(ROOT)).replace("\\", "/")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(rel))
    url = f"http://127.0.0.1:{args.port}/?file={rel}"
    print(f"Serving {rel}")
    print(f"Open THIS url (not the .html file):")
    print(f"  {url}")
    print("Edit + save the .md in Cursor — top bar flashes green and rev # increments.")
    print("Ctrl+C to stop.")

    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
        server.shutdown()


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
