"""Persist the TV hierarchy using the caller's catalogue/checkpoint transaction."""

from hashlib import sha256
from r3el.interface.DbMgr import DbMgr
from r3el.interface.TVCatalogue import TVCatalogue


class TVCatalogueDb:
    def __init__(self, db: DbMgr):
        self.db = db

    def save_in_transaction(self, series, season: dict, episode: dict, files: list[dict], artwork: list[dict]):
        if episode['id'] == 0:
            # Missing TMDB records still need a unique key for files and credits.
            # Reuse the natural episode identity on repeated imports.
            existing = self.db.query('SELECT tmdb_id FROM tv_episodes WHERE series_id=%s '
                                     'AND season_number=%s AND episode_number=%s FOR UPDATE',
                                     (series.tmdb_id,episode['season_number'],episode['episode_number']))
            if existing:
                placeholder_id = existing[0]['tmdb_id']
            else:
                highest = self.db.query('SELECT tmdb_id FROM tv_episodes ORDER BY tmdb_id DESC LIMIT 1 FOR UPDATE')
                placeholder_id = max(4000000000, highest[0]['tmdb_id'] if highest else 0) + 1
            episode = dict(episode, id=placeholder_id)
        self.db.execute("""INSERT INTO tv_series
            (tmdb_id,title,original_title,first_air_date,overview,rating,vote_count,added_at,fetched_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))
            ON DUPLICATE KEY UPDATE title=VALUES(title), original_title=VALUES(original_title),
            first_air_date=VALUES(first_air_date),overview=VALUES(overview),rating=VALUES(rating),
            vote_count=VALUES(vote_count),fetched_at=VALUES(fetched_at)""",
            (series.tmdb_id,series.title,series.original_title,series.release_date,series.overview,
             series.rating,series.vote_count))
        self.db.execute('DELETE FROM tv_series_genres WHERE series_id=%s', (series.tmdb_id,))
        for genre in series.genres:
            self.db.execute('INSERT INTO tmdb_tv_genres VALUES (%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name)',
                            (genre.id,genre.name))
            self.db.execute('INSERT INTO tv_series_genres VALUES (%s,%s)', (series.tmdb_id,genre.id))
        self.db.execute("""INSERT INTO tv_seasons
            (series_id,season_number,tmdb_id,title,overview,air_date) VALUES (%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE tmdb_id=VALUES(tmdb_id),title=VALUES(title),
            overview=VALUES(overview),air_date=VALUES(air_date)""",
            (series.tmdb_id,season['season_number'],season['id'],season['name'],
             season.get('overview'),season.get('air_date') or None))
        self.db.execute("""INSERT INTO tv_episodes
            (tmdb_id,series_id,season_number,episode_number,title,overview,air_date,runtime)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE title=VALUES(title),overview=VALUES(overview),
            air_date=VALUES(air_date),runtime=VALUES(runtime)""",
            (episode['id'],series.tmdb_id,episode['season_number'],episode['episode_number'],
             episode['name'],episode.get('overview'),episode.get('air_date') or None,episode.get('runtime')))
        episode_id = self.db.query('SELECT tmdb_id FROM tv_episodes WHERE series_id=%s '
                                  'AND season_number=%s AND episode_number=%s',
                                  (series.tmdb_id,episode['season_number'],episode['episode_number']))[0]['tmdb_id']
        for file in files:
            self.db.execute("""INSERT INTO tv_episode_files (path_hash,path,episode_id,kind)
                VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE episode_id=VALUES(episode_id),kind=VALUES(kind)""",
                (sha256(file['destination'].encode()).digest(),file['destination'],episode_id,file['kind']))
        for art in artwork:
            self.db.execute("""INSERT INTO tv_artwork
                (path_hash,path,series_id,season_number,episode_id,kind) VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE series_id=VALUES(series_id),season_number=VALUES(season_number),
                episode_id=VALUES(episode_id),kind=VALUES(kind)""",
                (sha256(art['path'].encode()).digest(),art['path'],series.tmdb_id,
                 art.get('season_number'),episode_id if art['kind'] == 'still' else None,art['kind']))
        self._credits('tv_series_credits','series_id',series.tmdb_id,series.credits)
        self._credits('tv_episode_credits','episode_id',episode_id,TVCatalogue.episode_credits(episode))

    def _credits(self, table, column, identifier, credits):
        roles={row['name']:row['role_id'] for row in self.db.query('SELECT role_id,name FROM credit_roles')}
        self.db.execute(f'DELETE FROM {table} WHERE {column}=%s',(identifier,))
        for position, credit in enumerate(credits):
            self.db.execute('INSERT INTO people VALUES (%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name)',
                            (credit.person_id,credit.name))
            self.db.execute(f"""INSERT INTO {table}
                ({column},position,person_id,role_id,character_name,billing_order) VALUES (%s,%s,%s,%s,%s,%s)""",
                (identifier,position,credit.person_id,roles[credit.role],credit.character,credit.billing_order))

    def get(self, series_id: int) -> dict | None:
        with self.db.transaction():
            rows = self.db.query('SELECT *, first_air_date AS release_date, YEAR(first_air_date) AS release_year '
                                 'FROM tv_series WHERE tmdb_id=%s', (series_id,))
            if not rows:
                return None
            series = rows[0]
            series.update(media_type='tv', runtime=None, imdb_id=None)
            series['genres'] = self.db.query('SELECT g.name FROM tv_series_genres sg JOIN tmdb_tv_genres g '
                                            'ON g.genre_id=sg.genre_id WHERE sg.series_id=%s ORDER BY g.name', (series_id,))
            series['credits'] = self.db.query(
                'SELECT p.name,r.name AS role,c.character_name FROM tv_series_credits c '
                'JOIN people p ON p.tmdb_id=c.person_id JOIN credit_roles r ON r.role_id=c.role_id '
                'WHERE c.series_id=%s ORDER BY c.position', (series_id,))
            series['artwork'] = self.db.query(
                'SELECT DISTINCT kind FROM tv_artwork WHERE series_id=%s AND season_number IS NULL '
                'AND episode_id IS NULL', (series_id,))
            series['files'] = self.db.query(
                'SELECT f.path,f.episode_id FROM tv_episode_files f JOIN tv_episodes e ON e.tmdb_id=f.episode_id '
                'WHERE e.series_id=%s ORDER BY e.season_number,e.episode_number,f.kind', (series_id,))
            series['episodes'] = self.db.query(
                'SELECT tmdb_id,season_number,episode_number,title,overview,air_date,runtime '
                'FROM tv_episodes WHERE series_id=%s '
                'ORDER BY season_number,episode_number', (series_id,))
            credits = self.db.query(
                'SELECT c.episode_id,p.name,r.name AS role,c.character_name FROM tv_episode_credits c '
                'JOIN tv_episodes e ON e.tmdb_id=c.episode_id '
                'JOIN people p ON p.tmdb_id=c.person_id JOIN credit_roles r ON r.role_id=c.role_id '
                'WHERE e.series_id=%s ORDER BY c.position', (series_id,))
            stills = self.db.query(
                "SELECT DISTINCT episode_id FROM tv_artwork WHERE series_id=%s AND kind='still'",
                (series_id,))
            still_ids = {row['episode_id'] for row in stills}
            for episode in series['episodes']:
                episode['files'] = [row for row in series['files'] if row['episode_id'] == episode['tmdb_id']]
                episode['credits'] = [row for row in credits if row['episode_id'] == episode['tmdb_id']]
                episode['has_still'] = episode['tmdb_id'] in still_ids
            return series

    def episode_still_path(self, series_id: int, episode_id: int) -> str | None:
        rows = self.db.query("SELECT path FROM tv_artwork WHERE series_id=%s AND episode_id=%s "
                             "AND kind='still' ORDER BY path LIMIT 1", (series_id,episode_id))
        return rows[0]['path'] if rows else None

    def artwork_path(self, series_id: int, kind: str) -> str | None:
        rows = self.db.query('SELECT path FROM tv_artwork WHERE series_id=%s AND kind=%s '
                             'AND season_number IS NULL AND episode_id IS NULL ORDER BY path LIMIT 1',
                             (series_id,kind))
        return rows[0]['path'] if rows else None
