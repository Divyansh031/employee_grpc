from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection


import employee_pb2
import employee_pb2_grpc
from db.database import SessionLocal
from db.emp_model import EmployeeModel


def to_proto(db_employee: EmployeeModel) -> employee_pb2.Employee:
    """Translate a DB row (EmployeeModel) into a wire message (employee_pb2.Employee)."""
    return employee_pb2.Employee(
        id=db_employee.id,
        name=db_employee.name,
        department=db_employee.department,
        salary=float(db_employee.salary),  # Numeric column comes back as Decimal
    )


class EmployeeServicer(employee_pb2_grpc.EmployeeServiceServicer):
    """
    Same interface as before (CreateEmployee, GetEmployee, UpdateEmployee,
    DeleteEmployee), but now backed by Postgres instead of a dict.

    No more threading.Lock() here - the database itself handles concurrent
    access safely (that's literally one of the jobs a DB is built for).
    We DO still need a fresh Session per request though - Sessions aren't
    thread-safe to share across concurrent requests, so each method opens
    its own and closes it when done.
    """

    def CreateEmployee(self, request, context):
        session = SessionLocal()
        try:
            db_employee = EmployeeModel(
                name=request.name,
                department=request.department,
                salary=request.salary,
            )
            session.add(db_employee)
            session.commit()       # writes the INSERT, assigns the auto id
            session.refresh(db_employee)  # pulls the generated id back into the object

            print(f"[CreateEmployee] created id={db_employee.id} name={request.name!r}")
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

    def UpdateEmployee(self, request, context):
        session = SessionLocal()
        try:
            db_employee = session.get(EmployeeModel, request.id)
            if db_employee is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Employee with id {request.id} not found")
                return employee_pb2.UpdateEmployeeResponse()

            db_employee.name = request.name
            db_employee.department = request.department
            db_employee.salary = request.salary
            session.commit()
            session.refresh(db_employee)

            print(f"[UpdateEmployee] updated id={request.id}")
            return employee_pb2.UpdateEmployeeResponse(employee=to_proto(db_employee))
        finally:
            session.close()

    def DeleteEmployee(self, request, context):
        session = SessionLocal()
        try:
            db_employee = session.get(EmployeeModel, request.id)
            if db_employee is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Employee with id {request.id} not found")
                return employee_pb2.DeleteEmployeeResponse(success=False)

            session.delete(db_employee)
            session.commit()

            print(f"[DeleteEmployee] deleted id={request.id}")
            return employee_pb2.DeleteEmployeeResponse(success=True)
        finally:
            session.close()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    employee_pb2_grpc.add_EmployeeServiceServicer_to_server(EmployeeServicer(), server)
 
    # Enable server reflection: advertise our EmployeeService (plus the
    # reflection service itself) so tools like Postman/grpcurl can discover
    # methods and message shapes without needing the .proto file directly.
    service_names = (
        employee_pb2.DESCRIPTOR.services_by_name["EmployeeService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)
 
    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Employee gRPC server (Postgres-backed) running on port {port}...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()