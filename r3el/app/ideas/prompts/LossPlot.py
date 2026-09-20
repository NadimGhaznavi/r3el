"""A dynamic PNG prompt showing one simulation's per-episode training loss."""

import base64
import json
from uuid import UUID

import plotly.graph_objects as go

from ax3l.app.DynamicPrompt import DynamicPrompt
from ax3l.constants.DLossPlot import DLossPlot
from ax3l.interface.SnakeLab import SnakeLab


class LossPlot(DynamicPrompt):
    """Use LossPlot(golden.run_id) to keep the image tied to that configuration.

    refresh() reloads the same run's losses and renders a new PNG in memory.
    to_json() includes the PNG as image content for the vision-capable LLM.
    """

    def __init__(self, run_id: str):
        UUID(run_id)
        self._run_id = run_id
        self._snake_lab = SnakeLab()
        super().__init__()

    def refresh(self) -> None:
        losses = self._snake_lab.get_episode_losses(self._run_id)
        if not any(loss is not None for _, loss in losses):
            raise ValueError(f"No training losses recorded for simulation {self._run_id}")

        figure = go.Figure(go.Scatter(
            x=[episode for episode, _ in losses],
            y=[loss for _, loss in losses],
            mode="lines", name="Loss", line=dict(width=2), connectgaps=False,
        ))
        figure.update_layout(
            title="Training Loss", xaxis_title="Episode", yaxis_title="Loss",
            template="plotly_dark", width=DLossPlot.WIDTH, height=DLossPlot.HEIGHT,
            margin=dict(l=80, r=40, t=80, b=70),
        )
        png = figure.to_image(format="png", scale=DLossPlot.SCALE)
        self._image_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        self._content = (
            f"Per-episode training loss for simulation {self._run_id}. "
            "Gaps indicate episodes without a recorded training loss."
        )

    def to_json(self) -> str:
        return json.dumps({
            "role": "user",
            "content": [
                {"type": "text", "text": self._content},
                {"type": "image_url", "image_url": {"url": self._image_url}},
            ],
        }, ensure_ascii=False)

    def to_md(self) -> str:
        return f"{self._content}\n\n![Training Loss]({self._image_url})"
