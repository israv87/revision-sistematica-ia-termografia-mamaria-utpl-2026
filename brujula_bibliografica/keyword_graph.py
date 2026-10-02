"""SVG de coocurrencia de palabras clave bibliográficas."""

from __future__ import annotations

import html
import math
import textwrap


def keyword_graph_svg(network: dict[str, object]) -> str:
    nodes: list[tuple[str, int]] = network["nodes"]
    edges: list[tuple[str, str, int]] = network["edges"]
    width, height = 1080, 650
    if not nodes:
        return ""

    positions = {nodes[0][0]: (width / 2, height / 2)}
    satellites = nodes[1:]
    for index, (term, _) in enumerate(satellites):
        angle = -math.pi / 2 + 2 * math.pi * index / max(len(satellites), 1)
        positions[term] = (width / 2 + 405 * math.cos(angle),
                           height / 2 + 246 * math.sin(angle))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Red de palabras clave que aparecen juntas en los artículos">',
             '<rect width="100%" height="100%" rx="22" fill="#102d3c"/>',
             '<g fill="none" stroke="#6bc9bd">']
    maximum = max((count for _, _, count in edges), default=1)
    for left, right, count in edges:
        x1, y1 = positions[left]
        x2, y2 = positions[right]
        thickness = 1.1 + 5.1 * count / maximum
        opacity = .18 + .47 * count / maximum
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke-width="{thickness:.1f}" opacity="{opacity:.2f}"/>')
    parts.append('</g>')

    for index, (term, count) in enumerate(nodes):
        x, y = positions[term]
        central = index == 0
        radius = 37 if central else 27
        color = "#ef9b62" if central else "#53baa9"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" opacity=".18"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius - 5}" fill="{color}"/>')
        parts.append(f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="14" font-weight="700" fill="#102d3c">{count}</text>')
        label_y = y + radius + 19
        label = textwrap.shorten(term, width=30, placeholder="…")
        lines = textwrap.wrap(label, width=20, break_long_words=False, break_on_hyphens=False)[:2]
        for line_no, line in enumerate(lines):
            parts.append(f'<text x="{x:.1f}" y="{label_y + line_no * 17:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="600" fill="#e9f7f5">{html.escape(line)}</text>')
    parts.append('</svg>')
    return "".join(parts)
