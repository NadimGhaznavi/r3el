"""Movie directory and filename rules from pages/file-naming.md."""

import re
import unicodedata


class MovieNaming:
    @staticmethod
    def title(title: str) -> str:
        title = unicodedata.normalize('NFKC', title)
        for old, new in {':': ' - ', '/': ' - ', '\\': ' - ', '#': '', '%': ' percent ',
                         '"': '', '*': '', '?': '', '<': '', '>': '', '|': '',
                         '’': "'", '‘': "'", '“': '', '”': ''}.items():
            title = title.replace(old, new)
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'\s*-\s*', ' - ', title).strip(' .-')
        if not title or any(ord(character) < 32 for character in title):
            raise ValueError('The movie title cannot form a valid filename.')
        return title

    @staticmethod
    def stem(title: str, year: int) -> str:
        return f'{MovieNaming.title(title)} ({year})'
