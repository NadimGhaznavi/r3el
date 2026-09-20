"""Serve R3el's event log independently of identification batches and Qwen."""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import re
import signal
from urllib.parse import parse_qs, urlsplit

import pymysql

from r3el.activity.EventReport import EventReport
from r3el.constants.DR3el import DR3el
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb
from r3el.server.EventPages import EventPages


@contextmanager
def event_log():
    # Each request owns its connection; MariaDB connections are not shared.
    db = DbMgr()
    try:
        yield EventLogDb(db)
    finally:
        db.close()


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    pages = EventPages()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/health':
                self.respond(200, b'{"status":"ok","service":"r3el-control"}', 'application/json')
                return
            if url.path not in ('/', '/events') and not re.fullmatch(r'/events/[0-9]{1,20}', url.path):
                self.send_error(404, 'Page not found')
                return
            try:
                query = parse_qs(url.query, keep_blank_values=True, max_num_fields=3)
                if set(query) - {'category', 'subcategory', 'refresh'} or any(len(v) != 1 for v in query.values()):
                    raise ValueError('Use category, subcategory, and refresh once each.')
                category = query.get('category', [''])[0] or None
                subcategory = query.get('subcategory', [''])[0] or None
                refresh = query.get('refresh', ['0'])[0]
                if refresh not in ('0', '5', '30', '60'):
                    raise ValueError('Refresh must be 0, 5, 30, or 60 seconds.')
            except ValueError as error:
                self.send_error(400, str(error))
                return
            try:
                with event_log() as events:
                    if url.path in ('/', '/events'):
                        try:
                            rows = EventReport(events).recent(category, subcategory)
                        except ValueError as error:
                            self.send_error(400, str(error))
                            return
                        body = pages.render('events.html', events=rows, category=category,
                                            subcategory=subcategory, refresh=int(refresh))
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
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535.')

    def stop(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        with make_server(args.host, args.port) as server:
            print(f'R3el Control: http://{args.host}:{server.server_port}/', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    main()
