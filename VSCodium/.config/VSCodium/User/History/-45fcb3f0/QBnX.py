from typing import Optional, Union, Literal

from fastapi import UploadFile, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator, StrictBool, StrictInt

from service54.settings import ENTITY_LIMIT
from service54.core.dependencies import check_request_type, ValidateBodyDependency
from service54.core.base_validators import CustomValidate, SearchData
from service54.core.datatypes import UUID, SingleUploadFile


class EntityCreateValidator(BaseModel):

    parent: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Parent of the entity",
    )
    entity_type: str = Field(
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
        ],
        description="Entity type",
    )
    actor: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Actor UUID",
    )
    owner: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Owner UUID",
    )
    params: Optional[Union[list, dict]] = Field(
        default={},
        examples=[
            {"name": "Project 2"},
            {"name": "Project 1"},
            [{"name": "Project 1"}, {"name": "Project 2"}],
        ],
        description="Entity parameters",
    )
    params_validate: Optional[dict] = Field(
        default={},
        examples=[
            {"lifeTime": "date"},
            {"lifeTime": "time"},
            {"lifeTime": "datetime"},
        ],
        description="Optional validation of entity date fields. "
        "There are 3 data types to validate: date, time and datetime.",
    )
    file_params: Optional[str] = Field(
        default=None,
        examples=[
            {"1": "{'key': 'value'}", "3": "{'key': 'value'}"},
        ],
        description="File parameters in json. Key - is position of the file in files list, starts from 0.",
    )
    file: Optional[Union[list[UploadFile], SingleUploadFile]] = Field(
        default=None,
        description="Single file or an array of files",
    )

    @field_validator("params_validate")
    def check_params(cls, v, values):
        for k, v in v.items():
            params = values.data.get("params")
            CustomValidate(params.get(k), v)
        return v

    @classmethod
    def as_unknown_source(
        cls,
        data=Depends(check_request_type),
    ):
        return cls(
            parent=data.get("parent"),
            entity_type=data.get("entity_type"),
            actor=data.get("actor"),
            owner=data.get("owner"),
            params=data.get("params", {}),
            params_validate=data.get("params_validate", {}),
            files=data.get("files"),
        )


class EntityReadUnlimitedValidator(BaseModel):

    entity_uuid: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    entity_uuids: Optional[list[UUID]] = Field(
        default=None,
        examples=[
            [
                "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
                "bb260a18-36b2-4b42-b424-841a712edcac",
            ],
            [
                "1baef474-8737-402b-aa5a-3b91cba4d736",
                "2af819ee-6948-4354-be21-1b01e8082750",
                "4357df37-910a-4c05-a24f-6e4dea3c9e0a",
            ],
        ],
        description="Array of entity UUIDs to include",
    )

    @field_validator("entity_uuids")
    def check_not_both_uuid(cls, v, values):
        if values.data.get("entity_uuid") and v is not None:
            raise HTTPException(status_code=422, detail="Use only one field entity_uuid or entity_uuids")
        return v

    @model_validator(mode="before")
    def check_uuid(values):
        if not values.get("entity_uuid") and not values.get("entity_uuids"):
            raise HTTPException(status_code=422, detail="No entity uuid specified")
        return values


class EntityReadValidator(EntityReadUnlimitedValidator):

    entity_uuids: Optional[list[UUID]] = Field(
        default=None,
        examples=[
            [
                "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
                "bb260a18-36b2-4b42-b424-841a712edcac",
            ],
            [
                "1baef474-8737-402b-aa5a-3b91cba4d736",
                "2af819ee-6948-4354-be21-1b01e8082750",
                "4357df37-910a-4c05-a24f-6e4dea3c9e0a",
            ],
        ],
        description="Array of entity UUIDs to include",
        max_items=ENTITY_LIMIT,
    )
    with_files: Optional[bool] = Field(
        default=False,
        examples=[True, False],
        description="Is entity with files",
    )
    only_files: Optional[bool] = Field(
        default=False,
        examples=[True, False],
        description="Is entity with files only",
    )


class EntityReadPartialValidator(EntityReadValidator):

    fields: Optional[dict] = Field(
        default={},
        examples=[
            {"actor": "actor", "owner": "owner"},
            {"owner.uinfo": "owner_uinfo", "entity.created": "created"},
        ],
        description="Fields to query on. Map key - name of the field in the db, value - alias for the db",
    )
    params_fields: Optional[dict] = Field(
        default={},
        examples=[
            {"text": "some text alias", "title": "some alias"},
            {"status": "status alias", "lifeTime": "some alias"},
        ],
        description="Query the entity params. Map key is the attribute name in affix.params, value - alias for it",
    )


class EntityUpdateValidator(EntityReadValidator):

    params: Optional[dict] = Field(
        default=None,
        examples=[
            {"name": "Project 3", "key": "value"},
        ],
        description="Entity parameters",
    )
    file_params: Optional[str] = Field(
        default=None,
        examples=[
            {"1": "{'key': 'value'}", "3": "{'key': 'value'}"},
        ],
        description="File parameters in json. Key - is position of the file in files list, starts from 0.",
    )
    entity_type: Optional[str] = Field(
        default=None,
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
        ],
        description="Entity type",
    )
    parent: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Parent of the entity",
    )
    file: Optional[Union[list[UploadFile], SingleUploadFile]] = Field(
        default=None,
        description="Single file or an array of affix files",
    )
    params_validate: Optional[dict] = Field(
        default={},
        examples=[
            {"lifeTime": "date"},
            {"lifeTime": "time"},
            {"lifeTime": "datetime"},
        ],
        description="Optional validation of entity date fields. "
        "There are 3 data types to validate: date, time and datetime.",
    )
    actor: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Actor UUID",
    )
    with_files: Optional[bool] = Field(
        default=True,
        examples=[True, False],
        description="Is entity with files",
    )

    @model_validator(mode="before")
    def check_if_values_specified(v):
        if not (v.get("params") or v.get("entity_type") or v.get("parent") or v.get("files") or v.get("actor")):
            raise HTTPException(status_code=422, detail="No update values specified")
        return v

    @field_validator("params_validate")
    def check_params(cls, v, values):
        for k, v in v.items():
            params = values.data.get("params")
            CustomValidate(params.get(k), v)
        return v

    @classmethod
    def as_unknown_source(cls, data=Depends(check_request_type)):
        return cls(
            params=data.get("params", {}),
            entity_type=data.get("entity_type"),
            parent=data.get("parent"),
            files=data.get("files"),
            params_validate=data.get("params_validate", {}),
            actor=data.get("actor", {}),
            with_files=data.get("with_files"),
            entity_uuid=data.get("entity_uuid"),
            entity_uuids=data.get("entity_uuids"),
            only_files=data.get("only_files"),
        )


class EntityDeleteValidator(EntityReadValidator):
    pass


class EntitySetValidator(EntityReadValidator):

    owner: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Owner UUID",
    )
    actor: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Actor UUID",
    )
    creator_perms: Optional[
        dict[Literal["create", "read", "update", "delete", "list", "set", "affix_creator_delete"], StrictBool]
    ] = Field(
        default=None,
        examples=[
            {
                "create": True,
                "read": True,
                "update": False,
                "delete": True,
                "list": True,
                "set": True,
                "affix_creator_delete": True,
            }
        ],
        description="Creator permissions",
    )

    @model_validator(mode="before")
    def check_owner_or_creator_perms(values):
        if not ("owner" in values or "creator_perms" in values or "actor" in values):
            raise HTTPException(status_code=422, detail="No set values specified")
        return values


class EntityListUnlimitedValidator(BaseModel):

    parent: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Parent of the entity",
    )
    entity_type: Optional[Union[str, list]] = Field(
        default=None,
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
            ["ProjectEntity", "SomeTypeEntity"],
        ],
        description="Entity type or an array of entity types",
    )
    entity_type__not: Optional[Union[str, list]] = Field(
        default=None,
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
            ["ProjectEntity", "SomeTypeEntity"],
        ],
        description="Is not a type or entity type not in array of entity types",
    )
    actor: Optional[Union[UUID, list[UUID]]] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            ["1baef474-8737-402b-aa5a-3b91cba4d736", "bb260a18-36b2-4b42-b424-841a712edcac"],
        ],
        description="Actor UUID or an array of actor UUIDs",
    )
    params: Optional[dict] = Field(
        default={},
        examples=[
            {"name": "Project 3", "key": "value"},
        ],
        description="Entity parameters",
    )
    depth: Optional[StrictInt] = Field(
        default=1,
        examples=[2, 3, 4],
        description="Search depth",
    )
    limit: Optional[int] = Field(
        default=ENTITY_LIMIT,
        examples=[25, 50, 100],
        description="Limit number of returned records",
    )
    offset: Optional[int] = Field(
        default=None,
        examples=[25, 50, 100],
        description="Skip first N records",
    )
    entities: Optional[list[UUID]] = Field(
        default=None,
        examples=[
            ["1baef474-8737-402b-aa5a-3b91cba4d736", "bb260a18-36b2-4b42-b424-841a712edcac"],
            ["ea60b9f4-e7ed-4d11-86e4-dec41c660733"],
        ],
        description="An array of entity UUIDs",
    )
    entities__not: Optional[list[UUID]] = Field(
        default=None,
        examples=[
            ["1baef474-8737-402b-aa5a-3b91cba4d736", "bb260a18-36b2-4b42-b424-841a712edcac"],
            ["ea60b9f4-e7ed-4d11-86e4-dec41c660733"],
        ],
        description="Entity UUID is not in array UUIDs",
    )
    entity_uuids__not: Optional[list[UUID]] = Field(
        default=None,
        examples=[
            ["1baef474-8737-402b-aa5a-3b91cba4d736", "bb260a18-36b2-4b42-b424-841a712edcac"],
            ["ea60b9f4-e7ed-4d11-86e4-dec41c660733"],
        ],
        description="Entity UUID is not in array UUIDs",
    )
    created__lte: Optional[str] = Field(
        default=None,
        description="Creation date is less than or equal to query parameter",
    )
    created__gte: Optional[str] = Field(
        default=None,
        description="Creation date is greater than or equal to query parameter",
    )
    created__lt: Optional[str] = Field(
        default=None,
        description="Creation date less than query parameter",
    )
    created__gt: Optional[str] = Field(
        default=None,
        description="Creation date is greater than query parameter",
    )
    modified__lte: Optional[str] = Field(
        default=None,
        description="Modified date is less than or equal to query parameter",
    )
    modified__gte: Optional[str] = Field(
        default=None,
        description="Modified date is greater than or equal to query parameter",
    )
    modified__lt: Optional[str] = Field(
        default=None,
        description="Modified date is less than query parameter",
    )
    modified__gt: Optional[str] = Field(
        default=None,
        description="Modified date is greater than query parameter",
    )
    order: Optional[Literal["asc", "desc"]] = Field(
        default="desc",
        examples=["asc", "desc"],
        description="Sort query in ascending or descending order",
    )
    order_by: Optional[str] = Field(
        default="created",
        examples=["created", "modified", "entity_type"],
        description="Order query by field",
    )
    order_by_params: Optional[str] = Field(
        default=None,
        examples=["name", "key"],
        description="Order query by params",
    )
    search_data: Optional[SearchData] = Field(
        default=None,
        examples=[
            {"fields": {"params": ["name"]}, "value": "name search"},
            {"fields": {"params": ["key"]}, "value": "key search"},
        ],
        description="Search for an entity by params field",
    )
    owner: Optional[Union[UUID, list[UUID]]] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            ["bb260a18-36b2-4b42-b424-841a712edcac", "56c5fd1d-65af-4fe9-b1a2-d8210c870468"],
        ],
        description="Owner of an entity",
    )
    owner__not: Optional[Union[UUID, list[UUID]]] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            ["bb260a18-36b2-4b42-b424-841a712edcac", "56c5fd1d-65af-4fe9-b1a2-d8210c870468"],
        ],
        description="Is not the owner of an entity",
    )
    uinfo: Optional[dict] = Field(
        default={},
        examples=[
            {"uinfo": {"groups": ["dd909964-086c-4a81-8daf-34037c0bf544"]}},
        ],
        description="Actor uinfo",
    )


class EntityListValidator(EntityListUnlimitedValidator):

    limit: Optional[int] = Field(
        default=ENTITY_LIMIT,
        examples=[25, 50, 100],
        description="Limit number of returned records",
        le=ENTITY_LIMIT,
        gt=0,
    )


class EntityUpdateCleanValidator(BaseModel):

    entity_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    params: Optional[dict] = Field(
        default=None,
        examples=[
            {"name": "Project 3", "key": "value"},
        ],
        description="Entity parameters",
    )
    file: Optional[Union[list[UUID], UUID]] = Field(
        default=None,
        description="Single file UUID or an array of entity file UUIDs",
    )
    entity_type: Optional[str] = Field(
        default=None,
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
        ],
        description="Entity type",
    )
    parent: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Parent of the entity",
    )
    with_files: Optional[bool] = Field(
        default=True,
        examples=[True, False],
        description="Is entity with files",
    )

    @model_validator(mode="before")
    def check_if_values_specified(v):
        if not ("params" in v or "entity_type" in v or "parent" in v or "filesd" in v):
            raise HTTPException(status_code=422, detail="No update values specified")
        return v


class EntityUniqueCheckValidator(BaseModel):

    key: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Unique key of an entity",
    )
    parent: Optional[UUID] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Parent of the entity",
    )
    entity_type: str = Field(
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
        ],
        description="Entity type",
    )
    params: Optional[dict] = Field(
        default={},
        examples=[
            {"name": "Project 3", "key": "value"},
        ],
        description="Entity parameters",
    )


class EntityCountValidator(BaseModel):

    parent: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Parent of the entity",
    )
    entity_type: Union[str, list] = Field(
        examples=[
            "ProjectEntity",
            "SomeTypeEntity",
            ["ProjectEntity", "SomeTypeEntity"],
        ],
        description="Entity type or an array of entity types",
    )
    params: Optional[dict] = Field(
        default=None,
        examples=[
            {"name": "Project 3", "key": "value"},
        ],
        description="Entity parameters",
    )


class EntityUniqueCleanValidator(BaseModel):

    entity_uuid: Optional[Union[list[UUID], UUID]] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            ["bb260a18-36b2-4b42-b424-841a712edcac", "56c5fd1d-65af-4fe9-b1a2-d8210c870468"],
        ],
        description="Entity UUID",
    )
    key: Optional[Union[list[UUID], UUID]] = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            ["bb260a18-36b2-4b42-b424-841a712edcac", "56c5fd1d-65af-4fe9-b1a2-d8210c870468"],
        ],
        description="Unique key or array of unique keys of an entity",
    )

    @model_validator(mode="before")
    def check_if_both_uuid(v):
        if v.get("entity_uuid") and v.get("key"):
            raise HTTPException(status_code=422, detail="Use only one type entity_uuid or key")
        return v


class EntityOptionalDataReadValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    keys: list[str] = Field(
        examples=[
            ["states", "patches"],
        ],
        description="Array of unique keys of an entity",
    )
    limit: Optional[int] = Field(
        default=0,
        examples=[25, 50, 100],
        description="Limit number of returned records",
    )
    offset: Optional[int] = Field(
        default=0,
        examples=[25, 50, 100],
        description="Skip first N records",
    )


class EntityOptionalDataUpdateValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    data: dict = Field(description="Optional data for an entity")


class EntityOptionalDataStateReadValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    state_id: Union[str, int] = Field(description="State id")
    keys: list[str] = Field(description="Array of keys")


class EntityOptionalDataPatchReadValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    state_id: Union[str, int] = Field(description="State id")
    patch_id: Union[str, list[str]] = Field(description="Patch id")
    keys: list[str] = Field(description="Array of keys")


class EntityOptionalDataStateLatestValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )


class EntityOptionalDataStateUpdateValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    state_id: Union[str, int] = Field(description="State id")
    data: dict = Field(description="Optional data for an entity")


class EntityOptionalDataPatchUpdateValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    state_id: Union[str, int] = Field(description="State id")
    patch_id: str = Field(description="Patch id")
    data: dict = Field(description="Optional data for an entity")


class EntityOptionalDataStatesDropValidator(BaseModel):

    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )


class EntityCreateFilesValidator(BaseModel):
    entity_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    file_params: Optional[str] = Field(
        default=None,
        examples=[
            {"1": "{'key': 'value'}", "3": "{'key': 'value'}"},
        ],
        description="File parameters in json. Key - is position of the file in files list, starts from 0.",
    )
    files: Optional[Union[list[UploadFile], SingleUploadFile]] = Field(
        default=None,
        description="Single file or an array of affix files",
    )


class EntityReadFilesValidator(BaseModel):
    entity_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    match_params: Optional[dict] = Field(
        default=None,
        examples=[{"preview": True}, {"preview": True, "source_uuid": "36993240-ab29-436c-8fcc-d455c551ed87"}],
        description="Get files by params",
    )


class EntityReadFileValidator(BaseModel):
    entity_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="Entity UUID",
    )
    file_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="File UUID",
    )

class EntityReadPartialFileValidator(EntityReadPartialValidator):

    file_uuids: Optional[list[UUID]] = Field(
        default=[],
        examples=[
            [
                "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
                "bb260a18-36b2-4b42-b424-841a712edcac",
            ]
        ],
        description="Entity files UUIDs"
    )
    filter_data: Optional[SearchData] = Field(
        default=None,
        examples=[
            {"fields": {"params": ["name"]}, "value": "name search"},
            {"fields": {"params": ["key"]}, "value": "key search"},
        ],
        description="Filter files by base or params field",
    )
    limit: Optional[int] = Field(
        default=0,
        examples=[25, 50, 100],
        description="Limit number of returned records",
    )
    offset: Optional[int] = Field(
        default=0,
        examples=[25, 50, 100],
        description="Skip first N records",
    )
    order: Optional[Literal["asc", "desc"]] = Field(
        default="desc",
        examples=["asc", "desc"],
        description="Sort query in ascending or descending order",
    )
    order_by: Optional[str] = Field(
        default="created",
        examples=["created", "modified"],
        description="Order query by field",
    )


class EntityBackupCreateValidator(BaseModel):
    entity_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="UUID of the entity backup",
    )

class EntityBackupReadValidator(BaseModel):
    backup_uuid: UUID = Field(
        default=None,
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
            "1baef474-8737-402b-aa5a-3b91cba4d736",
        ],
        description="UUID of the entity backup",
    )

# Anonymous link validators
class AnonymousLinkCreateValidator(BaseModel):
    url: str = Field(
        examples=["https://w54.p3.54origins.com/share/"],
        description="Frontend URL base for share link",
    )
    entity_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
        ],
        description="Entity UUID to share",
    )
    expires_at: str = Field(
        examples=["2025-02-20T12:00:00Z", "2025-12-31T23:59:59Z"],
        description="Expiration datetime in ISO format",
    )


class AnonymousLinkListValidator(BaseModel):
    entity_uuid: UUID = Field(
        examples=[
            "56c5fd1d-65af-4fe9-b1a2-d8210c870468",
            "bb260a18-36b2-4b42-b424-841a712edcac",
        ],
        description="Entity UUID to get links for",
    )


# Response models for anonymous links
class AnonymousLinkResponse(BaseModel):
    uuid: str
    url: str
    token: str
    full_url: str
    entity_uuid: str
    partition_uuid: str
    expires_at: str
    created: str
    created_by: Optional[str]
    is_expired: bool


class AnonymousLinkListResponse(BaseModel):
    links: list[AnonymousLinkResponse]
    count: int


class AnonymousLinkCreatedResponse(BaseModel):
    url: str
    token: str
    entity_uuid: str
    partition_uuid: str
    expires_at: str


# create dependencies for endpoints that validating both file and data
validate_entity_creation = ValidateBodyDependency(EntityCreateValidator)
validate_anonymous_link_creation = ValidateBodyDependency(AnonymousLinkCreateValidator)
validate_entity_update = ValidateBodyDependency(EntityUpdateValidator)

validate_entity_update_clean = ValidateBodyDependency(EntityUpdateCleanValidator)
validate_entity_file_creation = ValidateBodyDependency(EntityCreateFilesValidator)
