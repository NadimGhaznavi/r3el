"""Basic form validation at the external submission boundary."""

import unicodedata

from r3el.entity.Identification import Identification


class ValidateIdentification:
    def run(self, data: dict, *, series: bool = False) -> Identification:
        fields = {'title', 'confidence'} if series else {'title', 'year', 'confidence'}
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError('Supply exactly ' + ', '.join(sorted(fields)) + '.')
        title, year, confidence = data['title'], None if series else data['year'], data['confidence']
        if not isinstance(title, str) or len(title) > 255 or not title.strip():
            raise ValueError('title must be nonempty and at most 255 characters.')
        if any(unicodedata.category(char).startswith('C') for char in title):
            raise ValueError('title must not contain control or invisible formatting characters.')
        if not series and (type(year) is not int or not 1 <= year <= 9999):
            raise ValueError('year must be an integer between 1 and 9999.')
        if type(confidence) is not int or not 0 <= confidence <= 10:
            raise ValueError('confidence must be an integer between 0 and 10.')
        return Identification(title.strip(), year, confidence)
