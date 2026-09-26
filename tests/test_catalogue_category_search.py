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
        self.connection.executescript("""
            CREATE TABLE movies (
                tmdb_id INTEGER PRIMARY KEY, title TEXT, release_year INTEGER, poster_path TEXT, added_at TEXT);
            CREATE TABLE tv_series (tmdb_id INTEGER, title TEXT, first_air_date TEXT, added_at TEXT);
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
        self.assertEqual(self.catalogue.counts(),dict(movies=4,tv_shows=0))
        self.connection.execute("INSERT INTO tv_series VALUES (1,'Show','2020-01-01','2020-01-01')")
        self.assertEqual(self.catalogue.counts(),dict(movies=4,tv_shows=1))

    def ids(self, categories):
        return {row['tmdb_id'] for row in self.catalogue.movies_in_categories(categories)}

    def test_additional_categories_narrow_results(self):
        self.assertEqual(self.ids([28]), {1, 2, 3})
        self.assertEqual(self.ids([28, 35]), {2, 3})
        self.assertEqual(self.ids([28, 35, 18]), {3})

    def test_category_order_and_repeated_selections_do_not_change_results(self):
        self.assertEqual(self.ids([35, 28]), {2, 3})
        self.assertEqual(self.ids([28, 35, 28]), {2, 3})

    def test_missing_category_produces_no_matches(self):
        self.assertEqual(self.ids([28, 999]), set())
