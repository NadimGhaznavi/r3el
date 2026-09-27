"""Recognize explicit episodes and consistently numbered series directories."""

from collections import Counter
from os.path import commonpath
from pathlib import Path
import re


class TVPattern:
    # A separator between S/season and E/episode is common in release names.
    EXPLICIT = re.compile(
        r'(?i)(?:S(?:eason)?[ ._-]*(\d{1,3})[ ._-]*E(?:pisode)?[ ._-]*(\d{1,3})'
        r'|(?<![a-z0-9])(\d{1,2})x(\d{1,3}))(?!\d)')
    SEASON = re.compile(r'(?i)(?<![a-z0-9])season[ ._-]*(\d{1,3})(?!\d)')
    COMBINED = re.compile(
        r'(?i)^(?:[ ._-]*E\d|x\d|[-+&][ ._]*\d| +[+&] *\d'
        r'| +(?:- *)?\d{1,3}(?!\d)(?:$|[ ._-]*E\d))')
    EXTRA = re.compile(r'(?i)(?<![a-z0-9])(?:extras?|featurettes?|samples?|trailers?)(?![a-z0-9])')

    @classmethod
    def match(cls, paths: list[str], directory: str | None = None) -> dict[str, dict] | None:
        """Select unambiguous episodes; unrelated or conflicting files stay at source."""
        episodes = {}
        numbered = {}
        titles = {}
        weak = set()
        for path in paths:
            file = Path(path)
            if any(cls.EXTRA.search(part) for part in file.parts):
                continue
            season = cls._season(file)
            match = cls.EXPLICIT.search(file.stem)
            if match is None:
                # A release folder often spells out the episode when its video does not.
                match = cls.EXPLICIT.search(file.parent.name)
                text = file.parent.name
            else:
                text = file.stem
            if match:
                if cls.COMBINED.search(text[match.end():]):
                    continue
                explicit_season, episode = map(int, match.groups()[:2] if match[1] else match.groups()[2:])
                if season is not None and season != explicit_season:
                    continue
                season = explicit_season
                title = text[:match.start()]
            else:
                # Compact 103-style numbers need a season folder to distinguish them
                # from movie titles, years and release resolutions.
                compact = re.search(r'(?<![a-z0-9])(\d{3})(?![a-z0-9])', file.stem, re.I)
                if compact and season is not None and int(compact[1][0]) == season:
                    if cls.COMBINED.search(file.stem[compact.end():]):
                        continue
                    episode = int(compact[1][1:])
                    title = file.stem[:compact.start()]
                else:
                    number = re.fullmatch(r'(.+?)[-_. ](\d{1,3})', file.stem)
                    if number and len(number[2]) == 1 and season is None:
                        weak.add(path)
                    if number is None:
                        number = re.match(r'(.+?) +(\d{1,3}) +[\x27\x22]*(?=[a-z])', file.stem, re.I)
                    if number is None or re.search(r'(?i)(?:part|cd|disc)[-_. ]*$', number[1]):
                        continue
                    episode = int(number[2])
                    numbered[path] = number[1].casefold()
                    title = number[1]
            if episode > 0:
                episodes[path] = {'season_number': season, 'episode_number': episode}
                titles[path] = cls._title(title)
        # Bare numbered filenames require a repeated prefix, even alongside explicit
        # episodes. A stray movie sequel must not enter the TV mapping dialogue.
        bases = Counter(numbered[path] for path in episodes if path in numbered)
        episodes = {path: value for path, value in episodes.items()
                    if path not in numbered or bases[numbered[path]] >= 2}
        # Preserve the all-numbered directory convention, but don't mistake a
        # few unpadded movie sequels in a mixed collection for a TV series.
        if len(episodes) != len(paths):
            episodes = {path: value for path, value in episodes.items() if path not in weak}
        if episodes:
            root = Path(directory or commonpath([str(Path(path).parent) for path in paths]))
            root_title = cls._title(root.name)
            for path, title in titles.items():
                if not title:
                    parent = Path(path).parent
                    while parent != root and (cls.SEASON.search(parent.name)
                                               or cls._title(parent.name) in ('tvseries', 'episodes')):
                        parent = parent.parent
                    titles[path] = cls._title(parent.name)
            named = {title for path, title in titles.items() if path in episodes and title}
            if root_title and root_title in named:
                episodes = {path: value for path, value in episodes.items()
                            if not titles[path] or titles[path].startswith(root_title)}
            elif named:
                shortest = min(named, key=len)
                if any(not title.startswith(shortest) for title in named):
                    return None
        pairs = Counter((value['season_number'], value['episode_number']) for value in episodes.values())
        episodes = {path: value for path, value in episodes.items()
                    if pairs[value['season_number'], value['episode_number']] == 1}
        return episodes or None

    @staticmethod
    def _title(text: str) -> str:
        # Release years and separator choices do not change the series title.
        text = re.sub(r'^\s*(?:\[[^\]]+\][ ._-]*)+', '', text)
        text = re.sub(r'[([]\d{4}[)\]]', '', text)
        return re.sub(r'[^a-z0-9]', '', text.casefold())

    @classmethod
    def is_candidate(cls, paths: list[str]) -> bool:
        """Keep ambiguous TV directories out of the movie-part fallback."""
        return any(cls.EXPLICIT.search(Path(path).stem)
                   or any(cls.SEASON.search(parent.name) or cls.EXPLICIT.search(parent.name)
                          for parent in Path(path).parents)
                   for path in paths)

    @classmethod
    def _season(cls, path: Path) -> int | None:
        for parent in path.parents:
            match = cls.SEASON.search(parent.name)
            if match:
                return int(match[1])
        return None

    @staticmethod
    def numbered_files(expected: dict) -> list[dict]:
        return [dict(file_id=number, path=path, **expected[path])
                for number, path in enumerate(sorted(expected), 1)]

    @staticmethod
    def validate(mapping, expected: list[dict]) -> list[dict]:
        if not isinstance(mapping, list) or len(mapping) != len(expected):
            raise ValueError('Supply one episode mapping for every supplied video.')
        files = {row['file_id']: row for row in expected}
        used_ids, numbers, resolved = set(), set(), []
        for row in mapping:
            if not isinstance(row, dict) or set(row) != {'file_id', 'season_number', 'episode_number'}:
                raise ValueError('Each episode needs file_id, season_number and episode_number.')
            file_id, season, episode = row['file_id'], row['season_number'], row['episode_number']
            if type(file_id) is not int or file_id not in files:
                raise ValueError(f'Unknown file_id {file_id!r}; use the supplied integer IDs.')
            if file_id in used_ids:
                raise ValueError(f'Duplicate file_id {file_id}; use each supplied ID exactly once.')
            if type(season) is not int or not 0 <= season <= 999 or type(episode) is not int or not 1 <= episode <= 999:
                raise ValueError('Use season 0–999 and episode 1–999.')
            known = files[file_id]
            if any(known[key] is not None and known[key] != row[key] for key in ('season_number', 'episode_number')):
                raise ValueError('Do not change explicit season or episode numbers.')
            if (season, episode) in numbers:
                raise ValueError('Two videos cannot map to the same episode.')
            used_ids.add(file_id)
            resolved.append(dict(path=known['path'], season_number=season, episode_number=episode))
            numbers.add((season, episode))
        return resolved
