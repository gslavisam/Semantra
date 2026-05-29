"""Shared FastAPI dependencies such as principal and role enforcement."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.models.auth import ALL_PRINCIPAL_ROLES, AuthenticatedPrincipal, PrincipalRole


def _normalized_header_values(raw_header: str | None) -> list[str]:
    return [value.strip() for value in str(raw_header or "").split(",") if value.strip()]


def _parse_principal_roles(raw_header: str | None) -> frozenset[PrincipalRole]:
    parsed_roles: set[PrincipalRole] = set()
    for raw_role in _normalized_header_values(raw_header):
        try:
            parsed_roles.add(PrincipalRole(raw_role.lower()))
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported principal role '{raw_role}'.",
            ) from error
    return frozenset(parsed_roles)


def _principal_from_headers(
    *,
    principal_id: str | None,
    principal_roles: str | None,
    principal_tenant: str | None,
    principal_teams: str | None,
    admin_token_configured: bool,
) -> AuthenticatedPrincipal | None:
    roles = _parse_principal_roles(principal_roles)
    user_id = str(principal_id or "").strip() or None
    tenant_id = str(principal_tenant or "").strip() or None
    team_ids = tuple(_normalized_header_values(principal_teams))

    header_present = bool(user_id or roles or tenant_id or team_ids)
    if not header_present:
        return None
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Principal-Id header is required when using principal headers.",
        )
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Principal-Roles header is required when using principal headers.",
        )
    if admin_token_configured and PrincipalRole.PLATFORM_ADMIN in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="platform_admin role requires X-Admin-Token authentication.",
        )
    return AuthenticatedPrincipal(
        user_id=user_id,
        tenant_id=tenant_id,
        team_ids=team_ids,
        roles=roles,
        identity_source="principal_headers",
    )


async def get_request_principal(
    x_admin_token: str | None = Header(default=None),
    x_principal_id: str | None = Header(default=None),
    x_principal_roles: str | None = Header(default=None),
    x_principal_tenant: str | None = Header(default=None),
    x_principal_teams: str | None = Header(default=None),
) -> AuthenticatedPrincipal:
    expected_token = settings.admin_api_token.strip()
    provided_token = str(x_admin_token or "").strip()

    if expected_token:
        if provided_token:
            if provided_token != expected_token:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")
            return AuthenticatedPrincipal(
                user_id=str(x_principal_id or "").strip() or "platform-admin",
                tenant_id=str(x_principal_tenant or "").strip() or None,
                team_ids=tuple(_normalized_header_values(x_principal_teams)),
                roles=frozenset(ALL_PRINCIPAL_ROLES),
                identity_source="admin_token",
            )

        header_principal = _principal_from_headers(
            principal_id=x_principal_id,
            principal_roles=x_principal_roles,
            principal_tenant=x_principal_tenant,
            principal_teams=x_principal_teams,
            admin_token_configured=True,
        )
        if header_principal is not None:
            return header_principal
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authenticated principal required")

    header_principal = _principal_from_headers(
        principal_id=x_principal_id,
        principal_roles=x_principal_roles,
        principal_tenant=x_principal_tenant,
        principal_teams=x_principal_teams,
        admin_token_configured=False,
    )
    if header_principal is not None:
        return header_principal

    return AuthenticatedPrincipal(
        user_id="development-admin",
        roles=frozenset(ALL_PRINCIPAL_ROLES),
        identity_source="development-open",
    )


def require_roles(*allowed_roles: PrincipalRole) -> Callable[..., object]:
    allowed_role_set = frozenset(allowed_roles)
    allowed_role_names = ", ".join(role.value for role in allowed_roles)

    async def dependency(principal: AuthenticatedPrincipal = Depends(get_request_principal)) -> AuthenticatedPrincipal:
        if principal.roles.intersection(allowed_role_set):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"One of the following roles is required: {allowed_role_names}.",
        )

    return dependency


async def require_admin(
    principal: AuthenticatedPrincipal = Depends(require_roles(PrincipalRole.PLATFORM_ADMIN)),
) -> None:
    _ = principal