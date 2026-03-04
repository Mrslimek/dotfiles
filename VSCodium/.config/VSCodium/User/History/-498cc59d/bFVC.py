import logging
import secrets
from datetime import datetime, timedelta

from fastapi import Request, HTTPException

from service54.actions import EntityActionMixin
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.exceptions import Forbidden
from service54.core.exceptions import EntityNotFound
from service54.core.utils import get_partition

logger = logging.getLogger(__name__)


class AnonymousLinkCreateAction(EntityActionMixin):
    """
    Action to create an anonymous share link for an entity.

    TODO: CHECK WHO CAN CREATE ANONYMOUS LINKS - currently all authenticated users can create
    """

    def __init__(
        self,
        url: str,
        entity_uuid: str,
        partition_uuid: str,
        expires_at: str,
        request: Request,
        db: AsyncDatabaseAdapter
    ):
        self.url = url
        self.entity_uuid = entity_uuid
        self.partition_uuid = partition_uuid
        self.expires_at_str = expires_at
        self.request = request
        self.db = db

    async def execute(self):
        """
        Create anonymous link flow:
        1. Get current actor (authenticated user)
        2. Resolve partition and set context for EntityActionMixin
        3. Validate entity exists
        4. Validate expiration datetime
        5. Generate unique token
        6. Save to database
        7. Return link data
        """

        # Get current authenticated actor from request.state (set by @token_required)
        self.actor = getattr(self.request.state, "actor", None)
        if not self.actor:
            raise Forbidden(description="Authentication required")

        partition = await get_partition(self.partition_uuid, self.db)
        print(partition)
        if not partition:
            raise HTTPException(
                status_code=404,
                detail="Partition not found"
            )
        self.request.scope["partition"] = partition

        # Initialize EntityActionMixin after partition is set
        super().__init__(self.request, self.db)

        # Check if entity exists
        print(self.entity_uuid)
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


class EntityAnonymousOptionalDataReadAction:
    """
    Read optional_data from entity via anonymous share link.
    Similar to EntityOptionalDataReadAction but without permission checks.
    """

    def __init__(
        self,
        entity_uuid: str,
        keys: list,
        request: Request,
        db: AsyncDatabaseAdapter,
        limit: int = 0,
        offset: int = 0
    ):
        self.request = request
        self.db = db
        self.entity_uuid = entity_uuid
        self.keys = keys
        self.limit = limit
        self.offset = offset

        # Get partition from request.state (set by share_token_dependency)
        self.partition = getattr(request.state, "anonymous_link_partition", None)

    async def execute(self):
        """
        Read optional_data without permission checks.

        @flow
        """
        if not self.entity_uuid or not self.partition:
            logger.error("EntityAnonymousOptionalDataReadAction: entity_uuid or partition not found in request.state")
            raise Forbidden(description="Invalid anonymous link context")

        # Build dynamic columns for optional_data keys
        columns = ", ".join(
            [f"optional_data -> '{key}' AS \"{key}\"" for key in self.keys]
        )

        query = f"""
        SELECT
            {columns}
        FROM
            "entity_{self.partition}" entity
        WHERE
            entity.uuid = $1
        """

        result = await self.db.fetchone(query, self.entity_uuid)
        if not result:
            raise EntityNotFound(message="There is no entity with such uuid")

        # Apply pagination if needed
        if self.limit or self.offset:
            limit = self.limit or 1000
            end_idx = self.offset + limit

            paginated_result = {}
            for key, values in result.items():
                if values:
                    paginated_result[key] = values[self.offset : end_idx]
                else:
                    paginated_result[key] = values

            result = paginated_result

        return result


class EntityAnonymousOptionalDataStateReadAction:
    """
    Read state from optional_data via anonymous share link.
    Similar to EntityOptionalDataStateReadAction but without permission checks.
    """

    def __init__(
        self,
        entity_uuid: str,
        state_id: str,
        keys: list,
        request: Request,
        db: AsyncDatabaseAdapter
    ):
        self.request = request
        self.db = db
        self.entity_uuid = entity_uuid
        self.state_id = state_id
        self.keys = keys

        # Get partition from request.state (set by share_token_dependency)
        self.partition = getattr(request.state, "anonymous_link_partition", None)

    async def execute(self):
        """
        Read state from optional_data without permission checks.

        @flow
        """
        if not self.entity_uuid or not self.partition:
            logger.error("EntityAnonymousOptionalDataStateReadAction: entity_uuid or partition not found in request.state")
            raise Forbidden(description="Invalid anonymous link context")

        # Check if old or new structure
        is_old_structure_result = await self.db.fetchone(
            f"""SELECT
                    jsonb_typeof((optional_data::jsonb->>'states')::jsonb) = 'object' as new
                FROM entity_{self.partition}
                WHERE uuid = $1""",
            self.entity_uuid,
        )
        is_old_structure = (
            is_old_structure_result.get("new") if is_old_structure_result else False
        )

        if is_old_structure:
            # Old structure: states as object
            columns = ", ".join(
                [
                    f"optional_data -> 'states' -> $2::text -> '{key}' AS \"{key}\""
                    for key in self.keys
                ]
            )

            query = f"""
            SELECT
                {columns}
            FROM
                "entity_{self.partition}" entity
            WHERE
                entity.uuid = $1
            """
            result = await self.db.fetchone(query, self.entity_uuid, self.state_id)

            if not result:
                raise EntityNotFound(message="State not found")

            return result
        else:
            # New structure: states as array
            exclude_list_result = await self.db.fetchone(
                f"""SELECT optional_data #> '{{states, {self.state_id}, excluded_versions}}' as excluded_versions
                    FROM "entity_{self.partition}"
                    WHERE uuid = $1;""",
                self.entity_uuid,
            )
            exclude_list = (
                exclude_list_result.get("excluded_versions")
                if exclude_list_result
                else None
            )

            # Prepare filter statement to exclude versions from query
            exclude_conditions = ""
            if exclude_list:
                exclude_conditions += "WHERE " + " AND ".join(
                    f"(sub.rn < {exclude_tuple[0]} OR sub.rn > {exclude_tuple[1]})"
                    for exclude_tuple in exclude_list
                )

            # Get states that are not excluded
            query = f"""SELECT subq.state as state
                        FROM "entity_{self.partition}" entity
                        JOIN LATERAL
                            (
                                SELECT state
                                FROM (
                                    SELECT state, row_number() OVER () as rn
                                    FROM jsonb_array_elements(entity.optional_data -> 'states') as state
                                ) sub
                                {exclude_conditions}
                            ) subq ON true
                        WHERE
                        entity.uuid = $1"""

            query_result = await self.db.fetchall(query, self.entity_uuid)

            if not query_result:
                raise EntityNotFound(message="States not found")

            result = [state.get("state") for state in query_result]

            return result


class EntityAnonymousOptionalDataStateLatestAction:
    """
    Read latest state from optional_data via anonymous share link.
    Similar to EntityOptionalDataStateLatestAction but without permission checks.
    """

    def __init__(
        self,
        entity_uuid: str,
        request: Request,
        db: AsyncDatabaseAdapter
    ):
        self.request = request
        self.db = db
        self.entity_uuid = entity_uuid

        # Get partition from request.state (set by share_token_dependency)
        self.partition = getattr(request.state, "anonymous_link_partition", None)

    async def execute(self):
        """
        Read latest state from optional_data without permission checks.

        @flow
        """
        if not self.entity_uuid or not self.partition:
            logger.error("EntityAnonymousOptionalDataStateLatestAction: entity_uuid or partition not found in request.state")
            raise Forbidden(description="Invalid anonymous link context")

        query = f"""
        SELECT
            optional_data -> 'states' -> -1 as state
        FROM
            "entity_{self.partition}"
        WHERE
            uuid = $1
        """

        result = await self.db.fetchone(query, self.entity_uuid)

        if not result or not result.get("state"):
            raise EntityNotFound(message="No states found")

        return result.get("state")
