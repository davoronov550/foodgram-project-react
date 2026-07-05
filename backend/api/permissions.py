from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class AuthorOnly(BasePermission):
    """
    Разрешение только автору объекта.
    """

    def has_object_permission(
        self, request: Request, view: APIView, obj
    ) -> bool:
        return (request.method in SAFE_METHODS
                or obj.author == request.user)
