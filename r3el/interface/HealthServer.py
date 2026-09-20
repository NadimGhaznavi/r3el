"""HTTP health endpoint for the initial service skeletons."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthServer:
    def run(self, service: str, mode: str = "skeleton") -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, required=True)
        args = parser.parse_args()
        with self.make_server(service, args.port, mode) as server:
            server.serve_forever()

    def make_server(self, service: str, port: int, mode: str = "skeleton") -> HTTPServer:
        payload = json.dumps({"status": "ok", "service": service, "mode": mode}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/health":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = HTTPServer(("127.0.0.1", port), Handler)
        print(f"{service}: {mode}, listening on 127.0.0.1:{server.server_port}", flush=True)
        return server
