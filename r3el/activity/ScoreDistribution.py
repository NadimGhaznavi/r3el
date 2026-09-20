"""Interactive score histogram with a shared bin definition for both cohorts."""

import math

import plotly.graph_objects as go


def distribution(scores: list[int | None]) -> dict:
    half = len(scores) // 2
    all_scores = [score for score in scores if score is not None]
    older_scores = [score for score in scores[:half] if score is not None]
    figure = go.Figure()
    if all_scores:
        low, high = min(all_scores), max(all_scores)
        size = max(1, math.ceil((high - low + 1) / 40))
        bins = dict(start=low - .5, end=high + .5, size=size)
        for name, values, color in (
            ("All runs", all_scores, "#4c9be8"),
            ("Oldest half", older_scores, "#f09445"),
        ):
            figure.add_trace(go.Histogram(
                x=values, name=name, xbins=bins, bingroup="scores",
                histfunc="count", marker_color=color, opacity=.85,
                marker_line=dict(color="#101923", width=4),
                hovertemplate="Score: %{x}<br>Runs: %{y}<extra>%{fullData.name}</extra>",
            ))
        figure.update_layout(
            barmode="overlay", bargap=.08, template="plotly_dark",
            paper_bgcolor="#101720", plot_bgcolor="#151f2b",
            font=dict(family="Courier New, monospace", color="#d5dfeb"),
            xaxis_title="Run high score", yaxis_title="Number of runs",
            yaxis=dict(rangemode="tozero", dtick=1 if len(all_scores) < 20 else None),
            legend=dict(orientation="h", x=.5, xanchor="center", y=-.22, yanchor="top"),
            margin=dict(l=65, r=25, t=30, b=115),
        )
    return dict(
        total=len(scores), half=half, scored=len(all_scores), older_scored=len(older_scores),
        chart=figure.to_html(full_html=False, include_plotlyjs=True,
                             div_id="score-histogram", default_height="65vh",
                             config={"responsive": True, "displaylogo": False}) if all_scores else None,
    )
