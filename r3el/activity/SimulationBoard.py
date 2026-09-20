"""Render a saved Snake Lab high-score snapshot as an SVG board."""

import json
from xml.etree.ElementTree import Element, SubElement, tostring


def board_svg(snapshot: str | dict | None) -> str | None:
    if snapshot is None:
        return None
    try:
        if isinstance(snapshot, (str, bytes)):
            snapshot = json.loads(snapshot)
        board = snapshot["board"]
        width, height = board["grid_size"]
        if any(type(n) is not int or n <= 0 for n in (width, height)):
            return None
        body = board["snake_body"]
        head = board["snake_head"]
        food = board["food"]
        for x, y in [head, *body, *([food] if food is not None else [])]:
            if type(x) is not int or type(y) is not int or not (0 <= x < width and 0 <= y < height):
                return None
    except (ValueError, TypeError, KeyError):
        return None

    cell = 32
    pixel_width, pixel_height = width * cell, height * cell
    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(pixel_width), "height": str(pixel_height),
        "viewBox": f"0 0 {pixel_width} {pixel_height}",
        "role": "img", "aria-label": "Saved high-score Snake Lab board",
        "class": "simulation-board",
    })

    def draw(tag, **attributes):
        return SubElement(svg, tag, {key: str(value) for key, value in attributes.items()})

    draw("rect", width="100%", height="100%", fill="#101720")
    for x in range(width + 1):
        draw("line", x1=x * cell, y1=0, x2=x * cell, y2=pixel_height, stroke="#23364b")
    for y in range(height + 1):
        draw("line", x1=0, y1=y * cell, x2=pixel_width, y2=y * cell, stroke="#23364b")
    for x, y in body:
        draw("rect", x=x * cell + 2, y=y * cell + 2, width=cell - 4,
             height=cell - 4, rx=5, fill="#4c9be8")
    x, y = head
    draw("rect", x=x * cell + 1, y=y * cell + 1, width=cell - 2,
         height=cell - 2, rx=6, fill="#79b8f3")
    if food is not None:
        x, y = food
        draw("circle", cx=x * cell + cell / 2, cy=y * cell + cell / 2,
             r=cell * .3, fill="#f09445")
    return tostring(svg, encoding="unicode")
