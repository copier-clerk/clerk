"""Order model — T003, T004, T005."""

from dataclasses import asdict, dataclass, field


@dataclass
class OrderItem:
    product_id: str
    quantity: int
    unit_price: float

    def to_dict(self):
        return asdict(self)


@dataclass
class Order:
    id: str
    user_id: str
    items: list[OrderItem] = field(default_factory=list)

    def to_dict(self):
        d = {"id": self.id, "user_id": self.user_id, "items": [i.to_dict() for i in self.items]}
        return d
