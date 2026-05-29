"""Authenticated principal models and role definitions for backend authorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PrincipalRole(str, Enum):
    """Supported RBAC roles for the first backend authorization slice."""

    READER = "reader"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    STEWARD = "steward"
    BENCHMARK_OPERATOR = "benchmark_operator"
    PLATFORM_ADMIN = "platform_admin"


ALL_PRINCIPAL_ROLES: tuple[PrincipalRole, ...] = tuple(PrincipalRole)


@dataclass(slots=True)
class AuthenticatedPrincipal:
    """Minimal authenticated principal extracted from request headers."""

    user_id: str | None = None
    tenant_id: str | None = None
    team_ids: tuple[str, ...] = ()
    roles: frozenset[PrincipalRole] = field(default_factory=frozenset)
    identity_source: str = "anonymous"

    @property
    def is_platform_admin(self) -> bool:
        return PrincipalRole.PLATFORM_ADMIN in self.roles