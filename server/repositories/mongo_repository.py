from typing import Optional

from pymongo import MongoClient, ReturnDocument # type: ignore

from repositories.base import EmployeeRepository, EmployeeRecord

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "employee_db"


class MongoEmployeeRepository(EmployeeRepository):
    def __init__(self, client: Optional[MongoClient] = None):
        # Accepting an optional client lets us inject a fake one (mongomock)
        # for testing, while defaulting to a real connection otherwise.
        self._client = client or MongoClient(MONGO_URL)
        self._db = self._client[DB_NAME]
        self._employees = self._db["employees"]
        self._counters = self._db["counters"]

    def _next_id(self) -> int:
        """
        MongoDB's native _id is an ObjectId, not an int - but our gRPC
        contract (int32 id) needs real integers to match the Postgres
        behavior. This mimics Postgres's SERIAL by keeping a single counter
        document and atomically incrementing it with find_one_and_update.
        $inc + find_one_and_update is atomic at the database level, so this
        is safe even under concurrent requests - no race condition, no
        two employees ever getting the same id.
        """
        counter = self._counters.find_one_and_update(
            {"_id": "employee_id"},
            {"$inc": {"seq": 1}},
            upsert=True,  # create the counter doc on first-ever call
            return_document=ReturnDocument.AFTER,
        )
        return counter["seq"]

    def _to_record(self, doc: dict) -> EmployeeRecord:
        return {
            "id": doc["_id"],
            "name": doc["name"],
            "department": doc["department"],
            "salary": doc["salary"],
        }

    def create(self, name: str, department: str, salary: float) -> EmployeeRecord:
        employee_id = self._next_id()
        doc = {
            "_id": employee_id,  # we set _id ourselves - an int, not the default ObjectId
            "name": name,
            "department": department,
            "salary": salary,
        }
        self._employees.insert_one(doc)
        return self._to_record(doc)

    def get(self, employee_id: int) -> Optional[EmployeeRecord]:
        doc = self._employees.find_one({"_id": employee_id})
        return self._to_record(doc) if doc else None

    def update(
        self,
        employee_id: int,
        name: Optional[str] = None,
        department: Optional[str] = None,
        salary: Optional[float] = None,
    ) -> Optional[EmployeeRecord]:
        # Build $set with only the fields that were actually passed - a key
        # simply absent from $set is left completely untouched by MongoDB,
        # which is exactly the "don't change what wasn't sent" behavior.
        fields_to_set = {}
        if name is not None:
            fields_to_set["name"] = name
        if department is not None:
            fields_to_set["department"] = department
        if salary is not None:
            fields_to_set["salary"] = salary
 
        if not fields_to_set:
            # Nothing to change - just return the current document as-is,
            # but still confirm it exists (None if it doesn't).
            doc = self._employees.find_one({"_id": employee_id})
            return self._to_record(doc) if doc else None
 
        doc = self._employees.find_one_and_update(
            {"_id": employee_id},
            {"$set": fields_to_set},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_record(doc) if doc else None

    def delete(self, employee_id: int) -> bool:
        result = self._employees.delete_one({"_id": employee_id})
        return result.deleted_count > 0