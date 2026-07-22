# Employee gRPC Service (Learning Project)

A gRPC CRUD service in Python, built to learn gRPC concepts hands-on. This started as an
**in-memory** service (a Python dict, no database) to keep the focus purely on gRPC mechanics,
and was later extended with a **PostgreSQL** persistence layer, **Docker**, **server
reflection**, and **Postman** testing. This document covers both stages — what we started with,
and what changed and why.

---

## 1. What is gRPC, in short

gRPC is a framework for calling functions on a remote server as if they were local functions.

- You define a **contract** (`.proto` file) describing your data (`messages`) and your remote
  functions (`service` + `rpc` methods).
- A compiler (`protoc`) generates code in your language of choice from that contract — both
  message classes and client/server networking code.
- Under the hood, gRPC runs over **HTTP/2** and encodes data as **Protocol Buffers** (a compact
  binary format), not JSON. This makes it faster and smaller on the wire than typical REST/JSON,
  at the cost of the payload no longer being human-readable without the schema.
- Compare to REST: instead of designing URLs (`POST /employees`) and loosely-typed JSON bodies,
  you get strongly-typed request/response objects and real method names (`CreateEmployee(...)`),
  checked at compile time in the client and server code.

---

## 2. Project structure (original, in-memory version)

```
employee-grpc/
├──.venv/
├── proto/
│   └── employee.proto          ← the contract: messages + service definition
├── server/
│   ├── employee_pb2.py         ← generated: message classes
│   ├── employee_pb2_grpc.py    ← generated: servicer base class + client stub
│   └── server.py                ← our server implementation (in-memory CRUD)
├── client/
│   ├── employee_pb2.py         ← generated (copy of the same file)
│   ├── employee_pb2_grpc.py    ← generated (copy of the same file)
│   └── client.py                ← simple hardcoded-values client, exercises full CRUD
│     
└── data-flow-diagram.svg    ← diagram of a request/response round trip
```

> The generated `employee_pb2*.py` files are duplicated in `server/` and `client/` here for
> simplicity. In a larger project you'd typically generate them once into a shared package that
> both sides import, or generate them independently in each service's own build step.

---

## 3. The `.proto` file — the contract

```protobuf
syntax = "proto3";
package employee;

message Employee {
  int32 id = 1;
  string name = 2;
  string department = 3;
  double salary = 4;
}

message CreateEmployeeRequest { string name = 1; string department = 2; double salary = 3; }
message CreateEmployeeResponse { Employee employee = 1; }

message GetEmployeeRequest { int32 id = 1; }
message GetEmployeeResponse { Employee employee = 1; }

message UpdateEmployeeRequest { int32 id = 1; string name = 2; string department = 3; double salary = 4; }
message UpdateEmployeeResponse { Employee employee = 1; }

message DeleteEmployeeRequest { int32 id = 1; }
message DeleteEmployeeResponse { bool success = 1; }

service EmployeeService {
  rpc CreateEmployee(CreateEmployeeRequest) returns (CreateEmployeeResponse);
  rpc GetEmployee(GetEmployeeRequest) returns (GetEmployeeResponse);
  rpc UpdateEmployee(UpdateEmployeeRequest) returns (UpdateEmployeeResponse);
  rpc DeleteEmployee(DeleteEmployeeRequest) returns (DeleteEmployeeResponse);
}
```

Key points:

- **Field numbers** (`= 1`, `= 2`, ...) are not default values — they identify each field in the
  binary wire encoding. They must stay stable once clients depend on them; renaming a field is
  safe, renumbering it is a breaking change.
- Every RPC has its **own request and response message**, even for simple operations. This is
  idiomatic gRPC — it means you can add new fields to `CreateEmployeeRequest` later without
  touching the method signature or breaking old clients.
- All four RPCs here are **unary**: one request in, one response out — the simplest gRPC call
  shape, and a direct match for CRUD operations. gRPC also supports streaming (client-streaming,
  server-streaming, bidirectional) for cases like `ListEmployees` returning many records — not
  used here, but a natural next step.

*(The `.proto` contract itself never changed when we added Postgres — this is one of the points
of gRPC's design: storage is an implementation detail behind the contract, invisible to clients.)*

---

## 4. Compiling the `.proto` file

```bash
python3 -m grpc_tools.protoc \
  -I proto \
  --python_out=server \
  --grpc_python_out=server \
  proto/employee.proto
```

- `-I proto` — where to look for `.proto` files (the import path)
- `--python_out` — generates the message classes → `employee_pb2.py`
- `--grpc_python_out` — generates the service stub/servicer classes → `employee_pb2_grpc.py`

This produces two files, each with a distinct job:

| File | Contains | Used by |
|---|---|---|
| `employee_pb2.py` | Python classes for every `message` in the `.proto` (e.g. `Employee`, `CreateEmployeeRequest`), plus binary serialize/deserialize logic | Both client and server — anywhere a message needs to be built or read |
| `employee_pb2_grpc.py` | `EmployeeServiceStub` (client-side proxy for calling RPCs) and `EmployeeServiceServicer` (server-side base class to subclass), plus `add_EmployeeServiceServicer_to_server` glue | Client imports the **Stub**; server imports the **Servicer** and the glue function |

You never hand-edit these generated files — if the `.proto` changes, you just re-run `protoc`.

---

## 5. The server (`server/server.py`) — original in-memory version

- Subclasses `EmployeeServiceServicer` and overrides all four RPC methods (the generated base
  class stubs them out with an `UNIMPLEMENTED` error — overriding replaces that with real logic).
- Stores employees in `self._employees` (a plain dict) plus a `self._next_id` counter.
- Uses a `threading.Lock()` around all reads/writes, because `grpc.server(...)` runs on a thread
  pool (`ThreadPoolExecutor`) — multiple requests can be handled concurrently, so the shared dict
  needs protection from race conditions.
- Signals errors via `context.set_code(grpc.StatusCode.NOT_FOUND)` and
  `context.set_details(...)`, gRPC's equivalent of an HTTP status code — not a raised Python
  exception on the server side.
- `add_insecure_port("[::]:50051")` binds the server to all network interfaces on port 50051,
  with no TLS (fine for local learning; production would use `add_secure_port` with certificates).
- `wait_for_termination()` blocks the main thread indefinitely so the process stays alive to keep
  handling requests (actual request handling happens on the background thread pool).

## 6. The client

Two versions, same underlying calls:

- **`client.py`** — hardcoded values, walks through Create → Get → Update → Delete → Get (expects
  a NOT_FOUND error) in one run. Good for seeing the whole lifecycle at a glance.
- **`interactive_client.py`** — a simple menu loop using `input()` so you can create/get/update/
  delete employees interactively without editing code each time.

Both create a `grpc.insecure_channel("localhost:50051")` (the connection) and wrap it in an
`EmployeeServiceStub` (the callable proxy). Calling `stub.CreateEmployee(request)` looks like a
normal function call — the serialization, network transport, and deserialization are all hidden
behind it.

Client-side errors surface as Python exceptions (`grpc.RpcError`), even though the server never
raised one — gRPC translates a non-OK status code into an exception automatically on the client:

```python
try:
    stub.GetEmployee(employee_pb2.GetEmployeeRequest(id=employee_id))
except grpc.RpcError as e:
    print(e.code(), e.details())
```

---

## 7. Data flow diagram

See [`data-flow-diagram.svg`](./data-flow-diagram.svg) for a visual walkthrough of a single
`CreateEmployee` call, showing exactly which generated file does what at each step:

![data-flow-diagram.svg](data-flow-diagram.svg)

1. `client.py` builds a `CreateEmployeeRequest`
2. `employee_pb2.py` provides that message class
3. `employee_pb2_grpc.py`'s `EmployeeServiceStub` serializes it and sends it over the channel
4. The server's `grpc.server` receives the bytes and routes by method path
5. `employee_pb2_grpc.py`'s generated glue deserializes (using `employee_pb2.py`) and dispatches
   to our `EmployeeServicer`
6. `server.py`'s `CreateEmployee` method runs the actual logic against the in-memory dict
7. The response travels back the same path in reverse

---

## 8. Running the original in-memory version

Terminal 1 — start the server:

```bash
source .venv/bin/activate
cd server
python3 server.py
# Employee gRPC server running on port 50051...
```

Terminal 2 — run a client:

```bash
source .venv/bin/activate
cd client
python3 client.py                # scripted CRUD walkthrough
```

---
---

# Part 2 — Adding persistence, Docker, reflection, and Postman

Everything above still applies conceptually (the `.proto` contract, gRPC mechanics, client
patterns). What changed below is purely **how the server stores data and how we test it** — the
gRPC layer itself didn't change shape.

## 9. Why add a database at all?

The in-memory dict was intentional at first (Section 1), but it has an obvious limitation:
**restart the server, lose all data.** Moving storage into PostgreSQL means employees persist
across restarts, can be inspected/queried outside the app (via DBeaver or `psql`), and the setup
now resembles how a real backend service would actually be built.

## 10. PostgreSQL via Docker (with persistent storage)

We run Postgres in Docker instead of installing it directly, so the database is isolated,
disposable, and reproducible on any machine with Docker installed — no "works on my machine"
version drift.

`docker-compose.yml` (at the project root):

```yaml
services:
  postgres:
    image: postgres:16
    container_name: employee-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: employee_app
      POSTGRES_PASSWORD: employee_pass
      POSTGRES_DB: employee_db
    ports:
      - "5432:5432"
    volumes:
      - employee_pg_data:/var/lib/postgresql/data

volumes:
  employee_pg_data:
```

- **`image: postgres:16`** — the official Postgres image.
- **`environment`** — read by the image *only on first startup* to create the user/password/
  database combo; ignored on subsequent restarts.
- **`volumes: employee_pg_data:/var/lib/postgresql/data`** — this is the important line for
  persistence. It maps Postgres's internal data directory to a **named Docker volume**, which
  lives outside the container's own filesystem. Without this, deleting or recreating the
  container would wipe all employee data along with it.

Bring it up:

```bash
docker compose up -d
docker ps                 # confirm 'employee-postgres' is running
docker logs employee-postgres   # look for "database system is ready to accept connections"
```

## 11. Viewing the data with DBeaver

DBeaver isn't a database itself — it's a GUI client that connects to a running Postgres server
so you can browse tables/rows visually instead of using `psql`.

**New Connection → PostgreSQL:**
- Host: `localhost`
- Port: `5432`
- Database: `employee_db`
- Username: `employee_app`
- Password: `employee_pass`

After connecting: `employee_db` → `Databases` → `employee_db` → `Schemas` → `public` → `Tables`.
DBeaver caches schema metadata, so after creating tables via code (Section 13), right-click
**Tables → Refresh** to see them appear.

## 12. The SQLAlchemy layer

We chose **SQLAlchemy (ORM)** over raw `psycopg2` + hand-written SQL, trading a bit of
transparency for less boilerplate — closer to how most real Python backends talk to a database.

New files, all living in a `db/` package at the **project root** (a sibling of `server/` and
`client/`, not nested inside either):

```
employee-grpc/
├── db/
│   ├── database.py     ← engine + session factory
│   ├── emp_model.py    ← the ORM model (DB row ↔ Python class)
│   └── init_db.py      ← one-off script to create tables
├── server/
├── client/
├── proto/
├── docker-compose.yml
└── startup.sh
```

**`db/database.py`:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://employee_app:employee_pass@localhost:5432/employee_db"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
```
- `echo=True` prints every SQL statement SQLAlchemy runs under the hood — useful while learning,
  since it shows exactly what `session.add(...)`/`session.commit()` translate to as real SQL.
- `SessionLocal` is a **factory**, not a session itself — we call it fresh per request
  (explained in Section 14).

**`db/emp_model.py`:**
```python
from sqlalchemy import Column, Integer, String, Numeric
from db.database import Base

class EmployeeModel(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    salary = Column(Numeric, nullable=False)
```
This is deliberately a **separate class** from `employee_pb2.Employee` (the gRPC wire message).
`EmployeeModel` describes a database row; `employee_pb2.Employee` describes a network message.
Keeping them separate means the DB schema and the API contract can evolve independently — we
translate explicitly between the two in `server.py` (a small `to_proto()` helper).

**`db/init_db.py`:**
```python
from db.database import engine, Base
from db import emp_model  # noqa: F401  (import so Base knows about EmployeeModel)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created (or already existed).")
```
Run this once (or whenever models change) to create tables — the ORM equivalent of running
`CREATE TABLE` by hand. `create_all()` is idempotent: it skips tables that already exist, so
it's safe to re-run.

## 13. Why `db/` sits outside `server/` and `client/`, and the `PYTHONPATH` issue it causes

We chose to keep `db/` at the project root, shared conceptually by whichever process needs
persistence — right now just the server, but structurally it's not tied to `server/` alone.

The cost of that choice: when you run `python3 server/server.py`, Python only auto-adds the
**script's own folder** (`server/`) to its import search path — not the project root above it.
So `import employee_pb2` works (same folder), but `from db.database import SessionLocal` fails
with `ModuleNotFoundError: No module named 'db'`, because `db/` is one level up, outside that
search path.

**Fix:** explicitly add the project root to `PYTHONPATH` before running anything:
```bash
export PYTHONPATH=$(pwd)   # run once per terminal session, from the project root
```
or permanently, via `~/.bashrc`:
```bash
echo 'export PYTHONPATH=~/employee_grpc' >> ~/.bashrc
source ~/.bashrc
```
`startup.sh` (Section 17) sets this automatically every time, so you don't have to remember it.

## 14. The updated server (`server/server.py`) — Postgres-backed

Same four RPC methods, same signatures, same gRPC interface — only the storage logic inside
each method changed.

```python
from concurrent import futures
import grpc

import employee_pb2
import employee_pb2_grpc
from db.database import SessionLocal
from db.emp_model import EmployeeModel


def to_proto(db_employee: EmployeeModel) -> employee_pb2.Employee:
    return employee_pb2.Employee(
        id=db_employee.id,
        name=db_employee.name,
        department=db_employee.department,
        salary=float(db_employee.salary),  # Numeric column comes back as Decimal
    )


class EmployeeServicer(employee_pb2_grpc.EmployeeServiceServicer):
    def CreateEmployee(self, request, context):
        session = SessionLocal()
        try:
            db_employee = EmployeeModel(
                name=request.name,
                department=request.department,
                salary=request.salary,
            )
            session.add(db_employee)
            session.commit()
            session.refresh(db_employee)
            return employee_pb2.CreateEmployeeResponse(employee=to_proto(db_employee))
        finally:
            session.close()

    def GetEmployee(self, request, context):
        session = SessionLocal()
        try:
            db_employee = session.get(EmployeeModel, request.id)
            if db_employee is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Employee with id {request.id} not found")
                return employee_pb2.GetEmployeeResponse()
            return employee_pb2.GetEmployeeResponse(employee=to_proto(db_employee))
        finally:
            session.close()

    # UpdateEmployee, DeleteEmployee follow the same session-per-request pattern
```

**What changed and why, compared to the in-memory version:**

- **No more `threading.Lock()`.** The in-memory dict needed manual locking because plain Python
  dicts have zero protection against concurrent mutation. Postgres is built specifically to
  handle many simultaneous clients safely — every write runs inside an atomic transaction, with
  row-level locking and MVCC handled internally. We deleted the lock; the database now does that
  job, more robustly than a single `threading.Lock()` ever could.
- **A fresh `Session` per request, though — not removed, just relocated.** This looks like it
  contradicts the point above, but it's a different layer: a SQLAlchemy `Session` is stateful
  (tracks pending changes, loaded objects, an open connection) — that Python-level bookkeeping
  *is* shared mutable state, same category of problem as the original dict. Since
  `grpc.server(...)` handles requests on a thread pool (`ThreadPoolExecutor(max_workers=10)`),
  sharing one global `Session` across threads would risk one request's changes bleeding into
  another's. `session = SessionLocal()` at the top of each method, `session.close()` in a
  `finally`, keeps every request's bookkeeping fully isolated.
- **`session.get(EmployeeModel, request.id)`** replaces the old `self._employees.get(request.id)`
  — same idea, now backed by a real `SELECT ... WHERE id = ...` under the hood.
- **`session.commit()`** flushes pending changes as real SQL and commits the transaction —
  nothing hits the actual table until this line runs.
- **`session.refresh(db_employee)`** after insert — Postgres assigns `id` via `SERIAL` at insert
  time; `refresh` pulls that generated value back into the Python object so it can go in the
  response.
- **`to_proto()`** is the explicit translation between `EmployeeModel` (DB row) and
  `employee_pb2.Employee` (wire message) mentioned in Section 12 — kept as a small standalone
  function so the mapping is visible in one place.
- **Error handling (`context.set_code(grpc.StatusCode.NOT_FOUND)`) is unchanged** — this was
  never tied to the storage backend, so it carried over exactly as-is.

## 15. gRPC Server Reflection

Added so tools like Postman (or `grpcurl`) can discover the service's methods and message shapes
**at runtime**, without manually importing `employee.proto` into every tool.

**What reflection actually is:** it's a special extra gRPC service
(`grpc.reflection.v1alpha.ServerReflection`) running alongside `EmployeeService`. When a client
calls it, the server sends back its own compiled schema (the same `FileDescriptorProto` metadata
baked into `employee_pb2.py`'s `DESCRIPTOR`) — so the server is literally handing its own `.proto`
contract over the wire, on request.

**Why reflection over just importing the `.proto` into Postman directly:** direct import works
with zero server changes, but the moment the `.proto` changes, you have to manually re-import it
again — easy to forget, and it can silently drift out of sync with what the server actually
expects. Reflection means any tool always sees the live, current schema straight from the running
server, no manual file-passing, and it's the more realistic pattern for how production gRPC
services are typically set up for internal tooling.

```python
from grpc_reflection.v1alpha import reflection

service_names = (
    employee_pb2.DESCRIPTOR.services_by_name["EmployeeService"].full_name,
    reflection.SERVICE_NAME,
)
reflection.enable_server_reflection(service_names, server)
```
- `employee_pb2.DESCRIPTOR.services_by_name["EmployeeService"].full_name` pulls
  `"employee.EmployeeService"` directly from the compiled descriptor rather than hardcoding the
  string.
- `reflection.SERVICE_NAME` — reflection has to advertise *itself* too, or clients couldn't
  discover it exists in the first place.
- Both live on the same port (`50051`) as `EmployeeService` — reflection isn't a separate
  server/port, just another registered service on the existing one.

**Note:** reflection hands out your entire API schema to anyone who can reach the port, so it's
generally disabled in production and used for internal/dev tooling — exactly the use case here.

Verified with `grpcurl`:
```bash
grpcurl -plaintext localhost:50051 list
# employee.EmployeeService
# grpc.reflection.v1alpha.ServerReflection

grpcurl -plaintext localhost:50051 describe employee.EmployeeService
```

## 16. Testing via Postman

With reflection in place:

1. **New → gRPC Request**
2. URL: `localhost:50051` (plaintext, matching `add_insecure_port`)
3. Postman fetches the schema via server reflection automatically — `EmployeeService` appears
   with all four methods
4. Pick a method (e.g. `CreateEmployee`), fill in the auto-generated JSON body:
   ```json
   { "name": " Name", "department": "Engineering", "salary": 75000 }
   ```
5. **Invoke** — response comes back in the same JSON-like shape, and the row is now persisted in
   Postgres (verifiable in DBeaver).

If reflection doesn't auto-populate: confirm the server (with the reflection block from Section
15) is actually running and reachable on `localhost:50051`; as a fallback, `proto/employee.proto`
can always be imported into Postman directly.

## 17. `startup.sh` — tying it all together

Rather than remembering `PYTHONPATH`, waiting for Postgres to be ready, and initializing tables
by hand every time, `startup.sh` (at the project root) automates the whole sequence:

```bash
#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT"

echo "Waiting for Postgres to accept connections..."
MAX_ATTEMPTS=15
attempt=0
until docker exec employee-postgres pg_isready -U employee_app -d employee_db > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: Postgres did not become ready after ${MAX_ATTEMPTS} attempts."
        exit 1
    fi
    sleep 1
done
echo "Postgres is ready."

python3 -m db.init_db

echo "Starting server..."
exec python3 server/server.py
```

**Why each part exists:**
- **Resolving `PROJECT_ROOT` from `${BASH_SOURCE[0]}`** — so the script works identically
  whether you run it from the project root or via a full/relative path from anywhere else.
- **`export PYTHONPATH="$PROJECT_ROOT"`** — solves the exact import problem from Section 13,
  automatically, every run — no more manually exporting or forgetting it in a new terminal.
- **The `pg_isready` polling loop** — a container reporting "started" via `docker ps` is not the
  same moment as Postgres actually being ready to accept connections; there's a brief startup
  window where connecting would fail. Polling avoids racing that window.
- **`python3 -m db.init_db`** — ensures the `employees` table exists before the server tries to
  use it; safe to re-run since `create_all()` is idempotent.
- **`exec python3 server/server.py`** at the end — `exec` replaces the shell process with the
  server process instead of spawning a child, so `Ctrl+C` and exit codes behave exactly as if
  you'd run the server command directly, with no extra shell layer in between.

Usage:
```bash
chmod +x startup.sh   # one-time
./startup.sh
```
This single command now does: resolve paths → set `PYTHONPATH` → wait for Postgres → create
tables if needed → start the server. (It assumes `docker compose up -d` has already been run at
least once to bring the Postgres container up; `restart: unless-stopped` in
`docker-compose.yml` keeps it running after that.)

## 18. Running the full updated stack, end to end

```bash
# One-time / as needed
docker compose up -d              # start Postgres (persists via named volume)

# Every time you want to run the service
./startup.sh                      # sets PYTHONPATH, waits for DB, creates tables, starts server
```

Then test via **Postman** (Section 16) or the original `client.py` (Section 6, still works
unchanged — the gRPC interface never moved) — and check persisted rows anytime in **DBeaver**
(Section 11).