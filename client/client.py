import grpc

import employee_pb2
import employee_pb2_grpc


def run():
    # A channel represents the connection to the server.
    # 'localhost:50051' must match where our server is listening.
    with grpc.insecure_channel("localhost:50051") as channel:
        # The stub is our local proxy for the remote service - calling a
        # method on it looks like a normal function call, but under the hood
        # it serializes the request, sends it over the network, and
        # deserializes the response.
        stub = employee_pb2_grpc.EmployeeServiceStub(channel)

        # --- CREATE ---
        create_response = stub.CreateEmployee(
            employee_pb2.CreateEmployeeRequest(
                name="FirstName LastName",
                department="Engineering",
                salary=75000.0,
            )
        )
        employee_id = create_response.employee.id
        print(f"Created: {create_response.employee}")

        # --- READ ---
        get_response = stub.GetEmployee(
            employee_pb2.GetEmployeeRequest(id=employee_id)
        )
        print(f"Fetched: {get_response.employee}")

        # --- UPDATE ---
        update_response = stub.UpdateEmployee(
            employee_pb2.UpdateEmployeeRequest(
                id=employee_id,
                name="FirstName LastName",
                department="Platform Engineering",  # promoted teams
                salary=85000.0,
            )
        )
        print(f"Updated: {update_response.employee}")

        # --- DELETE ---
        delete_response = stub.DeleteEmployee(
            employee_pb2.DeleteEmployeeRequest(id=employee_id)
        )
        print(f"Deleted successfully: {delete_response.success}")

        # --- READ again, to prove it's gone ---
        try:
            stub.GetEmployee(employee_pb2.GetEmployeeRequest(id=employee_id))
        except grpc.RpcError as e:
            print(f"Expected error after delete: {e.code()} - {e.details()}")


if __name__ == "__main__":
    run()