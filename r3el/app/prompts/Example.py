"""Demonstrate a multiple-choice tool submission with structured example data."""

from r3el.app.Prompt import Prompt


class Example(Prompt):
    def __init__(self) -> None:
        super().__init__(
            'Here is an example.',
            data={'examples': [{
                'query': {'title': 'Batman', 'year': 2022},
                'candidates': [
                    {'number': 1, 'title': 'Batman: The Audio Adventures'},
                    {'number': 2, 'title': 'The Batman',
                     'overview': 'Two years of stalking the streets...'},
                ],
                'output': {'name': 'submit_multiple_choice', 'arguments': {'number': 2}},
            }]},
        )

    @property
    def source_name(self) -> str:
        return 'example'
