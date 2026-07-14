"""User repository — T006, T010."""

from models.user import User


class UserRepository:
    def __init__(self):
        self._store: dict[str, User] = {}

    def find_by_id(self, id: str) -> User | None:
        return self._store.get(id)

    def save(self, user: User) -> None:
        self._store[user.id] = user

    def delete(self, id: str) -> None:
        self._store.pop(id, None)
