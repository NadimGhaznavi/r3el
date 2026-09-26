"""Serve R3el's event log independently of identification batches and Qwen."""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import json
from pathlib import Path
import re
import signal
from urllib.parse import parse_qs, urlsplit

import pymysql
import zmq

from r3el.activity.EventReport import EventReport
from r3el.activity.BatchPreparation import BatchPreparation
from r3el.app.BatchMatching import BatchMatching
from r3el.app.MatchingJobs import MatchingJobs
from r3el.app.ClearWorkspace import ClearWorkspace
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.constants.DMessage import DMessage
from r3el.constants.DR3el import DR3el
from r3el.interface.BatchConfiguration import BatchConfiguration
from r3el.interface.BatchControl import BatchControl
from r3el.interface.DbMgr import DbMgr
from r3el.interface.TVCatalogueDb import TVCatalogueDb
from r3el.interface.CatalogueDb import CatalogueDb
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceActionConflict, WorkspaceBusy
from r3el.interface.TMDBReferenceDb import TMDBReferenceDb
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

    def execute_match(batch_id: str, *, file_id: str | None = None, movie_id: int | None = None,
                      replace_media: bool = False) -> None:
        db = DbMgr()
        try:
            matcher = BatchMatching(WorkspaceDb(db), EventLogDb(db).record)
            if replace_media:
                matcher.replace_media(batch_id, file_id)
            elif file_id is None:
                matcher.run(batch_id)
            else:
                matcher.match_id(batch_id, file_id, movie_id)
        finally:
            db.close()

    def execute_clear(batch_id: str) -> None:
        db = DbMgr()
        try:
            ClearWorkspace(WorkspaceDb(db)).run(batch_id)
        finally:
            db.close()

    matching = MatchingJobs(execute_match)
    clearing = MatchingJobs(execute_clear)

    class ControlHTTPServer(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            matching.close()
            clearing.close()

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
                try:
                    query = parse_qs(url.query, keep_blank_values=True, max_num_fields=2)
                    if set(query) - {'result', 'refresh'} or any(len(v) != 1 for v in query.values()):
                        raise ValueError('Use result and refresh once each.')
                    refresh = query.get('refresh', ['0'])[0]
                    if refresh not in ('0', '5', '30', '60'):
                        raise ValueError('Refresh must be 0, 5, 30, or 60 seconds.')
                except ValueError as error:
                    self.send_error(400, str(error))
                    return
                result = DMessage.ACCEPTED if query.get('result') == [DMessage.ACCEPTED] else None
                self.respond_control(result=result, refresh=int(refresh))
                return
            if url.path == '/health':
                self.respond(200, b'{"status":"ok","service":"r3el-control"}', 'application/json')
                return
            catalogue_path = url.path.replace('/catalogue/tv/', '/catalogue/', 1)
            catalogue = re.fullmatch(r'/catalogue(?:/([0-9]{1,10})(?:/(poster|backdrop))?)?', catalogue_path)
            if catalogue:
                movie_id = int(catalogue.group(1)) if catalogue.group(1) else None
                if movie_id is not None and not 1 <= movie_id <= 4294967295:
                    self.send_error(404, 'Movie not found')
                    return
                try:
                    query = parse_qs(url.query, keep_blank_values=True, max_num_fields=100)
                    if set(query) - {'title', 'recent_page', 'category'} or any(
                            len(v) != 1 for k, v in query.items() if k != 'category'):
                        raise ValueError('Supply title and recent_page once each.')
                    title = query.get('title', [''])[0].strip()
                    category_values = query.get('category', [])
                    if any(not re.fullmatch(r'[0-9]{1,10}', value)
                           or not 1 <= int(value) <= 4294967295 for value in category_values):
                        raise ValueError('Categories must be positive genre IDs.')
                    category_ids = list(dict.fromkeys(int(value) for value in category_values))
                    recent_page = query.get('recent_page', ['0'])[0]
                    if not re.fullmatch(r'[0-9]{1,9}', recent_page):
                        raise ValueError('recent_page must be a nonnegative integer.')
                except ValueError as error:
                    self.send_error(400, str(error))
                    return
                self.respond_catalogue(movie_id, catalogue.group(2), title, int(recent_page), category_ids, 'tv' if url.path.startswith('/catalogue/tv/') else 'movie')
                return
            job_path = re.fullmatch(r'/workspace/(match|clear)/status/([A-Za-z0-9-]{1,36})', url.path)
            if job_path:
                job = (clearing if job_path.group(1) == 'clear' else matching).current()
                if job is None or job['id'] != job_path.group(2):
                    self.respond(404, b'{"status":"unknown"}', 'application/json')
                else:
                    self.respond(200, json.dumps(job).encode(), 'application/json')
                return
            match = re.fullmatch(r'/matches/([A-Za-z0-9-]{1,36})/([A-Za-z0-9-]{1,36})', url.path)
            if match:
                self.respond_match(*match.groups())
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

        def respond_catalogue(self, movie_id: int | None, artwork: str | None, title: str, recent_page: int, category_ids: list[int], media_type: str):
            try:
                db = DbMgr()
                try:
                    catalogue = CatalogueDb(db)
                    if media_type == 'tv':
                        catalogue = TVCatalogueDb(db)
                    if artwork:
                        value = catalogue.artwork_path(movie_id, artwork)
                    elif movie_id is not None:
                        value = catalogue.get(movie_id)
                    else:
                        recent = catalogue.recent(offset=recent_page * 4, limit=5)
                        categories = catalogue.categories()
                        value = (catalogue.movies_in_categories(category_ids) if category_ids
                                 else catalogue.movies(title) if title else [])
                finally:
                    db.close()
            except pymysql.MySQLError:
                logging.exception('Unable to read the catalogue')
                self.respond(503, pages.render('catalogue_error.html', refresh=0))
                return
            if value is None:
                self.send_error(404, 'Catalogue entry not found')
            elif artwork:
                path = Path(value)
                content_type = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}.get(path.suffix.lower())
                if not content_type or path.is_symlink():
                    self.send_error(404, 'Artwork not found')
                    return
                try:
                    content = path.read_bytes()
                except OSError:
                    self.send_error(404, 'Artwork not found')
                    return
                self.respond(200, content, content_type)
            elif movie_id is not None:
                self.respond(200, pages.render('catalogue_movie.html', movie=value, media_type=media_type, refresh=0))
            else:
                self.respond(200, pages.render('catalogue.html', movies=value, recent=recent[:4],
                                               recent_page=recent_page, has_older=len(recent) > 4,
                                               search_title=title, catalogue_categories=categories,
                                               selected_categories=category_ids, refresh=0))

        def respond_control(self, status: int = 200, refresh: int = 0, **values):
            try:
                db = DbMgr()
                try:
                    workspace = WorkspaceDb(db).snapshot()
                    latest_event = (EventLogDb(db).latest_for_processes(
                        [workspace.id] + [item.id for item in workspace.files])
                        if workspace is not None else None)
                finally:
                    db.close()
            except pymysql.MySQLError:
                logging.exception('Unable to read the workspace')
                self.respond(503, pages.render('workspace_error.html', refresh=0))
                return
            job = matching.current()
            active_job = (job if workspace is not None and job is not None
                          and job['batch_id'] == workspace.id and job['status'] == 'running' else None)
            self.respond(status, pages.render('control.html', workspace=workspace, refresh=refresh,
                                             matching_job=active_job, latest_event=latest_event, **values))

        def do_POST(self):
            if self.path not in (DR3el.NEW_BATCH_URL, DR3el.FILE_ACTION_URL, DR3el.MATCH_TMDB_URL, DR3el.STOP_BATCH_URL, DR3el.MATCH_TMDB_ID_URL, DR3el.REPLACE_MEDIA_URL, DR3el.CLEAR_BATCH_URL):
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
                                  keep_blank_values=True, max_num_fields=4)
                if any(len(values) != 1 for values in fields.values()):
                    raise ValueError('Repeated form field.')
                payload = {name: values[0] for name, values in fields.items()}
                if self.path == DR3el.MATCH_TMDB_ID_URL:
                    if (set(payload) != {'batch_id', 'file_id', 'movie_id'}
                            or any(not re.fullmatch(r'[A-Za-z0-9-]{1,36}', payload[key]) for key in ('batch_id', 'file_id'))
                            or not re.fullmatch(r'[0-9]{1,10}', payload['movie_id'])
                            or not 1 <= int(payload['movie_id']) <= 4294967295):
                        raise ValueError('Supply a valid batch, file, and TMDB movie ID.')
                elif self.path == DR3el.REPLACE_MEDIA_URL:
                    if (set(payload) != {'batch_id', 'file_id'}
                            or any(not re.fullmatch(r'[A-Za-z0-9-]{1,36}', value) for value in payload.values())):
                        raise ValueError('Supply a valid batch and file ID.')
                elif self.path in (DR3el.MATCH_TMDB_URL, DR3el.STOP_BATCH_URL, DR3el.CLEAR_BATCH_URL):
                    if set(payload) != {'batch_id'} or not re.fullmatch(r'[A-Za-z0-9-]{1,36}', payload['batch_id']):
                        raise ValueError('Supply a valid batch_id.')
                elif self.path == DR3el.FILE_ACTION_URL:
                    self.save_file_action(payload)
                    return
                else:
                    refresh = payload.pop('refresh', '0')
                    if refresh not in ('0', '5', '30', '60'):
                        raise ValueError('Invalid refresh interval.')
                    payload['batch_size'] = int(payload['batch_size'])
                    parameters = BatchConfiguration.resolve(payload)
            except (KeyError, ValueError):
                if self.path in (DR3el.FILE_ACTION_URL, DR3el.MATCH_TMDB_URL, DR3el.STOP_BATCH_URL, DR3el.MATCH_TMDB_ID_URL, DR3el.REPLACE_MEDIA_URL, DR3el.CLEAR_BATCH_URL):
                    self.respond(400, b'{"saved":false}', 'application/json')
                    return
                self.respond_control(400, result=DMessage.INVALID_PARAMETERS)
                return
            if self.path == DR3el.MATCH_TMDB_ID_URL:
                self.match_batch(payload['batch_id'], file_id=payload['file_id'], movie_id=int(payload['movie_id']))
                return
            if self.path == DR3el.REPLACE_MEDIA_URL:
                self.match_batch(payload['batch_id'], file_id=payload['file_id'], replace_media=True)
                return
            if self.path == DR3el.CLEAR_BATCH_URL:
                job = clearing.submit(payload['batch_id'])
                self.respond(202 if job else 409,
                             json.dumps({'accepted': job is not None, 'job_id': job['id'] if job else None}).encode(),
                             'application/json')
                return
            if self.path == DR3el.STOP_BATCH_URL:
                self.stop_batch(payload['batch_id'])
                return
            if self.path == DR3el.MATCH_TMDB_URL:
                self.match_batch(payload['batch_id'])
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
                self.send_header('Location', '/?result=' + DMessage.ACCEPTED
                                 + ('&refresh=' + refresh if refresh != '0' else ''))
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

        def save_file_action(self, payload: dict):
            if set(payload) != {'batch_id', 'file_id', 'action'}:
                raise ValueError('Supply batch_id, file_id, and action.')
            for name in ('batch_id', 'file_id'):
                if not payload[name].strip() or len(payload[name]) > 36:
                    raise ValueError('Invalid workspace identifier.')
            action = MediaFileAction(payload['action'])
            try:
                db = DbMgr()
                try:
                    batch = WorkspaceDb(db).save_action(payload['batch_id'], payload['file_id'], action)
                finally:
                    db.close()
            except (WorkspaceActionConflict, WorkspaceBusy):
                self.respond(409, b'{"saved":false}', 'application/json')
                return
            except pymysql.MySQLError:
                logging.exception('Unable to save file action')
                self.respond(503, b'{"saved":false}', 'application/json')
                return
            self.respond(200, json.dumps({'saved': True, 'ready': BatchPreparation.ready(batch)}).encode(),
                         'application/json')

        def stop_batch(self, batch_id: str):
            job = matching.current()
            active = job is not None and job['batch_id'] == batch_id and job['status'] == 'running'
            try:
                db = DbMgr()
                try:
                    WorkspaceDb(db).request_stop(batch_id, matching=active)
                finally:
                    db.close()
            except WorkspaceActionConflict:
                self.respond(409, b'{"accepted":false}', 'application/json')
                return
            except pymysql.MySQLError:
                logging.exception('Unable to request batch stop')
                self.respond(503, b'{"accepted":false}', 'application/json')
                return
            self.respond(202, b'{"accepted":true}', 'application/json')

        def match_batch(self, batch_id: str, **selection):
            job = matching.submit(batch_id, **selection)
            if job is None:
                self.respond(409, b'{"accepted":false}', 'application/json')
                return
            self.respond(202, json.dumps({'accepted': True, 'job_id': job['id']}).encode(), 'application/json')

        def respond_match(self, batch_id: str, file_id: str):
            try:
                db = DbMgr()
                try:
                    workspace = WorkspaceDb(db).snapshot()
                    reference = TMDBReferenceDb(db).load()
                finally:
                    db.close()
            except pymysql.MySQLError:
                logging.exception('Unable to read TMDB matching results')
                self.respond(503, pages.render('workspace_error.html', refresh=0))
                return
            item = next((item for item in workspace.files if item.id == file_id), None) \
                if workspace is not None and workspace.id == batch_id else None
            if item is None or item.tmdb_match is None or item.tmdb_match.skipped:
                self.send_error(404, 'Match results not found')
                return
            self.respond(200, pages.render('match.html', file=item, match=item.tmdb_match,
                         reference=reference,
                         refresh=0))

        def respond(self, status: int, body: bytes, content_type: str = 'text/html; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

    return ControlHTTPServer((host, port), Handler)


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
