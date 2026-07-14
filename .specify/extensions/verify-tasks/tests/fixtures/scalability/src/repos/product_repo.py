"""Product repository — T007, T010."""

from models.product import Product


class ProductRepository:
    def __init__(self):
        self._store: dict[str, Product] = {}

    def find_by_id(self, id: str) -> Product | None:
        return self._store.get(id)

    def find_all(self) -> list[Product]:
        return list(self._store.values())

    def save(self, product: Product) -> None:
        self._store[product.id] = product

    def delete(self, id: str) -> None:
        self._store.pop(id, None)
