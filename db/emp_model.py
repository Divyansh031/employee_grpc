from sqlalchemy import Column, Integer, String, Numeric # type: ignore

from db.database import Base


class EmployeeModel(Base):
    """
    This class maps to a 'employees' table in Postgres.
    Each attribute becomes a column. This is a DIFFERENT class from
    employee_pb2.Employee - that one is the gRPC wire message, this one is
    the DB row. We translate between the two in server.py. Keeping them
    separate is intentional: your DB schema and your API contract are
    allowed to evolve independently.
    """

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    salary = Column(Numeric, nullable=False)