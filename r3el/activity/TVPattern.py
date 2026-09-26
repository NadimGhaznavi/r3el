"""Recognize explicit episodes and consistently numbered series directories."""

from pathlib import Path
import re


class TVPattern:
    @staticmethod
    def match(paths: list[str]) -> dict[str, dict] | None:
        episodes = {}
        bases = set()
        explicit = False
        for path in paths:
            stem = Path(path).stem
            match = re.search(r'(?i)(?<![a-z0-9])S(\d{1,3})E(\d{1,3})(?!\d|[Ee]\d|[- ]\d)', stem)
            if match:
                explicit = True
                season, episode = map(int, match.groups())
            else:
                match = re.fullmatch(r'(.+?)[-_. ](\d{1,3})', stem)
                if not match or re.search(r'(?i)(?:part|cd|disc)[-_. ]*$', match[1]):
                    return None
                bases.add(match[1].casefold())
                episode = int(match[2])
                folder = re.fullmatch(r'(?i)season[-_ ]*(\d{1,3})', Path(path).parent.name)
                season = int(folder[1]) if folder else None
            if episode < 1:
                return None
            episodes[path] = {'season_number': season, 'episode_number': episode}
        if not paths or (not explicit and (len(paths) < 2 or len(bases) != 1)):
            return None
        pairs = [(v['season_number'], v['episode_number']) for v in episodes.values()]
        return episodes if len(set(pairs)) == len(pairs) else None

    @staticmethod
    def validate(mapping, expected: dict) -> list[dict]:
        if not isinstance(mapping, list) or len(mapping) != len(expected):
            raise ValueError('Supply one episode mapping for every supplied video.')
        paths, numbers = set(), set()
        for row in mapping:
            if not isinstance(row, dict) or set(row) != {'path', 'season_number', 'episode_number'}:
                raise ValueError('Each episode needs path, season_number and episode_number.')
            path, season, episode = row['path'], row['season_number'], row['episode_number']
            if not isinstance(path, str) or path not in expected or path in paths:
                raise ValueError('Use every supplied video path exactly once.')
            if type(season) is not int or not 0 <= season <= 999 or type(episode) is not int or not 1 <= episode <= 999:
                raise ValueError('Use season 0–999 and episode 1–999.')
            known = expected[path]
            if any(known[key] is not None and known[key] != row[key] for key in known):
                raise ValueError('Do not change explicit season or episode numbers.')
            if (season, episode) in numbers:
                raise ValueError('Two videos cannot map to the same episode.')
            paths.add(path)
            numbers.add((season, episode))
        return mapping
