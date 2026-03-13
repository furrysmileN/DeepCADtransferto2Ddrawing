from typing import Iterable, List

from drawing.drawing_types import Annotation2D, Dimension2D, Entity2D, SheetLayout


def _require_ezdxf():
    try:
        import ezdxf
    except Exception as exc:  # pragma: no cover
        raise RuntimeError('Please install ezdxf: pip install ezdxf') from exc
    return ezdxf


def _add_entity(msp, ent: Entity2D):
    if ent.kind == 'line':
        msp.add_line(ent.data['start'], ent.data['end'], dxfattribs={'layer': ent.layer})
    elif ent.kind == 'circle':
        msp.add_circle(ent.data['center'], ent.data['radius'], dxfattribs={'layer': ent.layer})
    elif ent.kind == 'arc':
        center = ent.data['center']
        radius = ent.data['radius']
        msp.add_circle(center, radius, dxfattribs={'layer': ent.layer})


def _add_dimension(msp, dim: Dimension2D):
    try:
        if dim.kind in ('linear', 'extrude_depth'):
            start = dim.data.get('start', (0.0, 0.0))
            end = dim.data.get('end', (10.0, 0.0))
            offset = float(dim.data.get('offset', 8.0))
            msp.add_aligned_dim(p1=start, p2=end, distance=offset, dimstyle='EZDXF')
        elif dim.kind in ('radius', 'diameter'):
            center = dim.data.get('center', (0.0, 0.0))
            radius = float(dim.data.get('radius', 1.0))
            mpoint = (center[0] + radius, center[1])
            msp.add_radius_dim(center=center, radius=radius, mpoint=mpoint)
        elif dim.kind == 'angle':
            pass  # skip angle dim in DXF for now
    except Exception:
        pass


def _add_text(msp, ann: Annotation2D):
    txt = msp.add_text(ann.text, dxfattribs={'height': ann.height, 'layer': ann.layer})
    txt.set_placement(ann.position)


def export_to_dxf(layout: SheetLayout, output_path: str):
    ezdxf = _require_ezdxf()

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    for layer in ['VIEW_VISIBLE', 'VIEW_HIDDEN', 'DIM', 'NOTE', 'TITLE', 'BORDER']:
        if layer not in doc.layers:
            doc.layers.new(layer)

    w, h = layout.width, layout.height
    msp.add_lwpolyline(
        [(layout.border_margin, layout.border_margin), (w - layout.border_margin, layout.border_margin),
         (w - layout.border_margin, h - layout.border_margin), (layout.border_margin, h - layout.border_margin),
         (layout.border_margin, layout.border_margin)],
        dxfattribs={'layer': 'BORDER'},
    )

    for view in layout.views:
        for ent in view.entities:
            _add_entity(msp, ent)
        for ent in view.hidden_entities:
            _add_entity(msp, ent)

    for dim in layout.dimensions:
        _add_dimension(msp, dim)

    for ann in layout.annotations:
        _add_text(msp, ann)

    doc.saveas(output_path)
