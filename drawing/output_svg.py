from drawing.drawing_types import SheetLayout


def export_to_svg(layout: SheetLayout, output_path: str):
    width, height = layout.width, layout.height
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">',
        '<g fill="none" stroke="#111" stroke-width="0.35">',
    ]

    for view in layout.views:
        for ent in view.entities:
            if ent.kind == "line":
                x1, y1 = ent.data["start"]
                x2, y2 = ent.data["end"]
                rows.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />')
            elif ent.kind == "circle":
                cx, cy = ent.data["center"]
                r = ent.data["radius"]
                rows.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" />')

    rows.append("</g>")

    for ann in layout.annotations:
        x, y = ann.position
        rows.append(f'<text x="{x}" y="{y}" font-size="{ann.height}">{ann.text}</text>')

    rows.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))
