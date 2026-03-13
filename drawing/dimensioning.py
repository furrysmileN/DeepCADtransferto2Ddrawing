import math
from typing import Dict, List

import numpy as np

from cadlib.curves import Arc, Circle, Line
from cadlib.extrude import CADSequence
from drawing.drawing_types import Dimension2D, View2D


def _fmt(value: float, unit: str) -> str:
    return f'{value:.3f}{unit}'


def _project_point(pt3: np.ndarray, direction):
    dx, dy, dz = direction
    if abs(dz) > 0.9:
        return float(pt3[0]), float(pt3[1])
    if abs(dy) > 0.9:
        return float(pt3[0]), float(pt3[2])
    return float(pt3[1]), float(pt3[2])


def _curve_dimensions(curve, unit: str) -> List[Dimension2D]:
    dims = []
    if isinstance(curve, Line):
        length = float(np.linalg.norm(curve.end_point - curve.start_point))
        dims.append(
            Dimension2D(
                kind='linear',
                layer='DIM',
                value=length,
                text=_fmt(length, unit),
                data={'start': tuple(curve.start_point.tolist()), 'end': tuple(curve.end_point.tolist()), 'offset': 8.0},
            )
        )
    elif isinstance(curve, Circle):
        radius = float(curve.radius)
        dims.append(
            Dimension2D(
                kind='diameter',
                layer='DIM',
                value=2.0 * radius,
                text='D' + _fmt(2.0 * radius, unit),
                data={'center': tuple(curve.center.tolist()), 'radius': radius},
            )
        )
    elif isinstance(curve, Arc):
        radius = float(curve.radius)
        angle = abs(float(curve.end_angle - curve.start_angle)) * 180.0 / math.pi
        dims.append(
            Dimension2D(
                kind='radius',
                layer='DIM',
                value=radius,
                text='R' + _fmt(radius, unit),
                data={'center': tuple(curve.center.tolist()), 'radius': radius},
            )
        )
        dims.append(
            Dimension2D(
                kind='angle',
                layer='DIM',
                value=angle,
                text=f'{angle:.2f}deg',
                data={'start': tuple(curve.start_point.tolist()), 'vertex': tuple(curve.center.tolist()), 'end': tuple(curve.end_point.tolist())},
            )
        )
    return dims


def build_dimensions(cad_seq: CADSequence, views: List[View2D], view_directions: Dict[str, tuple], unit: str = 'mm') -> List[Dimension2D]:
    dimensions: List[Dimension2D] = []

    for ext in cad_seq.seq:
        profile = ext.profile
        profile.denormalize(ext.sketch_size)

        for loop in profile.children:
            for curve in loop.children:
                dimensions.extend(_curve_dimensions(curve, unit))

        ext_depth = float(abs(ext.extent_one))
        dimensions.append(
            Dimension2D(
                kind='extrude_depth',
                layer='DIM',
                value=ext_depth,
                text='DEPTH ' + _fmt(ext_depth, unit),
                data={'origin': tuple(ext.sketch_pos.tolist()), 'normal': tuple(ext.sketch_plane.normal.tolist())},
            )
        )

    return dimensions
