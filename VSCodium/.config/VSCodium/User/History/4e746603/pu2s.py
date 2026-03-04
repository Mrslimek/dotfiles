from uuid import UUID

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi_babel import _
from fastapi_utils.cbv import cbv
from typing_extensions import Annotated

from service54.actions.anonymous_link_actions import (
    AnonymousLinkCreateAction,
    AnonymousLinkListAction,
)
from service54.actions.get_entity import EntityReadAction
from service54.auth_perms.core.utils import create_response_message
from service54.auth_perms.fast_api.exceptions import Forbidden
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.decorators import token_required
from service54.auth_perms.fast_api.dependencies import (
    get_db_connection_for_submodule,
    set_cross_origin_headers,
)
from service54.core.dependencies import share_token_dependency
from service54.core.validators.entity_validators import (
    AnonymousLinkCreateValidator,
)


router = APIRouter()


@cbv(router)
class AnonymousLinkCreate:
    """
    @POST Create anonymous share link@
    @POST_body_description
    Request parameters:
        url - Frontend URL base for share link (e.g., https://w54.p3.54origins.com/share/)
        entity_uuid - Entity UUID to share
        partition_uuid - Partition UUID of the entity
        expires_at - Expiration datetime in ISO format (e.g., 2025-02-20T12:00:00Z)
    @
    @POST_body_request
    {
        "url": "https://w54.p3.54origins.com/share/",
        "entity_uuid": "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
        "partition_uuid": "bb260a18-36b2-4b42-b424-841a712edcac",
        "expires_at": "2025-12-31T23:59:59Z"
    }
    @
    @POST_body_response
    {
        "url": "https://w54.p3.54origins.com/share/abc123...",
        "token": "abc123...",
        "entity_uuid": "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
        "partition_uuid": "bb260a18-36b2-4b42-b424-841a712edcac",
        "expires_at": "2025-12-31T23:59:59Z"
    }
    @
    """

    @router.post(
        "/share-link/create",
        dependencies=[Depends(set_cross_origin_headers)]
    )
    @token_required
    async def post(
        self,
        request: Request,
        data: AnonymousLinkCreateValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        Create anonymous share link view
        @flows Create anonymous share link view
        """
        print(data)
        result = await AnonymousLinkCreateAction(
            url=data.url,
            entity_uuid=data.entity_uuid,
            partition_uuid=data.partition_uuid,
            expires_at=data.expires_at,
            request=request,
            db=db
        ).execute()
        return JSONResponse(jsonable_encoder(result), status_code=200)


@cbv(router)
class AnonymousLinkList:
    """
    @GET List anonymous share links@
    @GET_body_description
    Query parameters:
        entity_uuid - Entity UUID to get links for
    @
    @GET_body_request
    GET /entity/share?entity_uuid=56c5fd1d-65af-4fe9-b1a2-d8210c870468
    @
    @GET_body_response
    {
        "links": [
            {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "url": "https://w54.p3.54origins.com/share/",
                "token": "abc123...",
                "full_url": "https://w54.p3.54origins.com/share/abc123...",
                "entity_uuid": "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
                "partition_uuid": "bb260a18-36b2-4b42-b424-841a712edcac",
                "expires_at": "2025-12-31T23:59:59Z",
                "created": "2024-11-26T13:25:32.612943",
                "created_by": "76715295-e362-4623-8efc-929ea661d5e9",
                "is_expired": false
            }
        ],
        "count": 1
    }
    @
    """

    @router.get(
        "/share-link/list",
        dependencies=[Depends(set_cross_origin_headers)]
    )
    @token_required
    async def get(
        self,
        request: Request,
        entity_uuid: Annotated[str, Query(description="Entity UUID to get links for")],
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        List anonymous share links view
        @flows List anonymous share links view
        """
        # Validate entity_uuid format
        try:
            validated_uuid = UUID(entity_uuid)
        except ValueError:
            response = create_response_message(
                message=_("Invalid entity_uuid format"),
                error=True
            )
            return JSONResponse(jsonable_encoder(response), status_code=400)

        result = await AnonymousLinkListAction(
            entity_uuid=str(validated_uuid),
            request=request,
            db=db
        ).execute()
        return JSONResponse(jsonable_encoder(result), status_code=200)


@cbv(router)
class EntityAnonymousRead:
    """
    @GET Read entity via anonymous share link@
    @GET_body_description
    Headers:
        Share-Token - Token from anonymous share link
    @
    @GET_body_request
    GET /entity/share
    Headers: Share-Token: abc123...
    @
    @GET_body_response
    {
        "partition": "project_management",
        "uuid": "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
        "created": "2024-11-26T13:25:32.612943",
        "modified": "2024-11-26T13:25:32.612943",
        "entity_type": "project",
        "actor": "76715295-e362-4623-8efc-929ea661d5e9",
        "parent": "a0267432-4cb1-4eb5-af99-9eb7c4aed496",
        "params": {
            "name": "Project 1"
        },
        "owner": "08ee8342-0b22-4611-86c6-1f7947884eee",
        "uinfo": {
            "email": "example@mail.ru",
            "first_name": "John",
            "last_name": "Doe",
            "groups": ["d0d53af4-eb05-4e1c-95f1-935ff453dc37"]
        },
        "owner_uinfo": {
            "service_name": "SERVICE_NAME",
            "service_domain": "SERVICE_DOMAIN"
        },
        "files": []
    }
    @
    """

    @router.get(
        "/share-link/entity",
        dependencies=[Depends(set_cross_origin_headers)]
    )
    async def get(
        self,
        request: Request,
        share_token: str = Depends(share_token_dependency),
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        Read entity via anonymous share link view
        @flows Read entity via anonymous share link view
        """
        # Reuse standard EntityReadAction query logic.
        # For anonymous share links, entity UUID and partition are derived from Share-Token
        # and stored in request.state by share_token_dependency.
        entity_uuid = getattr(request.state, "anonymous_link_entity", None)
        partition = getattr(request.state, "anonymous_link_partition", None)

        if not entity_uuid or not partition:
            raise Forbidden(description="Invalid anonymous link context")

        # Ensure EntityActionMixin uses the partition resolved from the share token.
        request.scope["partition"] = partition

        action = EntityReadAction({"entity_uuid": entity_uuid}, request=request, db=db)
        action.include_optional_data = True
        result = await action.execute()

        # EntityReadAction returns a list (EntityList). For share-read we expose a single entity.
        if isinstance(result, dict) and "results" in result:
            results = result.get("results") or []
            result = results[0] if results else {}
        elif isinstance(result, list):
            result = result[0] if result else {}

        return JSONResponse(jsonable_encoder(result), status_code=200)
