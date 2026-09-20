from ax3l.app.Prompt import Prompt


class ProjectContext(Prompt):
    def __init__(self):
        super().__init__(
            'This project implements Patrick Loeber\'s "Train an AI to Play Snake" '
            'tutorial. You are in charge of choosing parameters.'
        )
