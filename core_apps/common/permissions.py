from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import View


class IsParent(permissions.BasePermission):
    def has_permission(self, request: Request, view: View) -> bool:
        is_authenticated = request.user.is_authenticated
        has_role_attr = hasattr(request.user, "role")
        return (
            is_authenticated
            and has_role_attr
            and request.user.role == "parent"
        )


class IsTeacher(permissions.BasePermission):
    def has_permission(self, request: Request, view: View) -> bool:
        is_authenticated = request.user.is_authenticated
        has_role_attr = hasattr(request.user, "role")
        return is_authenticated and has_role_attr and request.user.role == "teacher"


class IsOfficeStaff(permissions.BasePermission):
    def has_permission(self, request: Request, view: View) -> bool:
        is_authenticated = request.user.is_authenticated
        has_role_attr = hasattr(request.user, "role")
        return (
            is_authenticated and has_role_attr and request.user.role == "office_staff"
        )