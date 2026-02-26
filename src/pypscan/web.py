"""
Web UI backend for PyPScan.

Starts a local HTTP server (stdlib only) and opens a browser tab.
Supports inline image display and plain-text preview.
"""
import base64
import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .core import Scanner, ParametricIndex

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PyPScan</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #111; color: #eee; display: flex; flex-direction: column; height: 100vh; }
  header { background: #1e1e2e; padding: 12px 20px; font-size: 1.1rem; font-weight: 700; letter-spacing: .05em; color: #86efac; border-bottom: 1px solid #313244; }

  /* Controls: one parameter per row, stacked vertically */
  #controls {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 0 20px;
    background: #181825;
    border-bottom: 1px solid #313244;
    overflow-y: auto;
    max-height: 40vh;
  }
  .param-group {
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px solid #1e1e2e;
  }
  .param-group:last-child { border-bottom: none; }
  .param-label {
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .09em;
    color: #a6adc8;
    min-width: 80px;
    padding-top: 6px;
    flex-shrink: 0;
  }
  /* Buttons wrap to the next line when the row is full */
  .btn-row { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; }
  button.opt {
    padding: 4px 13px; border: 1px solid #45475a; border-radius: 6px;
    background: #313244; color: #cdd6f4; cursor: pointer; font-size: .83rem;
    transition: background .12s, border-color .12s;
    white-space: nowrap;
  }
  button.opt:hover { background: #45475a; }
  button.opt.active { background: #16a34a; border-color: #16a34a; color: #fff; }

  #viewer { flex: 1; display: flex; align-items: center; justify-content: center; overflow: auto; padding: 20px; }
  #viewer img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px; box-shadow: 0 4px 24px #0008; }
  #viewer pre { white-space: pre-wrap; word-break: break-all; font-family: monospace; font-size: .85rem; color: #cdd6f4; }
  #viewer .msg { color: #a6adc8; font-size: .9rem; }
  #status { font-size: .75rem; padding: 6px 20px; background: #1e1e2e; border-top: 1px solid #313244; color: #6c7086; }
</style>
</head>
<body>
<header>PyPScan</header>
<div id="controls"></div>
<div id="viewer"><span class="msg">Select parameters above.</span></div>
<div id="status">Ready</div>
<script>
const state = {};

// Fetch cross-filtered options for all params given the current state.
// The server computes per-param options with all other params fixed.
async function fetchOptions() {
  const resp = await fetch('/options?' + new URLSearchParams({state: JSON.stringify(state)}));
  return resp.json();
}

async function fetchFile() {
  if (!Object.keys(state).length) return;
  const resp = await fetch('/file?' + new URLSearchParams({selection: JSON.stringify(state)}));
  const data = await resp.json();
  const viewer = document.getElementById('viewer');
  if (data.error) {
    viewer.innerHTML = `<span class="msg">${data.error}</span>`;
  } else if (data.type === 'image') {
    viewer.innerHTML = `<img src="data:${data.mime};base64,${data.data}" alt="file">`;
  } else if (data.type === 'text') {
    const pre = document.createElement('pre');
    pre.textContent = data.data;
    viewer.innerHTML = '';
    viewer.appendChild(pre);
  } else {
    viewer.innerHTML = `<span class="msg">Path: ${data.path}</span>`;
  }
  document.getElementById('status').textContent = data.path || '';
}

async function selectOption(param, value) {
  state[param] = value;
  await updateControls();
  await fetchFile();
}

async function updateControls() {
  const allOptions = await fetchOptions();
  const controls = document.getElementById('controls');
  const existingGroups = {};
  controls.querySelectorAll('.param-group').forEach(g => {
    existingGroups[g.dataset.param] = g;
  });

  for (const [param, opts] of Object.entries(allOptions)) {
    // If current value is no longer valid, reset to first available.
    if (!opts.includes(state[param])) {
      state[param] = opts[0];
    }
    let group = existingGroups[param];
    if (!group) {
      group = document.createElement('div');
      group.className = 'param-group';
      group.dataset.param = param;
      const label = document.createElement('div');
      label.className = 'param-label';
      label.textContent = param;
      group.appendChild(label);
      const row = document.createElement('div');
      row.className = 'btn-row';
      group.appendChild(row);
      controls.appendChild(group);
    }
    const row = group.querySelector('.btn-row');
    row.innerHTML = '';
    for (const opt of opts) {
      const btn = document.createElement('button');
      btn.className = 'opt' + (opt === state[param] ? ' active' : '');
      btn.textContent = opt;
      btn.onclick = () => selectOption(param, opt);
      row.appendChild(btn);
    }
  }
}

(async () => {
  await updateControls();
  await fetchFile();
})();
</script>
</body>
</html>
"""


def _file_response(path: str) -> dict:
    """Build a JSON-serialisable dict describing the file for the browser."""
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "application/octet-stream"
    if mime.startswith("image/"):
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return {"type": "image", "mime": mime, "data": data, "path": path}
        except Exception as exc:
            return {"error": str(exc)}
    if mime.startswith("text/") or path.lower().endswith(".txt"):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"type": "text", "data": f.read(), "path": path}
        except Exception as exc:
            return {"error": str(exc)}
    return {"type": "other", "path": path}


def _make_handler(index: ParametricIndex, html: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence request logging

        def _send_json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)

            if parsed.path == "/":
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            elif parsed.path == "/options":
                # Receive full current state; return cross-filtered options:
                # for each param, compute valid values with all OTHER params fixed.
                raw = qs.get("state", ["{}"])[0]
                try:
                    state = json.loads(raw)
                except json.JSONDecodeError:
                    state = {}
                result = {}
                for param in index.all_params():
                    excl = {k: v for k, v in state.items() if k != param}
                    opts_map = index.get_options(excl)
                    result[param] = opts_map.get(param, [])
                self._send_json(result)

            elif parsed.path == "/file":
                raw = qs.get("selection", ["{}"])[0]
                try:
                    selection = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json({"error": "Bad selection."})
                    return
                try:
                    result = index.resolve(selection)
                    if isinstance(result, str):
                        self._send_json(_file_response(result))
                    else:
                        self._send_json({"error": "Ambiguous selection."})
                except KeyError:
                    self._send_json({"error": "No file matches the current selection."})

            else:
                self.send_response(404)
                self.end_headers()

    return Handler


class WebPScan:
    """
    Standalone web-browser UI for PyPScan.

    Starts a local HTTP server and opens the browser automatically.

    Usage::

        from pypscan.web import WebPScan

        browser = WebPScan(
            regex=r"param0_(?P<param0>.+)/param1_(?P<param1>\\d+)/file\\.png",
            base_path="demo/",
        )
        browser.run()
    """

    def __init__(self, regex: str, base_path: str = "./", port: int = 8765):
        self.regex = regex
        self.base_path = base_path
        self.port = port
        scanner = Scanner(regex, base_path)
        self._index = ParametricIndex(scanner.scan())

    def run(self):
        """Start the server and open the browser (blocking)."""
        handler = _make_handler(self._index, _HTML_TEMPLATE)
        server = HTTPServer(("127.0.0.1", self.port), handler)
        url = f"http://127.0.0.1:{self.port}/"
        print(f"PyPScan web UI: {url}  (Ctrl-C to stop)")
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
        finally:
            server.server_close()
