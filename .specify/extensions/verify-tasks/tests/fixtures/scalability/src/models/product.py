"""Product model — T002, T004, T005."""

from dataclasses import asdict, dataclass


@dataclass
class Product:
    id: str
    name: str
    price: float
    stock: int

    def to_dict(self):
        return asdict(self)
