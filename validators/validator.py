"""
Validation helpers for EmployeeService requests.

Each function returns a list of error strings (empty list = valid).
Returning a list rather than raising lets the servicer decide how to report
errors (here: a single INVALID_ARGUMENT gRPC status with all problems joined
together, so a client sees everything wrong in one round trip instead of
fixing one field, resubmitting, hitting the next error, etc.).
"""

MAX_NAME_LENGTH = 100
MAX_DEPARTMENT_LENGTH = 100


def validate_name(name: str) -> list[str]:
    errors = []
    if not name or not name.strip():
        errors.append("name must not be empty")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"name must be at most {MAX_NAME_LENGTH} characters")
    return errors


def validate_department(department: str) -> list[str]:
    errors = []
    if not department or not department.strip():
        errors.append("department must not be empty")
    elif len(department) > MAX_DEPARTMENT_LENGTH:
        errors.append(f"department must be at most {MAX_DEPARTMENT_LENGTH} characters")
    return errors


def validate_salary(salary: float) -> list[str]:
    errors = []
    if salary <= 0:
        errors.append("salary must be a positive number")
    return errors


def validate_id(employee_id: int) -> list[str]:
    errors = []
    if employee_id <= 0:
        errors.append("id must be a positive integer")
    return errors


def validate_create_request(request) -> list[str]:
    return (
        validate_name(request.name)
        + validate_department(request.department)
        + validate_salary(request.salary)
    )


def validate_update_request(request) -> list[str]:
    return (
        validate_id(request.id)
        + validate_name(request.name)
        + validate_department(request.department)
        + validate_salary(request.salary)
    )


def validate_id_only_request(request) -> list[str]:
    """Used by GetEmployee and DeleteEmployee, which only carry an id."""
    return validate_id(request.id)