"""Shared display labels for report parameters."""

from typing import Final


class DLabel:
    # Pair labels follow the component order in PairParameters.PAIR_PARAMETERS.

    HIDDEN_SIZE: Final[str] = "Hidden Size"
    SEQUENCE_LENGTH: Final[str] = "Sequence Length"
    BATCH_SIZE: Final[str] = "Batch Size"
    LEARNING_RATE: Final[str] = "Learning Rate"
    GAMMA: Final[str] = "Gamma"
    EPSILON_PAIR: Final[str] = "Epsilon: initial, decay"
    EPSILON_INITIAL: Final[str] = "Epsilon: initial"
    EPSILON_DECAY: Final[str] = "Epsilon: decay"
    REWARD_PAIR: Final[str] = "Food Reward: closer, further"
    CLOSER_TO_FOOD: Final[str] = "Food Reward: closer"
    FURTHER_FROM_FOOD: Final[str] = "Food Reward: further"


FIELD_TO_LABEL_MAP: Final[dict[str, str]] = {
    "hidden_size": DLabel.HIDDEN_SIZE,
    "model.hidden_size": DLabel.HIDDEN_SIZE,
    "sequence_length": DLabel.SEQUENCE_LENGTH,
    "training.sequence_length": DLabel.SEQUENCE_LENGTH,
    "batch_size": DLabel.BATCH_SIZE,
    "training.batch_size": DLabel.BATCH_SIZE,
    "learning_rate": DLabel.LEARNING_RATE,
    "training.learning_rate": DLabel.LEARNING_RATE,
    "gamma": DLabel.GAMMA,
    "training.gamma": DLabel.GAMMA,
    "epsilon_pair": DLabel.EPSILON_PAIR,
    "epsilon.initial": DLabel.EPSILON_INITIAL,
    "epsilon.decay": DLabel.EPSILON_DECAY,
    "reward_pair": DLabel.REWARD_PAIR,
    "closer_to_food": DLabel.CLOSER_TO_FOOD,
    "game.rewards.closer_to_food": DLabel.CLOSER_TO_FOOD,
    "further_from_food": DLabel.FURTHER_FROM_FOOD,
    "game.rewards.further_from_food": DLabel.FURTHER_FROM_FOOD,
}
