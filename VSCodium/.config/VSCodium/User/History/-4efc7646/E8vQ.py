from uuid import UUID

from fastapi import Request

from service54.actions import EntityActionMixin
from service54.actions.query.params import QueryParams
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.decorators import get_current_actor
from service54.auth_perms.fast_api.exceptions import Forbidden
from service54.core.datatypes import AffixList, AffixPartialList
from service54.core.exceptions import EntityNotFound


class AffixReadAction(EntityActionMixin):
    def __init__(self, data: dict, request: Request, db: AsyncDatabaseAdapter) -> None:
        super().__init__(request, db)
        affix_uuid = data.get("affix_uuid")
        affix_uuids = data.get("affix_uuids", [])
        self.affix_uuid: list[UUID] = [affix_uuid] if affix_uuid else affix_uuids
        self.with_files: bool = data.get("with_files", False)
        self.only_files: bool = data.get("only_files", False)

    async def validate(self):
        if not await self.check_perm():
            raise Forbidden

    async def execute(self) -> dict:
        """
        Affix read action
        @flow
        """
        if not await self.check_exist():
            raise EntityNotFound(message="There is no affix with such uuid")

        params = [self.affix_uuid]
        if self.with_files:
            query = f"""SELECT AF.*, A.uinfo, A2.uuid "owner", A2.uinfo owner_uinfo, array_agg(to_jsonb(AFF) ||
            jsonb_build_object('file', pencode_base64(AFF.file))) FILTER (WHERE AFF.uuid IS NOT NULL) files FROM "affix_{self.partition}" AF
            JOIN actor_entity_mirror A ON AF.actor_uuid = A.uuid LEFT JOIN "{self.partition}_files" AFF ON AFF.affix = AF.uuid JOIN "entity_{self.partition}" E ON
            AF.entity_uuid = E.uuid LEFT JOIN actor_entity_mirror A2 ON E.owner = A2.uuid WHERE AF.uuid = ANY($1::uuid[])
            GROUP BY AF.uuid, A.uinfo, A2.uuid, A2.uinfo ORDER BY array_position($1::uuid[], AF.uuid)"""
        elif self.only_files:
            query = f"""SELECT affix "uuid", jsonb_agg(to_jsonb(PF) - 'affix' || jsonb_build_object('file',
            pencode_base64(PF.file))) files FROM "{self.partition}_files" PF WHERE affix = ANY($1::uuid[]) GROUP BY affix;"""
        else:
            query = f"""SELECT AF.*, A.uinfo, A2.uuid "owner", A2.uinfo owner_uinfo, array_agg(to_jsonb(AFF) ||
            jsonb_build_object('file', pencode_base64(AFF.thumbnail))) FILTER (WHERE AFF.uuid IS NOT NULL) files FROM "affix_{self.partition}"
            AF JOIN actor_entity_mirror A ON AF.actor_uuid = A.uuid LEFT JOIN "{self.partition}_files" AFF ON AFF.affix = AF.uuid JOIN "entity_{self.partition}" E ON
            AF.entity_uuid = E.uuid LEFT JOIN actor_entity_mirror A2 ON E.owner = A2.uuid WHERE AF.uuid = ANY($1::uuid[])
            GROUP BY AF.uuid, A.uinfo, A2.uuid, A2.uinfo ORDER BY array_position($1::uuid[], AF.uuid)"""

        result = await self.db.fetchall(query, *params)
        affix = AffixList.model_validate(result)
        return affix.model_dump(exclude_none=True)

    async def check_perm(self, perm: str = "read") -> list[UUID]:
        if not self.actor:
            self.actor = await get_current_actor(self.db, self.request)

        if not self.actor:
            return []

        actor_is_admin = await self.actor.is_admin(self.request, self.db)
        qp = QueryParams()

        query = f"""
        WITH p_ltree AS (
            SELECT
                get_permitted_owner_ltree({qp.add(self.partition)}, {qp.add(self.actor.uuid)}) "owner",
                get_permitted_creator_ltree({qp.add(self.partition)}, {qp.add(self.actor.uuid)}, 'read') "creator",
                get_permitted_actor_ltree({qp.add(self.partition)}, {qp.add(self.actor.uuid)}, 'read') "actor"
        )
        SELECT jsonb_agg(AF.uuid ORDER BY ord) uuids
        FROM unnest({qp.add(self.affix_uuid if self.affix_uuid else [])}::uuid[]) WITH ORDINALITY EL(uuid, ord)
        JOIN "affix_{self.partition}" AF ON EL.uuid = AF.uuid
        JOIN "entity_{self.partition}" E ON AF.entity_uuid = E.uuid
        WHERE (SELECT ltree <@ owner FROM p_ltree)
           OR (SELECT ltree = ANY(creator) FROM p_ltree)
           OR (SELECT ltree <@ actor FROM p_ltree) AND NOT actor = {qp.add(self.actor.uuid)}
           OR {qp.add(self.actor.is_root(self.request))}
           OR {qp.add(actor_is_admin and not self.request.scope.get("partition_secured", False))}
        """

        result = await self.db.fetchone(query, *qp.args)
        if result:
            self.affix_uuid = result.get("uuids", [])
            return result.get("uuids", [])
        return []


class AffixReadPartialAction(AffixReadAction):
    def __init__(self, data: dict, request: Request, db: AsyncDatabaseAdapter) -> None:
        super().__init__(data, request, db)
        self.fields = data.get("fields", {})
        self.params_fields = data.get("params_fields", {})

    async def execute(self):
        fields_subquery = [
            f'{key} AS "{field_name}"' for key, field_name in self.fields.items()
        ]
        params_fields_subquery = [
            f"affix.params->'{field}' AS \"{field_name}\""
            for field, field_name in self.params_fields.items()
        ]

        all_fields = ", ".join(fields_subquery + params_fields_subquery)

        if self.only_files:
            query = f"""
            SELECT affix as uuid, jsonb_agg(to_jsonb(files_table) - 'affix' || jsonb_build_object(
                    'file', pencode_base64(files_table.file))
                ) "files"
            FROM "{self.partition}_files" files_table
            WHERE affix = ANY($1::uuid[])
            GROUP BY affix
            """
            params = [self.affix_uuid]
        else:
            file_or_thumbnail = (
                "files_table.file" if self.with_files else "files_table.thumbnail"
            )
            query = f"""
            SELECT {all_fields}, affix.uuid FROM "affix_{self.partition}" affix
            LEFT JOIN "entity_{self.partition}" entity ON affix.entity_uuid = entity.uuid
            LEFT JOIN actor_entity_mirror actor ON affix.actor_uuid = actor.uuid
            LEFT JOIN actor_entity_mirror owner ON entity.owner = owner.uuid
            LEFT JOIN (
                SELECT jsonb_agg(
                (to_jsonb(files_table.*) || jsonb_build_object('file', pencode_base64({file_or_thumbnail})))-'affix'
                ) files, affix
                FROM "{self.partition}_files" files_table
                WHERE affix IS NOT NULL
                GROUP BY affix
            ) files ON affix.uuid = files.affix
            WHERE affix.uuid = ANY($1::uuid[])
            ORDER BY array_position($1::uuid[], affix.uuid)
            """
            params = [self.affix_uuid]

        result = await self.db.fetchall(query, *params)
        affix = AffixPartialList.model_validate(result)
        return affix.model_dump(exclude_none=True)


class AffixListAction(EntityActionMixin):
    def __init__(self, data: dict, request: Request, db: AsyncDatabaseAdapter):
        super().__init__(request, db)
        self.entity_uuid = data.get("entity_uuid")
        self.affix_type = data.get("affix_type")
        self.actor_uuid = data.get("actor")
        self.params = data.get("params", {})
        self.limit = data.get("limit", self.request.app.config.get("ENTITY_LIMIT"))
        self.offset = data.get("offset")
        self.created__lte = data.get("created__lte")
        self.created__gte = data.get("created__gte")
        self.created__lt = data.get("created__lt")
        self.created__gt = data.get("created__gt")
        self.modified__lte = data.get("modified__lte")
        self.modified__gte = data.get("modified__gte")
        self.modified__lt = data.get("modified__lt")
        self.modified__gt = data.get("modified__gt")
        self.search_data = data.get("search_data")
        self.order = data.get("order", "desc")
        self.order_by = data.get("order_by", "created")
        self.order_by_params = data.get("order_by_params")
        self.depth = data.get("depth", 1)
        self.affix_entity_type__not = data.get("entity_type__not")
        self.owner = data.get("owner")
        self.owner__not = data.get("owner__not")
        self.permitted_affix_uuids = None

    async def validate(self):
        """
        Validate user has permissions and filter affix UUIDs.
        Called by standard endpoints before execute().
        """
        if not await self.check_perm("list"):
            raise Forbidden
        self.permitted_affix_uuids = await self._get_permitted_affix_uuids()

    async def _get_permitted_affix_uuids(self) -> list:
        """
        Get list of affix UUIDs that the actor has permission to access.
        This filters affixes based on owner/creator/actor ltree permissions.
        """
        if not self.actor:
            return []

        qp = QueryParams()
        actor_is_admin = await self.actor.is_admin(self.request, self.db)

        is_root = self.actor.is_root(self.request) if self.actor else False
        is_admin_unsecured = actor_is_admin and not self.request.scope.get("partition_secured", False)
        is_root_param = qp.add(is_root)
        is_admin_param = qp.add(is_admin_unsecured)
        
        query = f"""
        WITH p_ltree AS (
            SELECT
                get_permitted_owner_ltree({qp.add(self.partition)}, {qp.add(self.actor.uuid)}) "owner",
                get_permitted_creator_ltree({qp.add(self.partition)}, {qp.add(self.actor.uuid)}, 'read') "creator",
                get_permitted_actor_ltree({qp.add(self.partition)}, {qp.add(self.actor.uuid)}, 'read') "actor"
        )
        SELECT AF.uuid
        FROM "affix_{self.partition}" AF
        JOIN "entity_{self.partition}" E ON AF.entity_uuid = E.uuid
        WHERE E.uuid = {qp.add(self.entity_uuid)}
          AND (
              (E.ltree <@ (SELECT owner FROM p_ltree))
              OR (SELECT ltree = ANY(creator) FROM p_ltree WHERE ltree = E.ltree)
              OR (E.ltree <@ (SELECT actor FROM p_ltree) AND E.owner != {qp.add(self.actor.uuid)})
              OR {is_root_param}
              OR {is_admin_param}
          )
        """

        # Apply additional filters
        if self.affix_type:
            query += f" AND AF.affix_type = {qp.add(self.affix_type)}"
        if self.actor_uuid:
            query += f" AND AF.actor_uuid = {qp.add(self.actor_uuid)}"
        if self.params:
            for key, value in self.params.items():
                # Convert boolean to string for JSON comparison (->> returns text)
                param_value = 'true' if value is True else 'false' if value is False else value
                query += f" AND (AF.params->>{qp.add(key)} = {qp.add(param_value)})"

        result = await self.db.fetchall(query, *qp.args)
        return [row["uuid"] for row in result]

    async def execute(self) -> dict:
        """
        Affix list action - pure business logic for fetching affix data.
        @flow
        """
        if not await self.check_exist():
            raise EntityNotFound(message="There is no entity with such uuid")

        qp = QueryParams()

        # Build WHERE clause
        where_clauses = [f"AF.entity_uuid = {qp.add(self.entity_uuid)}"]
        
        # If permitted_affix_uuids is set (by validate()), filter by it
        # Otherwise, fetch all affixes for the entity (for share-links)
        if self.permitted_affix_uuids is not None:
            where_clauses.append(f"AF.uuid = ANY({qp.add(self.permitted_affix_uuids)}::uuid[])")

        if self.affix_type:
            where_clauses.append(f"AF.affix_type = {qp.add(self.affix_type)}")
        if self.actor_uuid:
            where_clauses.append(f"AF.actor_uuid = {qp.add(self.actor_uuid)}")
        if self.params:
            for key, value in self.params.items():
                # Convert boolean to string for JSON comparison (->> returns text)
                param_value = 'true' if value is True else 'false' if value is False else value
                where_clauses.append(f"(AF.params->>{qp.add(key)} = {qp.add(param_value)})")
        if self.created__lte:
            where_clauses.append(f"AF.created <= {qp.add(self.created__lte)}")
        if self.created__gte:
            where_clauses.append(f"AF.created >= {qp.add(self.created__gte)}")
        if self.created__lt:
            where_clauses.append(f"AF.created < {qp.add(self.created__lt)}")
        if self.created__gt:
            where_clauses.append(f"AF.created > {qp.add(self.created__gt)}")
        if self.modified__lte:
            where_clauses.append(f"AF.modified <= {qp.add(self.modified__lte)}")
        if self.modified__gte:
            where_clauses.append(f"AF.modified >= {qp.add(self.modified__gte)}")
        if self.modified__lt:
            where_clauses.append(f"AF.modified < {qp.add(self.modified__lt)}")
        if self.modified__gt:
            where_clauses.append(f"AF.modified > {qp.add(self.modified__gt)}")
        if self.owner:
            where_clauses.append(f"E.owner = {qp.add(self.owner)}")
        if self.owner__not:
            where_clauses.append(f"E.owner != {qp.add(self.owner__not)}")

        where_sql = f"WHERE {' AND '.join(where_clauses)}"

        # Order by
        order_by_sql = ""
        if self.order_by_params:
            order_by_sql = f"ORDER BY {self.order_by_params} {self.order}"
        else:
            order_by_sql = f"ORDER BY AF.created {self.order}"

        # Limit and offset
        limit_sql = ""
        if self.limit:
            limit_sql = f"LIMIT {self.limit}"
            if self.offset:
                limit_sql += f" OFFSET {self.offset}"

        # First, get total count
        count_query = f"""
        SELECT COUNT(*) as total
        FROM "affix_{self.partition}" AF
        JOIN "entity_{self.partition}" E ON AF.entity_uuid = E.uuid
        {where_sql}
        """
        count_result = await self.db.fetchone(count_query, *qp.args)
        total = count_result["total"] if count_result else 0

        # Then get paginated results
        query = f"""
        SELECT jsonb_agg(AF.uuid) as affix_uuids
        FROM (
            SELECT AF.uuid
            FROM "affix_{self.partition}" AF
            JOIN "entity_{self.partition}" E ON AF.entity_uuid = E.uuid
            {where_sql}
            {order_by_sql}
            {limit_sql}
        ) AF
        """

        result = await self.db.fetchone(query, *qp.args)
        affix_uuids = result.get("affix_uuids", []) if result else []
        print(result)
        print(affix_uuids)
        return {
            "affix_uuids": affix_uuids,
            "total": total
        }
