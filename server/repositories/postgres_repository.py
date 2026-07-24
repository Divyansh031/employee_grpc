from typing import Optional

from db.database import SessionLocal
from db.emp_model import EmployeeModel
from repositories.base import EmployeeRepository, EmployeeRecord


def _to_record(db_employee: EmployeeModel) -> EmployeeRecord:
    return {
        "id": db_employee.id,
        "name": db_employee.name,
        "department": db_employee.department,
        "salary": float(db_employee.salary),
    }


class PostgresEmployeeRepository(EmployeeRepository):
    def create(self, name: str, department: str, salary: float) -> EmployeeRecord:
        session = SessionLocal()
        try:
            db_employee = EmployeeModel(name=name, department=department, salary=salary)
            session.add(db_employee)
            session.commit()
            session.refresh(db_employee)
            return _to_record(db_employee)
        finally:
            session.close()

    def get(self, employee_id: int) -> Optional[EmployeeRecord]:
        session = SessionLocal()
        try:
            db_employee = session.get(EmployeeModel, employee_id)
            return _to_record(db_employee) if db_employee else None
        finally:
            session.close()

    def update(
        self,
        employee_id: int,
        name: Optional[str] = None,
        department: Optional[str] = None,
        salary: Optional[float] = None,
    ) -> Optional[EmployeeRecord]:
        session = SessionLocal()
        try:
            db_employee = session.get(EmployeeModel, employee_id)
            if db_employee is None:
                return None
            # Only touch attributes that were actually passed - None means
            # "client didn't send this field, leave it as-is".
            if name is not None:
                db_employee.name = name
            if department is not None:
                db_employee.department = department
            if salary is not None:
                db_employee.salary = salary
            session.commit()
            session.refresh(db_employee)
            return _to_record(db_employee)
        finally:
            session.close()

    def delete(self, employee_id: int) -> bool:
        session = SessionLocal()
        try:
            db_employee = session.get(EmployeeModel, employee_id)
            if db_employee is None:
                return False
            session.delete(db_employee)
            session.commit()
            return True
        finally:
            session.close()