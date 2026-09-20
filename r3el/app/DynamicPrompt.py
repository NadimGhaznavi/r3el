from ax3l.app.Prompt import Prompt

class DynamicPrompt(Prompt):

    def __init__(self):
        super().__init__("")
        self.refresh()

    def refresh(self) -> None:
        raise NotImplementedError("Subclasses must implement this method")
