#!/usr/bin/env python3
"""Lille web-app til at styre en BeoSound Moment over BeoLink/ASE-API'et.

Start:  python3 server.py [moment-ip] [port]
Åbn:    http://localhost:8765

Serveren leverer index.html, viderestiller /api/* til Moment (port 8080)
og omsætter Moment's notifikationsstrøm til Server-Sent Events på /events.
"""
import http.client
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOMENT_IP = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MOMENT_IP", "192.168.1.76")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("PORT", "8765"))
MOMENT_PORT = 8080
HERE = os.path.dirname(os.path.abspath(__file__))

# --- Notifikationer: én forbindelse til Moment, fordelt til alle browsere ---
subscribers = []
sub_lock = threading.Lock()
latest = {}  # seneste notifikation pr. type, så nye browsere får status med det samme


def broadcast(payload):
    with sub_lock:
        for q in list(subscribers):
            q.items.append(payload)
            q.event.set()


def handle_text(buf):
    """Udtræk komplette JSON-notifikationer (adskilt af tomme linjer) fra buf."""
    while True:
        cut = buf.find("\n\n")
        if cut < 0:
            return buf
        block, buf = buf[:cut].strip(), buf[cut + 2:]
        if not block:
            continue
        try:
            n = json.loads(block).get("notification", {})
        except ValueError:
            continue
        if n.get("type"):
            latest[n["type"]] = n
        broadcast(json.dumps(n))


def notification_loop():
    while True:
        try:
            sock = socket.create_connection((MOMENT_IP, MOMENT_PORT), timeout=90)
            sock.sendall(f"GET /BeoNotify/Notifications HTTP/1.1\r\nHost: {MOMENT_IP}\r\n\r\n".encode())
            f = sock.makefile("rb")
            headers = {}
            f.readline()  # statuslinje
            while True:
                h = f.readline().decode("latin-1").strip()
                if not h:
                    break
                k, _, v = h.partition(":")
                headers[k.strip().lower()] = v.strip().lower()
            chunked = headers.get("transfer-encoding") == "chunked"
            text = ""
            while True:
                if chunked:
                    size = int(f.readline().split(b";")[0].strip() or b"0", 16)
                    if size == 0:
                        break
                    data = f.read(size)
                    f.readline()  # CRLF efter chunk
                else:
                    data = f.readline()
                    if not data:
                        break
                text = handle_text(text + data.decode("utf-8", "replace").replace("\r\n", "\n"))
            sock.close()
        except socket.timeout:
            pass  # ingen hændelser i et stykke tid – forbind bare igen
        except Exception as exc:  # netværksfejl, standby osv.
            broadcast(json.dumps({"type": "_CONNECTION", "data": {"error": str(exc)}}))
        time.sleep(2)


class Sub:
    def __init__(self):
        self.items = []
        self.event = threading.Event()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/events":
            return self.events()
        if self.path.startswith("/api/"):
            return self.proxy("GET")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        self.proxy("POST")

    def do_PUT(self):
        self.proxy("PUT")

    def do_DELETE(self):
        self.proxy("DELETE")

    def proxy(self, method):
        if not self.path.startswith("/api/"):
            return self._send(404, b"not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        try:
            conn = http.client.HTTPConnection(MOMENT_IP, MOMENT_PORT, timeout=8)
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, self.path[4:], body=body, headers=headers)
            r = conn.getresponse()
            data = r.read()
            self._send(r.status, data, r.getheader("Content-Type") or "application/json")
        except Exception as exc:
            self._send(502, json.dumps({"error": str(exc)}).encode())

    def events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunk(data):
            self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))

        chunk(b": hej\n\n")
        self.wfile.flush()
        q = Sub()
        for n in list(latest.values()):
            q.items.append(json.dumps(n))
        q.event.set()  # send den seneste status med det samme
        with sub_lock:
            subscribers.append(q)
        try:
            while True:
                q.event.wait(15)
                q.event.clear()
                if not q.items:
                    chunk(b": ping\n\n")
                while q.items:
                    chunk(b"data: " + q.items.pop(0).encode() + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with sub_lock:
                subscribers[:] = [s for s in subscribers if s is not q]


if __name__ == "__main__":
    threading.Thread(target=notification_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Moment-styring kører på http://localhost:{PORT}  (Moment: {MOMENT_IP})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
