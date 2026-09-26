"""Exercise category intersection queries against relational fixture data."""

import sqlite3
import unittest

from r3el.interface.CatalogueDb import CatalogueDb


class CategorySearchTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function('YEAR', 1, lambda value: int(value[:4]) if value else None)
        self.connection.create_function('LOCATE', 2, lambda needle, value: value.find(needle) + 1)
        self.connection.executescript("""
            CREATE TABLE movies (
                tmdb_id INTEGER PRIMARY KEY, title TEXT, release_year INTEGER, poster_path TEXT, added_at TEXT);
            CREATE TABLE tv_series (tmdb_id INTEGER, title TEXT, first_air_date TEXT, added_at TEXT);
            CREATE TABLE tv_seasons (series_id INTEGER, season_number INTEGER);
            CREATE TABLE tv_episodes (tmdb_id INTEGER, series_id INTEGER, season_number INTEGER);
            CREATE TABLE tv_artwork (series_id INTEGER, kind TEXT, path TEXT, season_number INTEGER, episode_id INTEGER);
            CREATE TABLE tv_series_genres (series_id INTEGER,genre_id INTEGER);
            CREATE TABLE movie_genres (movie_id INTEGER, genre_id INTEGER,
                                       PRIMARY KEY (movie_id, genre_id));
            INSERT INTO movies VALUES
                (1, 'Action only', 2020, NULL, '2020-01-01'),
                (2, 'Action comedy', 2020, NULL, '2020-01-01'),
                (3, 'Action comedy drama', 2020, NULL, '2020-01-01'),
                (4, 'Comedy only', 2020, NULL, '2020-01-01');
            INSERT INTO movie_genres VALUES
                (1, 28), (2, 28), (2, 35), (3, 28), (3, 35), (3, 18), (4, 35);
        """)
        self.catalogue = CatalogueDb(self)

    def query(self, sql, params=()):
        # Only the DB driver's placeholder syntax differs for these portable queries.
        return [dict(row) for row in self.connection.execute(sql.replace('%s', '?'), params)]

    def test_counts_separate_movies_and_series(self):
        self.assertEqual(self.catalogue.counts(),dict(movies=4,tv_shows=0,tv_seasons=0,tv_episodes=0))
        self.connection.execute("INSERT INTO tv_series VALUES (1,'Show','2020-01-01','2020-01-01')")
        self.assertEqual(self.catalogue.counts(),dict(movies=4,tv_shows=1,tv_seasons=0,tv_episodes=0))
        self.connection.executescript("""
            INSERT INTO tv_series VALUES (2,'Second show','2020-01-01','2020-01-01');
            INSERT INTO tv_seasons VALUES (1,1),(2,1);
            INSERT INTO tv_episodes VALUES (11,1,1),(12,1,1),(21,2,1);
        """)
        self.assertEqual(self.catalogue.counts(),dict(movies=4,tv_shows=2,tv_seasons=2,tv_episodes=3))

    def test_random_includes_movies_shows_and_episodes_without_duplicates(self):
        self.connection.create_function('RAND', 0, lambda: 0.5)
        self.connection.executescript("""
            DELETE FROM movies WHERE tmdb_id > 2;
            ALTER TABLE tv_episodes ADD COLUMN title TEXT;
            ALTER TABLE tv_episodes ADD COLUMN air_date TEXT;
            ALTER TABLE tv_episodes ADD COLUMN episode_number INTEGER;
            INSERT INTO tv_series VALUES (1,'Show','2020-01-01','2020-01-01');
            INSERT INTO tv_episodes VALUES (1,1,2,'Episode','2021-01-01',3);
            INSERT INTO tv_artwork VALUES (1,'still','/still.jpg',2,1);
            INSERT INTO tv_artwork VALUES (1,'poster','/poster.jpg',NULL,NULL);
        """)
        rows = self.catalogue.random()
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({(r['media_type'], r['tmdb_id']) for r in rows}), 4)
        episode = next(r for r in rows if r['media_type'] == 'episode')
        self.assertEqual((episode['series_title'], episode['poster_path'], episode['release_year']),
                         ('Show', '/poster.jpg', 2021))
        self.connection.execute("INSERT INTO movies VALUES (5,'Extra',2020,NULL,'2020-01-01')")
        self.assertEqual(len(self.catalogue.random()), 4)
        self.connection.executescript('DELETE FROM tv_episodes; DELETE FROM tv_series; DELETE FROM movies;')
        self.assertEqual(self.catalogue.random(), [])
        self.connection.execute("INSERT INTO movies VALUES (1,'Only',2020,NULL,'2020-01-01')")
        self.assertEqual(len(self.catalogue.random()), 1)

    def ids(self, categories):
        return {row['tmdb_id'] for row in self.catalogue.movies_in_categories(categories)}

    def test_initial_search_includes_movie_and_show_titles(self):
        self.assertEqual(self.catalogue.available_initials(), ['a', 'c'])
        self.connection.executescript("""
            INSERT INTO tv_series VALUES (10,'action show','2020-01-01','2020-01-01');
            INSERT INTO tv_series VALUES (11,'11.22.63','2020-01-01','2020-01-01');
            INSERT INTO tv_series VALUES (14,'Beta show','2020-01-01','2020-01-01');
            INSERT INTO movies VALUES (12,'#Title',2020,NULL,'2020-01-01');
            INSERT INTO movies VALUES (13,'  Zebra',2020,NULL,'2020-01-01');
            INSERT INTO tv_episodes VALUES (100,10,1),(101,10,1);
        """)
        found = self.catalogue.titles_by_initial('a')
        self.assertEqual(self.catalogue.available_initials(), ['a', 'b', 'c', 'z'])
        self.assertEqual(len(found), 4)
        self.assertEqual({r['media_type'] for r in found}, {'tv', 'movie'})
        self.assertEqual({r['title'] for r in self.catalogue.titles_by_initial('symbols')}, {'11.22.63', '#Title'})
        self.assertEqual([r['title'] for r in self.catalogue.titles_by_initial('z')], ['  Zebra'])
        self.assertEqual(self.catalogue.titles_by_initial('x'), [])

    def test_title_type_filters_and_categories_include_both(self):
        self.connection.executescript("""
            INSERT INTO tv_series VALUES (1,'Action show','2020-01-01','2020-01-01');
            INSERT INTO tv_series_genres VALUES (1,28),(1,35);
        """)
        self.assertEqual({r['media_type'] for r in self.catalogue.movies('Action','movie')},{'movie'})
        self.assertEqual([(r['tmdb_id'],r['media_type']) for r in self.catalogue.movies('Action','tv')],[(1,'tv')])
        self.assertEqual(len(self.catalogue.movies('Action','both')),4)
        self.assertEqual({(r['tmdb_id'],r['media_type']) for r in self.catalogue.movies_in_categories([28,35])},
                         {(2,'movie'),(3,'movie'),(1,'tv')})

    def test_additional_categories_narrow_results(self):
        self.assertEqual(self.ids([28]), {1, 2, 3})
        self.assertEqual(self.ids([28, 35]), {2, 3})
        self.assertEqual(self.ids([28, 35, 18]), {3})

    def test_category_order_and_repeated_selections_do_not_change_results(self):
        self.assertEqual(self.ids([35, 28]), {2, 3})
        self.assertEqual(self.ids([28, 35, 28]), {2, 3})

    def test_missing_category_produces_no_matches(self):
        self.assertEqual(self.ids([28, 999]), set())
