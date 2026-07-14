"""Order repository — T008, T010."""

from models.order import Order


class OrderRepository:
    def __init__(self):
        self._store: dict[str, Order] = {}

    def find_by_user(self, user_id: str) -> list[Order]:
        return [o for o in self._store.values() if o.user_id == user_id]

    def save(self, order: Order) -> None:
        self._store[order.id] = order

    def delete(self, id: str) -> None:
        self._store.pop(id, None)
