"""Authentication & tenant middleware for backoffice API.

The backend uses service_role_key (bypasses RLS) but we still need to:
1. Verify the caller is a valid backoffice user
2. Filter data by their allowed_implementations
3. Check role-based permissions

For now: JWT verification via Supabase Auth + backoffice_users lookup.
The admin routes can optionally use get_current_user() as a dependency.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request

from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)

# Default permissions by role
ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "superadmin": {
        "can_edit_prompts": True,
        "can_manage_users": True,
        "can_manage_groups": True,
        "can_generate_reports": True,
        "can_view_usage": True,
        "can_bulk_import": True,
        "can_edit_frameworks": True,
    },
    "admin": {
        "can_edit_prompts": True,
        "can_manage_users": True,
        "can_manage_groups": True,
        "can_generate_reports": True,
        "can_view_usage": False,
        "can_bulk_import": True,
        "can_edit_frameworks": False,
    },
    "analyst": {
        "can_edit_prompts": False,
        "can_manage_users": False,
        "can_manage_groups": False,
        "can_generate_reports": True,
        "can_view_usage": True,
        "can_bulk_import": False,
        "can_edit_frameworks": False,
    },
    "viewer": {
        "can_edit_prompts": False,
        "can_manage_users": False,
        "can_manage_groups": False,
        "can_generate_reports": False,
        "can_view_usage": False,
        "can_bulk_import": False,
        "can_edit_frameworks": False,
    },
}


class BackofficeUser:
    """Authenticated backoffice user with tenant context."""

    def __init__(self, data: dict[str, Any]):
        self.id: str = data["id"]
        self.email: str = data.get("email", "")
        self.name: str = data.get("name", "")
        self.role: str = data.get("role", "viewer")
        self.allowed_implementations: list[str] = data.get("allowed_implementations") or []
        self.permissions: dict[str, bool] = data.get("permissions") or {}
        self.is_active: bool = data.get("is_active", True)

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"

    def has_impl_access(self, impl_id: str) -> bool:
        """Check if user can access a specific implementation."""
        if self.is_superadmin:
            return True
        return impl_id in self.allowed_implementations

    def has_permission(self, perm: str) -> bool:
        """Check a specific permission. User-level overrides role defaults."""
        # User-level override first
        if perm in self.permissions:
            return self.permissions[perm]
        # Fall back to role defaults
        role_perms = ROLE_PERMISSIONS.get(self.role, {})
        return role_perms.get(perm, False)

    def filter_implementations(self, impl_ids: list[str]) -> list[str]:
        """Filter a list of implementation IDs to only those the user can access."""
        if self.is_superadmin:
            return impl_ids
        return [i for i in impl_ids if i in self.allowed_implementations]


async def get_current_user(request: Request) -> BackofficeUser:
    """Extract and verify the current backoffice user from JWT.

    Usage as FastAPI dependency:
        @router.get("/something")
        async def endpoint(user: BackofficeUser = Depends(get_current_user)):
            if not user.has_impl_access("telecable"):
                raise HTTPException(403)
    """
    auth_header = request.headers.get("Authorization", "")

    # If no auth header, check if we're in transition mode (allow unauthenticated)
    # TODO: Remove this fallback once frontend auth is verified working
    if not auth_header.startswith("Bearer "):
        from src.config.settings import settings
        if settings.environment.lower() in ("development", "dev", "local", "transition"):
            logger.warning("auth_bypassed_transition_mode")
            return BackofficeUser({
                "id": "anonymous",
                "email": "anonymous",
                "name": "Anonymous (transition)",
                "role": "superadmin",
                "allowed_implementations": [],
                "is_active": True,
            })
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header.split(" ", 1)[1]

    try:
        # Verify JWT with Supabase
        from src.config.settings import settings
        from supabase import create_client

        # Use anon key client for JWT verification (not service_role)
        anon_client = create_client(settings.supabase_url, settings.supabase_anon_key)
        user_response = anon_client.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = user_response.user.id

        # Look up backoffice_users record
        client = get_client()
        result = (
            client.table("backoffice_users")
            .select("*")
            .eq("id", user_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )

        if not result or not result.data:
            raise HTTPException(
                status_code=403,
                detail="User not registered in backoffice. Contact admin.",
            )

        # Update last_login
        import datetime
        client.table("backoffice_users").update({
            "last_login": datetime.datetime.now(datetime.UTC).isoformat(),
        }).eq("id", user_id).execute()

        return BackofficeUser(result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("auth_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")


def require_permission(perm: str):
    """Factory for permission-checking dependencies.

    Usage:
        @router.post("/edit-prompt")
        async def edit(user: BackofficeUser = Depends(require_permission("can_edit_prompts"))):
            ...
    """
    async def checker(user: BackofficeUser = Depends(get_current_user)) -> BackofficeUser:
        if not user.has_permission(perm):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {perm} required (your role: {user.role})",
            )
        return user
    return checker


def require_superadmin():
    """Dependency that requires superadmin role."""
    async def checker(user: BackofficeUser = Depends(get_current_user)) -> BackofficeUser:
        if not user.is_superadmin:
            raise HTTPException(status_code=403, detail="Superadmin required")
        return user
    return checker


# ── Admin endpoints for managing backoffice users ──────────────


async def list_backoffice_users() -> list[dict[str, Any]]:
    """List all backoffice users (superadmin only)."""
    client = get_client()
    result = client.table("backoffice_users").select("*").order("created_at").execute()
    return result.data or []


async def create_backoffice_user(
    email: str,
    name: str,
    role: str = "admin",
    allowed_implementations: list[str] | None = None,
    permissions: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Create a backoffice user. The user must already exist in Supabase Auth."""
    client = get_client()

    # Find the auth.users record by email
    # We need to use the admin API for this
    from src.config.settings import settings
    from supabase import create_client as sc
    admin_client = sc(settings.supabase_url, settings.supabase_service_role_key)

    # List users and find by email
    users_response = admin_client.auth.admin.list_users()
    auth_user = None
    for u in users_response:
        if hasattr(u, 'email') and u.email == email:
            auth_user = u
            break

    if not auth_user:
        # Create the auth user with a temp password
        import secrets
        temp_password = secrets.token_urlsafe(16)
        auth_user = admin_client.auth.admin.create_user({
            "email": email,
            "password": temp_password,
            "email_confirm": True,
        })
        logger.info("auth_user_created", email=email)

    user_id = auth_user.id if hasattr(auth_user, 'id') else str(auth_user)

    # Insert backoffice_users record
    row = {
        "id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "allowed_implementations": allowed_implementations or [],
        "permissions": permissions or {},
        "is_active": True,
    }

    result = client.table("backoffice_users").upsert(row).execute()
    return result.data[0] if result.data else row
