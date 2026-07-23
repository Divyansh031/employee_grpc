import os
from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection

import employee_pb2
import employee_pb2_grpc
from validators import validator
from repositories.base import EmployeeRecord


def get_repository():
    """
    Picks a storage backend based on the DB_BACKEND environment variable.
    Defaults to postgres if unset. This is the ONLY place that reads the
    env var - it returns both the repository instance and the backend name,
    so callers never need to read DB_BACKEND themselves.
    """
    backend = os.environ.get("DB_BACKEND", "postgres").lower()

    if backend == "postgres":
        from repositories.postgres_repository import PostgresEmployeeRepository
        return PostgresEmployeeRepository(), backend
    elif backend == "mongo":
        from repositories.mongo_repository import MongoEmployeeRepository
        return MongoEmployeeRepository(), backend
    else:
        raise ValueError(f"Unknown DB_BACKEND: {backend!r} (expected 'postgres' or 'mongo')")


def to_proto(record: EmployeeRecord) -> employee_pb2.Employee:
    """Translate a repository record (a plain dict) into a wire message."""
    return employee_pb2.Employee(
        id=record["id"],
        name=record["name"],
        department=record["department"],
        salary=record["salary"],
    )


class EmployeeServicer(employee_pb2_grpc.EmployeeServiceServicer):
    """
    This class no longer knows or cares whether it's talking to Postgres or
    MongoDB - it only calls methods on self.repository, which follows the
    EmployeeRepository interface. Swapping backends is a config change
    (DB_BACKEND env var), not a code change here.
    """

    def __init__(self, repository):
        self.repository = repository

    def CreateEmployee(self, request, context):
        errors = validator.validate_create_request(request)
        if errors:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("; ".join(errors))
            return employee_pb2.CreateEmployeeResponse()

        record = self.repository.create(
            name=request.name, department=request.department, salary=request.salary
        )
        print(f"[CreateEmployee] created id={record['id']} name={request.name!r}")
        return employee_pb2.CreateEmployeeResponse(employee=to_proto(record))

    def GetEmployee(self, request, context):
        errors = validator.validate_id_only_request(request)
        if errors:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("; ".join(errors))
            return employee_pb2.GetEmployeeResponse()

        record = self.repository.get(request.id)
        if record is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Employee with id {request.id} not found")
            return employee_pb2.GetEmployeeResponse()

        return employee_pb2.GetEmployeeResponse(employee=to_proto(record))

    def UpdateEmployee(self, request, context):
        errors = validator.validate_update_request(request)
        if errors:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("; ".join(errors))
            return employee_pb2.UpdateEmployeeResponse()

        record = self.repository.update(
            employee_id=request.id,
            name=request.name,
            department=request.department,
            salary=request.salary,
        )
        if record is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Employee with id {request.id} not found")
            return employee_pb2.UpdateEmployeeResponse()

        print(f"[UpdateEmployee] updated id={request.id}")
        return employee_pb2.UpdateEmployeeResponse(employee=to_proto(record))

    def DeleteEmployee(self, request, context):
        errors = validator.validate_id_only_request(request)
        if errors:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("; ".join(errors))
            return employee_pb2.DeleteEmployeeResponse(success=False)

        deleted = self.repository.delete(request.id)
        if not deleted:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Employee with id {request.id} not found")
            return employee_pb2.DeleteEmployeeResponse(success=False)

        print(f"[DeleteEmployee] deleted id={request.id}")
        return employee_pb2.DeleteEmployeeResponse(success=True)


def serve():
    repository, backend_name = get_repository()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    employee_pb2_grpc.add_EmployeeServiceServicer_to_server(
        EmployeeServicer(repository), server
    )

    service_names = (
        employee_pb2.DESCRIPTOR.services_by_name["EmployeeService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Employee gRPC server ({backend_name}-backed) running on port {port}...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()