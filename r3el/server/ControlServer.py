"""Serve R3el's event log independently of identification batches and Qwen."""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import re
import signal
from urllib.parse import parse_qs, urlsplit

import pymysql
import zmq

from r3el.activity.EventReport import EventReport
from r3el.constants.DMessage import DMessage
from r3el.constants.DR3el import DR3el
from r3el.interface.BatchConfiguration import BatchConfiguration
from r3el.interface.BatchControl import BatchControl
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.WorkspaceDb import WorkspaceDb
from r3el.server.EventPages import EventPages


@contextmanager
def event_log():
    # Each request owns its connection; MariaDB connections are not shared.
    db = DbMgr()
    try:
        yield EventLogDb(db)
    finally:
        db.close()


def make_server(host: str, port: int, endpoint: str = DR3el.ZMQ_ENDPOINT) -> ThreadingHTTPServer:
    pages = EventPages()
    batches = BatchControl(endpoint)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == DR3el.CONTROL_LOGO_URL:
                self.respond(200, Path(__file__).with_name('static').joinpath('r3el.png').read_bytes(), 'image/png')
                return
            if url.path == '/':
                result = DMessage.ACCEPTED if url.query == 'result=' + DMessage.ACCEPTED else None
                self.respond_control(result=result)
                return
            if url.path == '/health':
                self.respond(200, b'{"status":"ok","service":"r3el-control"}', 'application/json')
                return
            if url.path != '/events' and not re.fullmatch(r'/events/[0-9]{1,20}', url.path):
                self.send_error(404, 'Page not found')
                return
            try:
                query = parse_qs(url.query, keep_blank_values=True, max_num_fields=4)
                if set(query) - {'category', 'subcategory', 'name', 'refresh'} or any(len(v) != 1 for v in query.values()):
                    raise ValueError('Use category, subcategory, name, and refresh once each.')
                category = query.get('category', [''])[0] or None
                subcategory = query.get('subcategory', [''])[0] or None
                name = query.get('name', [''])[0] or None
                refresh = query.get('refresh', ['0'])[0]
                if refresh not in ('0', '5', '30', '60'):
                    raise ValueError('Refresh must be 0, 5, 30, or 60 seconds.')
            except ValueError as error:
                self.send_error(400, str(error))
                return
            try:
                with event_log() as events:
                    if url.path == '/events':
                        try:
                            category, subcategory, name = EventReport.resolve_filters(category, subcategory, name)
                            rows = events.recent(category=category, subcategory=subcategory, name=name)
                        except ValueError as error:
                            self.send_error(400, str(error))
                            return
                        body = pages.render('events.html', events=rows, category=category,
                                            subcategory=subcategory, name=name, refresh=int(refresh))
                    else:
                        event_id = int(url.path.rsplit('/', 1)[1])
                        if not 1 <= event_id <= 18446744073709551615:
                            self.send_error(404, 'Event not found')
                            return
                        event = events.get(event_id)
                        if event is None:
                            self.send_error(404, 'Event not found')
                            return
                        body = pages.render('event.html', event=event, refresh=0)
            except pymysql.MySQLError:
                logging.exception('Unable to read the event log')
                self.respond(503, pages.render('error.html', refresh=0))
                return
            self.respond(200, body)

        def respond_control(self, status: int = 200, **values):
            try:
                db = DbMgr()
                try:
                    workspace = WorkspaceDb(db).snapshot()
                finally:
                    db.close()
            except pymysql.MySQLError:
                logging.exception('Unable to read the workspace')
                self.respond(503, pages.render('workspace_error.html', refresh=0))
                return
            refresh = 0
            if self.command == 'GET' and (workspace is not None or values.get('result') == DMessage.ACCEPTED):
                refresh = DR3el.WORKSPACE_REFRESH_SECONDS
            self.respond(status, pages.render('control.html', workspace=workspace, refresh=refresh, **values))

        def do_POST(self):
            if self.path != DR3el.NEW_BATCH_URL:
                self.send_error(404)
                return
            # Browser form submissions must originate from this control server.
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                self.send_error(403)
                return
            try:
                if self.headers.get_content_type() != 'application/x-www-form-urlencoded':
                    raise ValueError('Unsupported form encoding.')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= DR3el.MAX_CONTROL_BODY_BYTES:
                    raise ValueError('Invalid form length.')
                fields = parse_qs(self.rfile.read(length).decode('utf-8'),
                                  keep_blank_values=True, max_num_fields=3)
                if any(len(values) != 1 for values in fields.values()):
                    raise ValueError('Repeated form field.')
                payload = {name: values[0] for name, values in fields.items()}
                payload['batch_size'] = int(payload['batch_size'])
                parameters = BatchConfiguration.resolve(payload)
            except (KeyError, ValueError):
                self.respond_control(400, result=DMessage.INVALID_PARAMETERS)
                return
            try:
                response = batches.new_batch(parameters)
            except (zmq.ZMQError, ValueError, KeyError, TypeError):
                logging.exception('Unable to confirm batch acceptance; request will not be retried')
                self.respond_control(503, result=DMessage.UNAVAILABLE)
                return
            if response['status'] == DMessage.ACCEPTED:
                # Refreshing the result page must not submit the batch again.
                self.send_response(303)
                self.send_header('Location', '/?result=' + DMessage.ACCEPTED)
                self.send_header('Content-Length', '0')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return
            result = response['status']
            if result == DMessage.ERROR:
                result = response['error']['code']
            status = 409 if result == DMessage.BUSY else 400
            if result == DMessage.NOT_CONFIGURED:
                status = 503
            self.respond_control(status, result=result,
                                 input_directory=parameters.input_directory,
                                 output_directory=parameters.output_directory,
                                 batch_size=parameters.batch_size)

        def respond(self, status: int, body: bytes, content_type: str = 'text/html; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=DR3el.PORT)
    parser.add_argument('--zmq-endpoint', default=DR3el.ZMQ_ENDPOINT)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535.')

    def stop(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        with make_server(args.host, args.port, args.zmq_endpoint) as server:
            print(f'R3el Control: http://{args.host}:{server.server_port}/', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    main()
