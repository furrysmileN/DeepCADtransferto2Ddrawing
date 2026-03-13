from dataclasses import dataclass, field
from typing import Dict, List, Tuple

Point2D = Tuple[float, float]


@dataclass
class Entity2D:
    kind: str
    layer: str
    data: Dict[str, object]


@dataclass
class View2D:
    name: str
    entities: List[Entity2D] = field(default_factory=list)
    hidden_entities: List[Entity2D] = field(default_factory=list)
    origin: Point2D = (0.0, 0.0)


@dataclass
class Dimension2D:
    kind: str
    layer: str
    value: float
    text: str
    data: Dict[str, object]


@dataclass
class Annotation2D:
    text: str
    layer: str
    position: Point2D
    height: float = 2.5
    rotation: float = 0.0


@dataclass
class SheetLayout:
    width: float
    height: float
    views: List[View2D]
    dimensions: List[Dimension2D]
    annotations: List[Annotation2D]
    border_margin: float = 10.0
