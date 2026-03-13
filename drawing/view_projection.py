import math
from typing import Dict, Iterable, List, Tuple

import numpy as np

from cadlib.curves import Arc, Circle, Line
from cadlib.extrude import CADSequence
from drawing.drawing_types import Entity2D, View2D

try:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCC.Core.HLRAlgo import HLRAlgo_Projector
    from OCC.Core.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
except Exception:  # pragma: no cover
    HLRBRep_Algo = None


def _iter_edges(shape) -> Iterable:
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        yield exp.Current()
        exp.Next()


def _edge_to_entity(edge, layer: str) -> Entity2D:
    curve = BRepAdaptor_Curve(edge)
    first = curve.FirstParameter()
    last = curve.LastParameter()
    ctype = curve.GetType()

    if ctype == GeomAbs_Line:
        p0 = curve.Value(first)
        p1 = curve.Value(last)
        return Entity2D(
            kind='line',
            layer=layer,
            data={'start': (float(p0.X()), float(p0.Y())), 'end': (float(p1.X()), float(p1.Y()))},
        )

    if ctype == GeomAbs_Circle:
        circle = curve.Circle()
        center = circle.Location()
        radius = float(circle.Radius())
        if abs(last - first) >= 2 * math.pi - 1e-6:
            return Entity2D(
                kind='circle',
                layer=layer,
                data={'center': (float(center.X()), float(center.Y())), 'radius': radius},
            )

        p0 = curve.Value(first)
        p1 = curve.Value(last)
        return Entity2D(
            kind='arc',
            layer=layer,
            data={
                'center': (float(center.X()), float(center.Y())),
                'radius': radius,
                'start': (float(p0.X()), float(p0.Y())),
                'end': (float(p1.X()), float(p1.Y())),
            },
        )

    p0 = curve.Value(first)
    p1 = curve.Value(last)
    return Entity2D(
        kind='line',
        layer=layer,
        data={'start': (float(p0.X()), float(p0.Y())), 'end': (float(p1.X()), float(p1.Y()))},
    )


def project_views(shape, view_directions: Dict[str, Tuple[float, float, float]]) -> List[View2D]:
    'Project 3D shape to multiple 2D orthographic views with HLR.'
    if HLRBRep_Algo is None:
        raise RuntimeError('pythonocc HLR modules are unavailable. Please install pythonocc-core.')

    views = []
    for view_name, direction in view_directions.items():
        algo = HLRBRep_Algo()
        algo.Add(shape)
        projector = HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*direction)))
        algo.Projector(projector)
        algo.Update()
        algo.Hide()

        to_shape = HLRBRep_HLRToShape(algo)
        visible_shape = to_shape.VCompound()
        hidden_shape = to_shape.HCompound()

        visible_entities = []
        hidden_entities = []

        if not visible_shape.IsNull():
            for edge in _iter_edges(visible_shape):
                visible_entities.append(_edge_to_entity(edge, 'VIEW_VISIBLE'))

        if not hidden_shape.IsNull():
            for edge in _iter_edges(hidden_shape):
                hidden_entities.append(_edge_to_entity(edge, 'VIEW_HIDDEN'))

        views.append(View2D(name=view_name, entities=visible_entities, hidden_entities=hidden_entities))

    return views


def default_view_directions() -> Dict[str, Tuple[float, float, float]]:
    return {
        'front': (0.0, 1.0, 0.0),
        'top': (0.0, 0.0, -1.0),
        'left': (-1.0, 0.0, 0.0),
    }


def _project_point(point3d: np.ndarray, direction: Tuple[float, float, float]) -> Tuple[float, float]:
    dx, dy, dz = direction
    if abs(dz) >= abs(dx) and abs(dz) >= abs(dy):
        return float(point3d[0]), float(point3d[1])
    if abs(dy) >= abs(dx):
        return float(point3d[0]), float(point3d[2])
    return float(point3d[1]), float(point3d[2])


def _local_to_global(ext, point2d: np.ndarray) -> np.ndarray:
    return point2d[0] * ext.sketch_plane.x_axis + point2d[1] * ext.sketch_plane.y_axis + ext.sketch_pos


def project_views_from_cad_sequence(
    cad_seq: CADSequence, view_directions: Dict[str, Tuple[float, float, float]]
) -> List[View2D]:
    """Fallback projection path without OCC hidden-line support."""
    views = [View2D(name=name, entities=[], hidden_entities=[]) for name in view_directions.keys()]
    view_map = {v.name: v for v in views}

    for ext in cad_seq.seq:
        profile = ext.profile
        profile.denormalize(ext.sketch_size)
        for loop in profile.children:
            for curve in loop.children:
                for view_name, direction in view_directions.items():
                    target = view_map[view_name]
                    if isinstance(curve, Line):
                        s = _project_point(_local_to_global(ext, curve.start_point), direction)
                        e = _project_point(_local_to_global(ext, curve.end_point), direction)
                        target.entities.append(Entity2D("line", "VIEW_VISIBLE", {"start": s, "end": e}))
                    elif isinstance(curve, Circle):
                        c3 = _local_to_global(ext, curve.center)
                        c2 = _project_point(c3, direction)
                        target.entities.append(
                            Entity2D("circle", "VIEW_VISIBLE", {"center": c2, "radius": float(curve.radius)})
                        )
                    elif isinstance(curve, Arc):
                        c2 = _project_point(_local_to_global(ext, curve.center), direction)
                        s2 = _project_point(_local_to_global(ext, curve.start_point), direction)
                        e2 = _project_point(_local_to_global(ext, curve.end_point), direction)
                        target.entities.append(
                            Entity2D(
                                "arc",
                                "VIEW_VISIBLE",
                                {"center": c2, "radius": float(curve.radius), "start": s2, "end": e2},
                            )
                        )
    return views
