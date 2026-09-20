from ax3l.app.Prompt import Prompt


class FirstContact(Prompt):
    def __init__(self):
        super().__init__(
            "This experiment is an implementation of Patrick Loeber's Famous "
            "AI Snake Game. You are responsible for choosing values that will achieve "
            "the best possible high score. Sometimes your available choices all "
            "look bad. You can still gather important data by running simulations "
            "in these ranges. You may also discover a new higher plateau!"
        )
