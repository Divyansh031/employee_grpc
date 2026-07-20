import threading
from concurrent import futures

import grpc

import employee_pb2
import employee_pb2_grpc


class EmployeeServicer(employee_pb2_grpc.EmployeeServiceServicer):
    """
    This class implements the actual business logic for our RPCs.
    It overrides every method that the generated EmployeeServiceServicer
    base class stubbed out with 'UNIMPLEMENTED'.
    """

    def __init__(self):
        # our "database" - just a dict in memory
        self._employees = {}
        self._next_id = 1
        # gRPC servers are multi-threaded by default (see the ThreadPoolExecutor
        # below), so multiple requests could touch this dict at the same time.
        # A lock keeps our reads/writes safe.
        self._lock = threading.Lock()

    def CreateEmployee(self, request, context):
        with self._lock:
            employee_id = self._next_id
            self._next_id += 1

            employee = employee_pb2.Employee(
                id=employee_id,
                name=request.name,
                department=request.department,
                salary=request.salary,
            )
            self._employees[employee_id] = employee

        print(f"[CreateEmployee] created id={employee_id} name={request.name!r}")
        return employee_pb2.CreateEmployeeResponse(employee=employee)

    def GetEmployee(self, request, context):
        with self._lock:
            employee = self._employees.get(request.id)

        if employee is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Employee with id {request.id} not found")
            return employee_pb2.GetEmployeeResponse()

        return employee_pb2.GetEmployeeResponse(employee=employee)

    def UpdateEmployee(self, request, context):
        with self._lock:
            if request.id not in self._employees:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Employee with id {request.id} not found")
                return employee_pb2.UpdateEmployeeResponse()

            employee = employee_pb2.Employee(
                id=request.id,
                name=request.name,
                department=request.department,
                salary=request.salary,
            )
            self._employees[request.id] = employee

        print(f"[UpdateEmployee] updated id={request.id}")
        return employee_pb2.UpdateEmployeeResponse(employee=employee)

    def DeleteEmployee(self, request, context):
        with self._lock:
            if request.id not in self._employees:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Employee with id {request.id} not found")
                return employee_pb2.DeleteEmployeeResponse(success=False)

            del self._employees[request.id]

        print(f"[DeleteEmployee] deleted id={request.id}")
        return employee_pb2.DeleteEmployeeResponse(success=True)


def serve():
    # max_workers controls how many requests can be handled concurrently
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    employee_pb2_grpc.add_EmployeeServiceServicer_to_server(
        EmployeeServicer(), server
    )

    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Employee gRPC server running on port {port}...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()