"""Diagrama SVG de la selección bibliográfica, generado desde los archivos."""

from __future__ import annotations


def _box(x: int, y: int, w: int, h: int, fill: str, value: str,
         label: str, value_size: int = 31) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="13" fill="{fill}" stroke="#87cecb" stroke-opacity=".48"/>'
            f'<text x="{x+15}" y="{y+42}" fill="white" font-family="Segoe UI,Arial,sans-serif" font-size="{value_size}" font-weight="700">{value}</text>'
            f'<text x="{x+15}" y="{y+69}" fill="#d7f1ee" font-family="Segoe UI,Arial,sans-serif" font-size="12">{label}</text>')


def flow_svg(summary: dict[str, object], narrow: bool = False) -> str:
    scopus, wos = summary["scopus"], summary["wos"]
    reunited, pairs = summary["unified_rows"], summary["pairs_fused"]
    deduplicated, removed, final = (summary["deduplicated_rows"],
                                    summary["screened_out"], summary["final_rows"])
    head = ('<defs><linearGradient id="bg"><stop stop-color="#102d43"/><stop offset="1" stop-color="#124c54"/></linearGradient>'
            '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#92d6d4"/></marker></defs>')
    if narrow:
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 620" role="img" aria-label="Ruta de selección de registros">', head,
                 '<rect width="360" height="620" rx="19" fill="url(#bg)"/>',
                 '<text x="20" y="29" fill="#a9dcda" font-family="Segoe UI,Arial,sans-serif" font-size="12" font-weight="700" letter-spacing="1.5">RUTA DE LOS REGISTROS</text>',
                 _box(18, 49, 150, 77, '#8b482f', str(scopus), 'Scopus', 25),
                 _box(192, 49, 150, 77, '#2b5480', str(wos), 'Web of Science', 25)]
        stages = [("registros reunidos", reunited, '#1c6e76'),
                  ("duplicados retirados", f'−{pairs}', '#214c60'),
                  ("tras deduplicación", deduplicated, '#295b70'),
                  ("fuera del tema térmico mamario", f'−{removed}', '#70534c'),
                  ("artículos del dataset final", final, '#188d83')]
        for index, (label, value, fill) in enumerate(stages):
            y = 151 + index * 90
            parts.append(f'<path d="M180 {y-22} V{y-7}" stroke="#92d6d4" stroke-width="3" marker-end="url(#arrow)"/>')
            parts.append(_box(39, y, 282, 76, fill, str(value), label, 29))
        parts.append('<text x="19" y="610" fill="#b6d5d4" font-family="Segoe UI,Arial,sans-serif" font-size="10">Selección textual; revisar elegibilidad en el texto completo.</text></svg>')
        return ''.join(parts)

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1190 239" role="img" aria-label="Ruta de selección de registros">', head,
             '<rect width="1190" height="239" rx="21" fill="url(#bg)"/>',
             '<text x="23" y="29" fill="#a9dcda" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.8">RUTA DE LOS REGISTROS</text>',
             _box(20, 47, 143, 69, '#8b482f', str(scopus), 'Scopus', 25),
             _box(20, 126, 143, 69, '#2b5480', str(wos), 'Web of Science', 25),
             '<path d="M164 83 H179 Q188 83 188 101 V120 H201 M164 162 H179 Q188 162 188 144 V120" fill="none" stroke="#92d6d4" stroke-width="3" marker-end="url(#arrow)"/>']
    stages = [
        (216, str(reunited), 'reunidos', '#1c6e76'),
        (405, f'−{pairs}', 'duplicados', '#214c60'),
        (594, str(deduplicated), 'sin duplicados', '#295b70'),
        (783, f'−{removed}', 'fuera del tema', '#70534c'),
        (972, str(final), 'dataset final', '#188d83'),
    ]
    for index, (x, value, label, fill) in enumerate(stages):
        parts.append(_box(x, 76, 169, 99, fill, value, label, 34))
        if index < len(stages) - 1:
            parts.append(f'<path d="M{x+169} 125 H{x+187}" stroke="#92d6d4" stroke-width="3" marker-end="url(#arrow)"/>')
    parts.append('<text x="23" y="220" fill="#b6d5d4" font-family="Segoe UI,Arial,sans-serif" font-size="11">Se conserva termografía o imagen térmica/infrarroja de mama. Elegibilidad sujeta a revisión del texto completo.</text></svg>')
    return ''.join(parts)
