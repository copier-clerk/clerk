"""User model — T001, T004, T005."""

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class User:
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self):
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d
