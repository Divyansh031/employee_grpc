from sqlalchemy import create_engine # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base # type: ignore

# Connection string format: postgresql://<user>:<password>@<host>:<port>/<database>
# This must match whatever you set in docker-compose.yml
DATABASE_URL = "postgresql://employee_app:employee_pass@localhost:5432/employee_db"

# The engine manages a pool of actual DB-API connections underneath.
# echo=True prints every SQL statement SQLAlchemy runs - great for learning,
# turn it off (or set to False) once you've seen enough.
engine = create_engine(DATABASE_URL, echo=True)

# A session is a "workspace" for a unit of work: you load/create objects in
# it, and commit() flushes changes as SQL. sessionmaker gives us a factory
# to create new sessions on demand (we'll make one per request).
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Base is the parent class every ORM model inherits from. SQLAlchemy uses it
# to collect metadata (table names, columns) from all your model classes.
Base = declarative_base()