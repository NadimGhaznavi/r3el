"""Choose a movie's preferred container without inferring encoding quality."""

from pathlib import Path


class MovieFormats:
    ORDER = ('mkv', 'mp4', 'm4v', 'avi', 'mov', 'wmv', 'flv', 'mpg', 'mpeg')

    @classmethod
    def rank(cls, path: str) -> int:
        extension = Path(path).suffix.lower().lstrip('.')
        if extension == 'mpeg':
            extension = 'mpg'
        if extension not in cls.ORDER:
            raise ValueError(f'Unsupported movie format: {Path(path).suffix or "(no extension)"}')
        return cls.ORDER.index(extension)

    @classmethod
    def choose(cls, source: str, existing: list[str]) -> tuple[str, list[str]]:
        # Stable ordering retains the catalogued version on an equal rank.
        candidates = list(dict.fromkeys([*existing, source]))
        preferred = min(candidates, key=cls.rank)
        discarded = [path for path in candidates if path != preferred
                     and Path(path).suffix.lower() != Path(preferred).suffix.lower()]
        return preferred, discarded
