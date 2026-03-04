import secrets
from datetime import datetime, timedelta

from fastapi import Request, HTTPException

from service54.actions import EntityActionMixin
from service54.core.validators.entity_validators import AnonymousLinkCreateValidator
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.exceptions import Forbidden
from service54.core.exceptions import EntityNotFound


class AnonymousLinkCreateAction(EntityActionMixin):
    """
    Action to create an anonymous share link for an entity.

    TODO: CHECK WHO CAN CREATE ANONYMOUS LINKS - currently all authenticated users can create
    """

    def __init__(
        self,
        data: AnonymousLinkCreateValidator,
        request: Request,
        db: AsyncDatabaseAdapter,
        partition_uuid: str
    ):
        super().__init__(request, db)
        self.actor = request.state.actor
        self.url = data.url
        self.entity_uuid = data.entity_uuid
        self.partition_uuid = partition_uuid
        self.expires_at_str = data.expires_at

    async def execute(self):
        """
        Create anonymous link flow:
        3. Validate entity exists
        4. Validate expiration datetime
        5. Generate unique token
        6. Save to database
        7. Return link data
        """
        # Check if entity exists
        if not await self.check_exist():
            raise EntityNotFound(message="Entity not found")

        # Parse expiration datetime
        try:
            expires_at = datetime.fromisoformat(self.expires_at_str.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid expires_at format. Use ISO format: 2025-02-20T12:00:00Z"
            )

        # Check if expiration is in the future
        if expires_at < datetime.now(expires_at.tzinfo):
            raise HTTPException(
                status_code=400,
                detail="Expiration datetime must be in the future"
            )

        # Check if expiration is within 2 years
        max_expiration = datetime.now(expires_at.tzinfo) + timedelta(days=730)  # 2 years
        if expires_at > max_expiration:
            raise HTTPException(
                status_code=400,
                detail="Expiration datetime must be within 2 years from now"
            )

        # Generate unique token
        token = secrets.token_urlsafe(32)

        # Check token uniqueness (retry if collision)
        max_retries = 5
        existing = None
        for attempt in range(max_retries):
            existing = await self.db.fetchone(
                "SELECT uuid FROM anonymous_link WHERE token = $1",
                token
            )
            if not existing:
                break
            token = secrets.token_urlsafe(32)

        if existing and attempt == max_retries - 1:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail="Failed to generate unique token"
            )

        # Construct full URL
        full_url = f"{self.url.rstrip('/')}/{token}"

        # Save to database
        await self.db.fetchone(
            """INSERT INTO anonymous_link
               (url, token, entity, partition_uuid, expires_at, created_by)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING uuid, created""",
            self.url,
            token,
            self.entity_uuid,
            self.partition_uuid,
            expires_at,
            self.actor.uuid
        )

        # Return data directly (FastAPI style)
        return {
            "url": full_url,
            "token": token,
            "entity_uuid": self.entity_uuid,
            "partition_uuid": self.partition_uuid,
            "expires_at": expires_at.isoformat()
        }


class AnonymousLinkListAction:
    """
    Action to list all anonymous links for a specific entity.
    """

    def __init__(
        self,
        entity_uuid: str,
        request: Request,
        db: AsyncDatabaseAdapter
    ):
        self.entity_uuid = entity_uuid
        self.request = request
        self.db = db

    async def execute(self):
        """
        List anonymous links flow:
        1. Get current authenticated actor
        2. Query all links for the entity
        3. Format and return list
        """
        # Get current authenticated actor from request.state (set by @token_required)
        self.actor = getattr(self.request.state, "actor", None)
        if not self.actor:
            raise Forbidden(description="Authentication required")

        # Query links
        links = await self.db.fetchall(
            """SELECT uuid, url, token, entity, partition_uuid,
                      expires_at, created, created_by
               FROM anonymous_link
               WHERE entity = $1
               ORDER BY created DESC""",
            self.entity_uuid
        )

        # Format response
        result = []
        for link in links:
            result.append({
                "uuid": str(link["uuid"]),
                "url": link["url"],
                "token": link["token"],
                "full_url": f"{link['url'].rstrip('/')}/{link['token']}",
                "entity_uuid": str(link["entity"]),
                "partition_uuid": str(link["partition_uuid"]),
                "expires_at": link["expires_at"].isoformat() if link["expires_at"] else None,
                "created": link["created"].isoformat() if link["created"] else None,
                "created_by": str(link["created_by"]) if link["created_by"] else None,
                "is_expired": link["expires_at"] and link["expires_at"] < datetime.now(link["expires_at"].tzinfo)
            })

        # Return data directly (FastAPI style)
        return {
            "links": result,
            "count": len(result)
        }


