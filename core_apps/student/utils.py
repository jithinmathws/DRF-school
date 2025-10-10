import secrets
from os import getenv
from typing import Union, List
from django.db import transaction, IntegrityError
from core_apps.student import emails as StudentEmails

from core_apps.student import models as student_models


def generate_admission_number(total_length: int = 16) -> str:
    school_code = getenv("SCHOOL_CODE")
    if not school_code or not school_code.isdigit():
        raise ValueError("SCHOOL_CODE must be set and numeric.")

    prefix = f"{school_code}"

    remaining_digits = total_length - len(prefix) - 1
    if remaining_digits <= 0:
        raise ValueError("SCHOOL_CODE too long for the configured admission number length.")

    random_digits = "".join(
        secrets.choice("0123456789") for _ in range(remaining_digits)
    )
    partial_admission_number = f"{prefix}{random_digits}"

    check_digit = calculate_luhn_check_digit(partial_admission_number)
    return f"{partial_admission_number}{check_digit}"


def calculate_luhn_check_digit(number: str) -> int:
    def split_into_digits(n: Union[str, int]) -> List[int]:
        return [int(digit) for digit in str(n)]

    digits = split_into_digits(number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)

    for d in even_digits:
        doubled = d * 2
        total += sum(split_into_digits(doubled))

    return (10 - (total % 10)) % 10


def create_student_account(
    user,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    gender: str | None = None,
) -> student_models.Student:
    """Create a student account for a parent user.

    Requires first_name, last_name, gender to satisfy model constraints.
    Ensures unique admission number with retry and sends email after commit.
    """
    # Apply sensible defaults if not provided
    if not first_name:
        first_name = "Student"
    if not last_name:
        last_name = (getattr(user, "last_name", None) or "Account")
    if not gender:
        gender = student_models.Student.Gender.OTHER

    # Basic gender validation against choices
    gender_values = {choice[0] for choice in student_models.Student.Gender.choices}
    if gender not in gender_values:
        raise ValueError(f"Invalid gender value. Allowed: {sorted(gender_values)}")

    with transaction.atomic():
        has_sibling = student_models.Student.objects.filter(parent=user).exists()

        # Generate and attempt to create until unique admission_number is persisted
        while True:
            admission_number = generate_admission_number(16)
            try:
                student_account = student_models.Student.objects.create(
                    parent=user,
                    admission_number=admission_number,
                    has_sibling=has_sibling,
                    first_name=first_name.strip().title(),
                    last_name=last_name.strip().title(),
                    gender=gender,
                )
                break
            except IntegrityError:
                # Collision on unique admission_number, retry
                continue

        # Defer email until transaction successfully commits
        transaction.on_commit(lambda: send_account_creation_email(user, student_account))

    return student_account