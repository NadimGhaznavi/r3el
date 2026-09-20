"""Plot the accepted config's score, preserving seed baseline decreases."""

from html import escape

import plotly.graph_objects as go


def highscores(history: list[dict], total: int) -> dict:
    if not history:
        return {"chart": None, "total": total}
    x = [row["simulations"] for row in history]
    y = [row["score"] for row in history]
    details = [[row["seed"], escape(row["run_id"]), escape(row["reason"])] for row in history]
    figure = go.Figure()
    # Continue the accepted score across unsuccessful and pending submissions.
    end = max(total, x[-1])
    figure.add_trace(go.Scatter(
        x=x + ([end] if end > x[-1] else []),
        y=y + ([y[-1]] if end > x[-1] else []),
        mode="lines", line=dict(shape="spline", color="#4c9be8", width=4),
        name="High score", hoverinfo="skip", showlegend=True,
    ))
    figure.add_trace(go.Scatter(
        x=x, y=y, customdata=details, mode="markers", marker=dict(color="#f09445", size=8),
        name="Accepted config", showlegend=True,
        hovertemplate="Simulations: %{x}<br>Score: %{y}<br>Seed: %{customdata[0]}"
                      "<br>Run: %{customdata[1]}<br>%{customdata[2]}<extra></extra>",
    ))
    figure.update_layout(
        template="plotly_dark", paper_bgcolor="#101720", plot_bgcolor="#151f2b",
        font=dict(family="Courier New, monospace", color="#d5dfeb"),
        xaxis_title="Number of simulations", yaxis_title="Current config high score",
        xaxis=dict(rangemode="tozero", dtick=1 if end < 20 else None),
        yaxis=dict(rangemode="tozero"),
        legend=dict(orientation="h", x=.5, xanchor="center", y=-.22, yanchor="top"),
        margin=dict(l=65, r=25, t=30, b=115),
    )
    return {"total": total, "chart": figure.to_html(
        full_html=False, include_plotlyjs=True, div_id="experiment-highscores", default_height="65vh",
        config={"responsive": True, "displaylogo": False},
    )}
