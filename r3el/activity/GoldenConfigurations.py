"""Format value changes captured in golden configuration decision events."""

import re

from ax3l.app.snakelab.PairParameters import PAIR_PARAMETERS
from ax3l.constants.DLabel import FIELD_TO_LABEL_MAP


def parameter_change(decision: str | None, parameter: str | None = None) -> str:
    """Show recorded changes, ordering known pairs to match their display label."""
    number = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    changes = re.findall(
        rf"(?:^|; )([\w.]+): ({number}) -> ({number})(?=; |\.$|$)",
        decision or "",
    )
    if len(changes) == 1:
        _, before, after = changes[0]
        return f"{before} > {after}"
    if parameter in PAIR_PARAMETERS:
        paths = [".".join(path) for path in PAIR_PARAMETERS[parameter]]
        by_path = {name: (before, after) for name, before, after in changes}
        if len(changes) == len(paths) and set(by_path) == set(paths):
            return ", ".join(f"{by_path[path][0]} > {by_path[path][1]}" for path in paths)
    return "; ".join(
        f"{FIELD_TO_LABEL_MAP.get(name, name)}: {before} > {after}"
        for name, before, after in changes
    )
