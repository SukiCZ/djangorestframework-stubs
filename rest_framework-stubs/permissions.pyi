from _typeshed import Incomplete
from collections.abc import Sequence
from typing import Any, Protocol

from django.db.models import Model, QuerySet
from rest_framework.request import Request
from rest_framework.views import APIView
from typing_extensions import TypeAlias

SAFE_METHODS: Sequence[str]

class _SupportsHasPermission(Protocol):
    def has_permission(self, request: Request, view: APIView) -> bool: ...
    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool: ...

# https://github.com/python/mypy/issues/12392
_PermissionClass: TypeAlias = type[BasePermission] | OperandHolder | SingleOperandHolder

class OperationHolderMixin:
    def __and__(self, other: _PermissionClass) -> OperandHolder: ...
    def __or__(self, other: _PermissionClass) -> OperandHolder: ...
    def __rand__(self, other: _PermissionClass) -> OperandHolder: ...
    def __ror__(self, other: _PermissionClass) -> OperandHolder: ...
    def __invert__(self) -> SingleOperandHolder: ...

class SingleOperandHolder(OperationHolderMixin):
    operator_class: _SupportsHasPermission
    op1_class: _PermissionClass
    def __init__(self, operator_class: _SupportsHasPermission, op1_class: _PermissionClass) -> None: ...
    def __call__(self, *args: Incomplete, **kwargs: Incomplete) -> _SupportsHasPermission: ...

class OperandHolder(OperationHolderMixin):
    operator_class: _SupportsHasPermission
    op1_class: _PermissionClass
    op2_class: _PermissionClass
    def __init__(
        self, operator_class: _SupportsHasPermission, op1_class: _PermissionClass, op2_class: _PermissionClass
    ) -> None: ...
    def __call__(self, *args: Incomplete, **kwargs: Incomplete) -> _SupportsHasPermission: ...

class AND(_SupportsHasPermission):
    def __init__(self, op1: _SupportsHasPermission, op2: _SupportsHasPermission) -> None: ...

class OR(_SupportsHasPermission):
    def __init__(self, op1: _SupportsHasPermission, op2: _SupportsHasPermission) -> None: ...

class NOT(_SupportsHasPermission):
    def __init__(self, op1: _SupportsHasPermission) -> None: ...

class BasePermissionMetaclass(OperationHolderMixin, type): ...  # type: ignore[misc,unused-ignore]

class BasePermission(metaclass=BasePermissionMetaclass):
    def has_permission(self, request: Request, view: APIView) -> bool: ...
    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool: ...

class AllowAny(BasePermission): ...
class IsAuthenticated(BasePermission): ...
class IsAdminUser(BasePermission): ...
class IsAuthenticatedOrReadOnly(BasePermission): ...

class DjangoModelPermissions(BasePermission):
    perms_map: dict[str, list[str]]
    authenticated_users_only: bool
    def get_required_permissions(self, method: str, model_cls: type[Model]) -> list[str]: ...
    def _queryset(self, view: APIView) -> QuerySet: ...

class DjangoModelPermissionsOrAnonReadOnly(DjangoModelPermissions): ...

class DjangoObjectPermissions(DjangoModelPermissions):
    def get_required_object_permissions(self, method: str, model_cls: type[Model]) -> list[str]: ...
