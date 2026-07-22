"""
Run this once (or whenever you add/change models) to create tables in Postgres
based on the SQLAlchemy models. Equivalent to running CREATE TABLE by hand.
"""
from db.database import engine, Base
from db import emp_model  #  (import so Base knows about EmployeeModel)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created (or already existed).")