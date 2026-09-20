"""Local scripted HTTP model for tests; all MCP and ZMQ components remain real."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Event, Thread


class FakeLLM:
    def __init__(self, submissions, *, block=False, status=200):
        self.requests = []
        self.errors = []
        self.called = Event()
        self.release = Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    assert self.path == '/v1/chat/completions'
                    request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    index = len(owner.requests)
                    owner.requests.append(request)
                    owner.called.set()
                    if block:
                        owner.release.wait(15)
                    submission = submissions[index]
                    if isinstance(submission, str):
                        body = submission.encode()
                    else:
                        body = json.dumps({'choices': [{'message': {
                            'role': 'assistant', 'content': None, 'tool_calls': [{
                                'id': f'call_{index}', 'type': 'function',
                                'function': {'name': 'submit_identification',
                                             'arguments': json.dumps(submission)},
                            }],
                        }}]}).encode()
                    self.send_response(status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as error:
                    owner.errors.append(error)
                    self.send_error(500)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
