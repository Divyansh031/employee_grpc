"""
The repository interface - the contract any storage backend must fulfill.

The servicer (server.py) will only ever talk to this interface, never to
SQLAlchemy or pymongo directly. That's the whole point: swapping Postgres
for MongoDB (or anything else) later means writing a new class that follows
this shape - zero changes needed in the gRPC-facing code.

Each method works with plain Python values in, and a dict-like record out
(or None if not found) - NOT ORM objects, NOT MongoDB documents. This keeps
the interface itself database-agnostic.
"""
from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class EmployeeRecord(TypedDict):
    id: int
    name: str
    department: str
    salary: float


class EmployeeRepository(ABC):
    @abstractmethod
    def create(self, name: str, department: str, salary: float) -> EmployeeRecord:
        ...

    @abstractmethod
    def get(self, employee_id: int) -> Optional[EmployeeRecord]:
        ...

    @abstractmethod
    def update(
        self, employee_id: int, name: str, department: str, salary: float
    ) -> Optional[EmployeeRecord]:
        """Returns None if no employee with this id exists."""
        ...

    @abstractmethod
    def delete(self, employee_id: int) -> bool:
        """Returns True if an employee was deleted, False if it didn't exist."""
        ...