import argparse
import glob
import json
import os
import sys
from typing import List

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cadlib.extrude import CADSequence
from drawing.annotations import build_annotations, load_annotation_config
from drawing.dimensioning import build_dimensions
from drawing.output_dxf import export_to_dxf
from drawing.output_svg import export_to_svg
from drawing.drawing_types import SheetLayout
from drawing.view_projection import default_view_directions, project_views, project_views_from_cad_sequence


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


def _load_vec_from_h5(path: str) -> np.ndarray:
    import h5py

    with h5py.File(path, "r") as fp:
        if "out_vec" in fp:
            return fp["out_vec"][:].astype(float)
        if "vec" in fp:
            return fp["vec"][:].astype(float)
        raise KeyError("h5 file must contain `out_vec` or `vec` dataset")


def _load_cad(path: str, src_format: str):
    if src_format == "h5":
        vec = _load_vec_from_h5(path)
        cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
        shape = None
        try:
            from cadlib.visualize import vec2CADsolid

            shape = vec2CADsolid(vec, is_numerical=True, n=256)
        except Exception:
            # OCC is optional here; fallback path still exports 2D drawings.
            shape = None
        return cad_seq, shape

    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    cad_seq = CADSequence.from_dict(data)
    cad_seq.normalize()
    shape = None
    try:
        from cadlib.visualize import create_CAD

        shape = create_CAD(cad_seq)
    except Exception:
        shape = None
    return cad_seq, shape


def _build_demo_cad():
    pad = -1
    n_args = 16
    rows = []
    rows.append([4] + [pad] * n_args)  # SOL
    rows.append([0, 156, 100] + [pad] * (n_args - 2))
    rows.append([0, 156, 156] + [pad] * (n_args - 2))
    rows.append([0, 100, 156] + [pad] * (n_args - 2))
    rows.append([0, 100, 100] + [pad] * (n_args - 2))
    rows.append([5] + [pad] * 5 + [128, 128, 128, 128, 128, 128, 128, 192, 128, 0, 0])  # EXT
    rows.append([3] + [pad] * n_args)  # EOS
    vec = np.array(rows, dtype=float)
    cad_seq = CADSequence.from_vector(vec, is_numerical=True, n=256)
    return cad_seq, None, "demo_block"


def _entity_points(ent):
    if ent.kind == "line":
        return [ent.data["start"], ent.data["end"]]
    if ent.kind == "circle":
        cx, cy = ent.data["center"]
        r = ent.data["radius"]
        return [(cx - r, cy - r), (cx + r, cy + r)]
    if ent.kind == "arc":
        cx, cy = ent.data["center"]
        r = ent.data["radius"]
        return [(cx - r, cy - r), (cx + r, cy + r), ent.data["start"], ent.data["end"]]
    return []


def _view_bbox(view):
    pts = []
    for ent in view.entities + view.hidden_entities:
        pts.extend(_entity_points(ent))
    if not pts:
        return 0.0, 0.0, 1.0, 1.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _shift_entity(ent, dx: float, dy: float):
    if ent.kind == "line":
        x1, y1 = ent.data["start"]
        x2, y2 = ent.data["end"]
        ent.data["start"] = (x1 + dx, y1 + dy)
        ent.data["end"] = (x2 + dx, y2 + dy)
    elif ent.kind == "circle":
        cx, cy = ent.data["center"]
        ent.data["center"] = (cx + dx, cy + dy)
    elif ent.kind == "arc":
        cx, cy = ent.data["center"]
        sx, sy = ent.data["start"]
        ex, ey = ent.data["end"]
        ent.data["center"] = (cx + dx, cy + dy)
        ent.data["start"] = (sx + dx, sy + dy)
        ent.data["end"] = (ex + dx, ey + dy)


def _layout_views(views, sheet_width: float, sheet_height: float):
    margin = 20.0
    cell_w = (sheet_width - margin * 2) / 3.0
    baseline = sheet_height * 0.55
    for idx, view in enumerate(views):
        minx, miny, maxx, maxy = _view_bbox(view)
        vw = max(maxx - minx, 1e-6)
        vh = max(maxy - miny, 1e-6)
        target_x = margin + cell_w * idx + cell_w * 0.5
        target_y = baseline
        dx = target_x - (minx + vw * 0.5)
        dy = target_y - (miny + vh * 0.5)
        for ent in view.entities:
            _shift_entity(ent, dx, dy)
        for ent in view.hidden_entities:
            _shift_entity(ent, dx, dy)
        view.origin = (target_x, target_y)


def _collect_paths(src: str, src_format: str) -> List[str]:
    if os.path.isdir(src):
        return sorted(glob.glob(os.path.join(src, f"*.{src_format}")))
    return [src]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=str, default=None, help="source folder or single file")
    parser.add_argument("--src_format", type=str, default="h5", choices=["h5", "json"])
    parser.add_argument("-o", "--output", type=str, required=True, help="output folder")
    parser.add_argument("--format", type=str, default="dxf", choices=["dxf", "svg", "both"])
    parser.add_argument("--annotation_config", type=str, default=None, help="path to JSON config file")
    parser.add_argument("--unit", type=str, default="mm", help="dimension unit text")
    parser.add_argument("--demo", action="store_true", help="run built-in sample without external dependencies")
    args = parser.parse_args()

    ensure_dir(args.output)
    if not args.demo and not args.src:
        raise ValueError("--src is required unless --demo is enabled")

    in_paths = [] if args.demo else _collect_paths(args.src, args.src_format)
    ann_config = load_annotation_config(args.annotation_config)
    sheet = ann_config.get("sheet", {})
    sheet_width = float(sheet.get("width", 420.0))
    sheet_height = float(sheet.get("height", 297.0))

    if args.demo:
        in_paths = ["__demo__"]

    for path in in_paths:
        try:
            if args.demo:
                cad_seq, shape, name = _build_demo_cad()
            else:
                cad_seq, shape = _load_cad(path, args.src_format)
                name = os.path.splitext(os.path.basename(path))[0]
            directions = default_view_directions()
            if shape is not None:
                try:
                    views = project_views(shape, directions)
                except Exception:
                    views = project_views_from_cad_sequence(cad_seq, directions)
            else:
                views = project_views_from_cad_sequence(cad_seq, directions)
            _layout_views(views, sheet_width, sheet_height)
            dims = build_dimensions(cad_seq, views, directions, unit=args.unit)
            anns = build_annotations(ann_config)
        except Exception as exc:
            print("failed:", path, exc)
            continue

        layout = SheetLayout(
            width=sheet_width,
            height=sheet_height,
            views=views,
            dimensions=dims,
            annotations=anns,
        )
        if args.format in ("dxf", "both"):
            export_to_dxf(layout, os.path.join(args.output, name + ".dxf"))
        if args.format in ("svg", "both"):
            export_to_svg(layout, os.path.join(args.output, name + ".svg"))
        print("done:", path)


if __name__ == "__main__":
    main()
