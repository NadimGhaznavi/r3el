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
