import json
from typing import Dict, List

from drawing.drawing_types import Annotation2D


def load_annotation_config(path: str = None) -> Dict[str, object]:
    if path is None:
        return {
            'sheet': {'size': 'A3', 'width': 420.0, 'height': 297.0},
            'title': 'DeepCAD Drawing',
            'notes': [
                'UNSPECIFIED FILLET: R0.5',
                'UNSPECIFIED CHAMFER: C0.5x45deg',
                'GENERAL TOLERANCE: GB/T 1804-m',
                'SURFACE ROUGHNESS: Ra3.2',
            ],
        }

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_annotations(config: Dict[str, object]) -> List[Annotation2D]:
    annotations: List[Annotation2D] = []

    title = str(config.get('title', 'DeepCAD Drawing'))
    annotations.append(Annotation2D(text=title, layer='TITLE', position=(20.0, 20.0), height=5.0))

    notes = config.get('notes', [])
    for idx, text in enumerate(notes):
        annotations.append(
            Annotation2D(
                text=str(text),
                layer='NOTE',
                position=(20.0, 35.0 + 6.0 * idx),
                height=2.5,
            )
        )

    scale = config.get('scale', '1:1')
    annotations.append(Annotation2D(text=f'SCALE: {scale}', layer='TITLE', position=(320.0, 275.0), height=2.5))

    drawing_no = config.get('drawing_no', 'DC-0001')
    annotations.append(Annotation2D(text=f'DWG NO: {drawing_no}', layer='TITLE', position=(320.0, 282.0), height=2.5))

    return annotations
