import io
from decimal import Decimal
from typing import Optional

import PIL
from fastapi import Request
from fastapi_babel import _
from PIL import Image

from service54.actions.query.params import QueryParams
from service54.auth_perms.core.utils import create_response_message
from service54.auth_perms.fast_api.actor import Actor
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.utils import get_current_actor, get_session_token
from service54.core.exceptions import TableError
from service54.core.utils import check_perm


class EntityActionMixin:
    def __init__(self, request: Request, db: AsyncDatabaseAdapter):
        self.request: Request = request
        self.db: AsyncDatabaseAdapter = db
        self.actor = None
        self.entity_uuid = None
        self.entity_uuids__not = None
        self.affix_uuid = None
        self.perm_uuid = None
        self.entities = None
        self.entities__not = None
        self.files = None
        self.file_params = None
        self.params = None
        self.created__gte = None
        self.created__lte = None
        self.created__gt = None
        self.created__lt = None
        self.modified__gte = None
        self.modified__lte = None
        self.modified__gt = None
        self.modified__lt = None
        self.order = "DESC"
        self.order_by = None
        self.order_by_params = None
        self.limit = None
        self.offset = None
        self.entity_type = None
        self.entity_type__not = None
        self.actor_type = None
        self.actor_type__not = None
        self.result = []
        self.owner = None
        self.owner__not = None
        self.depth = 1
        self.search_data = {}
        self.partition = request.scope.get("partition")
        self.affix_entity_type__not = None
        self.uinfo = None

        if not self.partition:
            raise TableError()

    @staticmethod
    def create_thumbnail(file):
        if file.get("content_type").split("/")[0] == "image":
            try:
                image = Image.open(io.BytesIO(file.get("file")))
            except PIL.UnidentifiedImageError:
                return
            image.thumbnail((64, 64))
            thumbnail = io.BytesIO()
            image.save(thumbnail, format="PNG")
            return thumbnail.getvalue()

    async def check_perm(self, perm: str):
        self.actor = await get_current_actor(self.db, self.request)
        if self.actor:
            query = f"""
                    WITH
                        p_ltree AS (
                            SELECT
                                get_permitted_owner_ltree($1, $2) "owner",
                                get_permitted_creator_ltree($3, $4, $5) "creator",
                                get_permitted_actor_ltree($6, $7, $8) "actor"
                        )
                    SELECT
                        jsonb_agg(E.uuid ORDER BY ord) result
                    FROM
                        unnest($9::uuid[]) WITH ORDINALITY EL(uuid, ord)
                    JOIN
                        "entity_{self.partition}" E ON EL.uuid = E.uuid
                    WHERE
                    (
                        (SELECT ltree <@ owner FROM p_ltree)
                        OR
                        (SELECT ltree = ANY(creator) FROM p_ltree)
                        OR
                        (SELECT ltree <@ actor FROM p_ltree)
                    )
                    AND NOT actor = $10 OR $11 OR $12
                    """
            actor_is_admin = await self.actor.is_admin(self.request, self.db)
            params = [
                self.partition,  # $1
                self.actor.uuid,  # $2
                self.partition,  # $3
                self.actor.uuid,  # $4
                perm,  # $5
                self.partition,  # $6
                self.actor.uuid,  # $7
                perm,  # $8
                self.entity_uuid
                if isinstance(self.entity_uuid, list)
                else [self.entity_uuid],  # $9
                self.actor.uuid,  # $10
                self.actor.is_root(self.request),  # $11
                actor_is_admin
                and not self.request.scope.get("partition_secured", False),  # $12
            ]
            result = await self.db.fetchone(query, *params)
            return result.get("result") if result else None

    async def check_exist(self):
        if self.affix_uuid:
            table_name = f"affix_{self.partition}"
            uuid_val = self.affix_uuid
        elif self.perm_uuid:
            table_name = f"entity_{self.partition}_perms"
            uuid_val = self.perm_uuid
        elif self.entity_uuid:
            table_name = f"entity_{self.partition}"
            uuid_val = self.entity_uuid
        else:
            return False

        if isinstance(uuid_val, str):
            query = f'SELECT uuid FROM "{table_name}" WHERE uuid = $1'
            values = [uuid_val]
        else:
            query = f'SELECT uuid FROM "{table_name}" WHERE uuid = ANY($1::uuid[])'
            values = [uuid_val]

        result = await self.db.fetchall(query, *values)
        return result

    async def validate_files(self):
        """
        Validate files
        """
        data = list()
        if not self.files:
            return data
        for file in self.files:
            file_data = await file.read()
            if len(file_data) > 50 * (1024**2):
                response = create_response_message(
                    message=_(f"File {file.filename} is too large. Max size is 50 MB."),
                    error=True,
                )
                return response
            elif len(file.filename) > 128:
                response = create_response_message(
                    message=_(
                        f"File {file.filename} has too long name. Please rename it."
                    ),
                    error=True,
                )
                return response
            else:
                data.append(
                    {
                        "file": file_data,
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "content_length": len(file_data),
                    }
                )

        return data

    def construct_filter_query(
        self,
        table_name: str,
        qp: QueryParams,
        entity_properties=None,
        affix_properties=None,
    ):
        """
        Build SQL fragments for filtering entities/affixes.

        Contract:
        - This method ONLY builds:
          - WHERE fragment (without a leading 'AND'/'WHERE')
          - ORDER BY fragment (or empty string)
        - It NEVER builds LIMIT/OFFSET.
        - It NEVER returns a separate list of values; instead it appends values into `qp`
          and allocates placeholders via `qp.add(...)`.

        The caller is responsible for:
        - adding fixed query parameters before calling this method
        - applying LIMIT/OFFSET (using qp.add(value) for placeholders)
        """
        filters = []

        if self.depth:
            filters.append(
                f'nlevel(ltree) - (SELECT nlevel(ltree) FROM "entity_{self.partition}" WHERE uuid = {qp.add(self.entity_uuid)}::uuid) <= {qp.add(self.depth)}'
            )

        if self.entity_uuids__not:
            filters.append(
                f'NOT ("{table_name}".uuid = any({qp.add(self.entity_uuids__not)}::uuid[]))::boolean'
            )

        if self.entity_type:
            if isinstance(self.entity_type, list):
                filters.append(
                    f'"{table_name}"."entity_type" = ANY({qp.add(self.entity_type)})'
                )
            else:
                filters.append(
                    f'"{table_name}"."entity_type" = {qp.add(self.entity_type)}'
                )

        if self.entity_type__not:
            if isinstance(self.entity_type__not, list):
                filters.append(
                    f'NOT ltree <@ (SELECT COALESCE(array_agg(ltree), \'{{}}\') FROM "{table_name}" WHERE "entity_type" = ANY({qp.add(self.entity_type__not)}))'
                )
            else:
                filters.append(
                    f'NOT ltree <@ (SELECT COALESCE(array_agg(ltree), \'{{}}\') FROM "{table_name}" WHERE "entity_type" = {qp.add(self.entity_type__not)})'
                )

        if self.affix_entity_type__not:
            if isinstance(self.affix_entity_type__not, list):
                filters.append(
                    f'NOT "entity_type" = ANY({qp.add(self.affix_entity_type__not)})'
                )
            else:
                filters.append(
                    f'NOT "entity_type" = {qp.add(self.affix_entity_type__not)}'
                )

        if self.actor_type:
            if isinstance(self.actor_type, list):
                filters.append(f"actor.actor_type = ANY({qp.add(self.actor_type)})")
            else:
                filters.append(f"actor.actor_type = {qp.add(self.actor_type)}")

        if self.actor_type__not:
            if isinstance(self.actor_type__not, list):
                filters.append(
                    f"NOT actor.actor_type = ANY({qp.add(self.actor_type__not)})"
                )
            else:
                filters.append(
                    f"NOT actor.actor_type = {qp.add(self.actor_type__not)}"
                )

        if self.entities:
            filters.append(
                f'"{table_name}".ltree <@ ANY(SELECT ltree FROM "entity_{self.partition}" WHERE uuid = ANY({qp.add(self.entities)}::uuid[]))'
            )

        if self.entities__not:
            filters.append(
                f'NOT "{table_name}".ltree <@ ANY(SELECT ltree FROM "entity_{self.partition}" WHERE uuid = ANY({qp.add(self.entities__not)}::uuid[]))'
            )

        if self.owner:
            if isinstance(self.owner, list):
                filters.append(
                    f'"entity_{self.partition}"."owner"=ANY({qp.add(self.owner)}::uuid[])'
                )
            else:
                filters.append(
                    f'"entity_{self.partition}"."owner"={qp.add(self.owner)}'
                )

        if self.owner__not:
            if isinstance(self.owner__not, list):
                filters.append(
                    f'NOT "entity_{self.partition}"."owner"=ANY({qp.add(self.owner__not)}::uuid[])'
                )
            else:
                filters.append(
                    f'NOT "entity_{self.partition}"."owner"={qp.add(self.owner__not)}'
                )

        if entity_properties:
            for field, value in entity_properties.items():
                if isinstance(value, str):
                    filters.append(
                        f'"entity_{self.partition}"."{field}"={qp.add(value)}'
                    )
                elif isinstance(value, list):
                    filters.append(
                        f'"entity_{self.partition}"."{field}" = ANY({qp.add(value)})'
                    )

        if affix_properties:
            for field, value in affix_properties.items():
                if isinstance(value, str):
                    filters.append(f'"{table_name}"."{field}"={qp.add(value)}')
                elif isinstance(value, list):

                    if field.endswith("_uuid") or field in {"actor_uuid", "owner", "creator"}:
                        filters.append(
                            f'"{table_name}"."{field}" = ANY({qp.add(list(value))}::uuid[])'
                        )
                    else:
                        # Fallback for non-uuid lists: use ANY($n) without casting.
                        filters.append(
                            f'"{table_name}"."{field}" = ANY({qp.add(list(value))})'
                        )

        if self.params:
            for param, value in self.params.items():
                ph = qp.reserve()

                if param.endswith("__not"):
                    filters.append(" NOT ")
                    param = param[:-5]
                else:
                    filters.append(" ")

                # Param grander than
                if param.endswith("__gt"):
                    param = param[:-4]
                    if (
                        param.startswith("date_")
                        or param.endswith("_date")
                        or "date" == param
                    ):
                        filters[-1] += (
                            f"coalesce(to_timestamp(\"{table_name}\".params ->> '{param}', 'YYYY-MM-DD HH24:MI:SS') > to_timestamp({ph}, 'YYYY-MM-DD HH24:MI:SS'), false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    elif (
                        isinstance(value, int)
                        or isinstance(value, float)
                        or isinstance(value, Decimal)
                    ):
                        filters[-1] += (
                            f"coalesce((\"{table_name}\".params ->> '{param}')::decimal > ({ph})::decimal, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    else:
                        filters[-1] += (
                            f"coalesce(\"{table_name}\".params ->> '{param}' > {ph}, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)

                # Param less than
                elif param.endswith("__lt"):
                    param = param[:-4]
                    if (
                        param.startswith("date_")
                        or param.endswith("_date")
                        or "date" == param
                    ):
                        filters[-1] += (
                            f"coalesce(to_timestamp(\"{table_name}\".params ->> '{param}', 'YYYY-MM-DD HH24:MI:SS') < to_timestamp({ph}, 'YYYY-MM-DD HH24:MI:SS'), false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    elif (
                        isinstance(value, int)
                        or isinstance(value, float)
                        or isinstance(value, Decimal)
                    ):
                        filters[-1] += (
                            f"coalesce((\"{table_name}\".params ->> '{param}')::decimal < ({ph})::decimal, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    else:
                        filters[-1] += (
                            f"coalesce(\"{table_name}\".params ->> '{param}' < {ph}, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)

                # Param grander than equal
                elif param.endswith("__gte"):
                    param = param[:-5]
                    if (
                        param.startswith("date_")
                        or param.endswith("_date")
                        or "date" == param
                    ):
                        filters[-1] += (
                            f"coalesce(to_timestamp(\"{table_name}\".params ->> '{param}', 'YYYY-MM-DD HH24:MI:SS') >= to_timestamp({ph}, 'YYYY-MM-DD HH24:MI:SS'), false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    elif (
                        isinstance(value, int)
                        or isinstance(value, float)
                        or isinstance(value, Decimal)
                    ):
                        filters[-1] += (
                            f"coalesce((\"{table_name}\".params ->> '{param}')::decimal >= ({ph})::decimal, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    else:
                        filters[-1] += (
                            f"coalesce(\"{table_name}\".params ->> '{param}' >= {ph}, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)

                # Param less than equal
                elif param.endswith("__lte"):
                    param = param[:-5]
                    if (
                        param.startswith("date_")
                        or param.endswith("_date")
                        or "date" == param
                    ):
                        filters[-1] += (
                            f"coalesce(to_timestamp(\"{table_name}\".params ->> '{param}', 'YYYY-MM-DD HH24:MI:SS') <= to_timestamp({ph}, 'YYYY-MM-DD HH24:MI:SS'), false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    elif (
                        isinstance(value, int)
                        or isinstance(value, float)
                        or isinstance(value, Decimal)
                    ):
                        filters[-1] += (
                            f"coalesce((\"{table_name}\".params ->> '{param}')::decimal <= ({ph})::decimal, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)
                    else:
                        filters[-1] += (
                            f"coalesce(\"{table_name}\".params ->> '{param}' <= {ph}, false)"
                        )
                        qp.set_reserved(int(ph.replace('$', '')), value)

                # String param contains value anywhere in the string (not case-sensitive)
                elif param.endswith("__icontain"):
                    param = param[:-10]
                    filters[-1] += (
                        f"coalesce(\"{table_name}\".params ->> '{param}' ILIKE {ph}, false)"
                    )
                    qp.set_reserved(int(ph.replace('$', '')), f'%{value}%')

                # String param contains value anywhere in the string (case-sensitive)
                elif param.endswith("__contain"):
                    param = param[:-9]
                    filters[-1] += (
                        f"coalesce(\"{table_name}\".params ->> '{param}' LIKE {ph}, false)"
                    )
                    qp.set_reserved(int(ph.replace('$', '')), f'%{value}%')

                elif isinstance(value, list):
                    if value:
                        filters[-1] += (f"coalesce((\"{table_name}\".params -> '{param}')::jsonb ?| {ph}, false)")
                        qp.set_reserved(int(ph.replace('$', '')), list(value))
                    else:
                        filters[-1] += (
                            f"coalesce(\"{table_name}\".params -> '{param}' = '[]', true)"
                        )

                elif isinstance(value, bool):
                    filters[-1] += (
                        f"coalesce((\"{table_name}\".params->>'{param}')::boolean={ph}, false)"
                    )
                    qp.set_reserved(int(ph.replace('$', '')), value)

                elif (
                    isinstance(value, int)
                    or isinstance(value, float)
                    or isinstance(value, Decimal)
                ):
                    filters[-1] += (
                        f"coalesce((\"{table_name}\".params ->> '{param}')::decimal = ({ph})::decimal, false)"
                    )
                    qp.set_reserved(int(ph.replace('$', '')), value)

                else:
                    filters[-1] += (
                        f"\"{table_name}\".params ->> '{param}'={ph}"
                    )
                    qp.set_reserved(int(ph.replace('$', '')), value)

        if self.uinfo:
            for field, value in self.uinfo.items():
                if field.endswith("__not"):
                    filters.append(" NOT ")
                    field = field[:-5]
                else:
                    filters.append(" ")

                if isinstance(value, list):
                    if value:
                        # For uinfo json arrays, avoid `?| $n` (can produce syntax errors with bind params).
                        # Use jsonb_array_elements_text + ANY(text[]) instead.
                        placeholders = qp.add([str(v) for v in value])
                        exists_expr = f"""EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements_text(actor.uinfo -> '{field}') AS el(value)
                                WHERE el.value = ANY({placeholders}::text[])
                            )"""
                        filters[-1] += exists_expr
                    else:
                        filters[-1] += (
                            f"COALESCE(actor.uinfo -> '{field}' = '[]', true)"
                        )
                elif isinstance(value, bool):
                    filters[-1] += (
                        f"COALESCE((actor.uinfo ->> '{field}')::boolean = {qp.add(value)}, false)"
                    )
                else:
                    filters[-1] += (
                        f"COALESCE(actor.uinfo ->> '{field}' = {qp.add(value)}, false)"
                    )

        if self.created__gte:
            filters.append(
                f'"{table_name}"."created" >= to_timestamp({qp.add(self.created__gte)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.created__lte:
            filters.append(
                f'"{table_name}"."created" <= to_timestamp({qp.add(self.created__lte)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.created__gt:
            filters.append(
                f'"{table_name}"."created" > to_timestamp({qp.add(self.created__gt)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.created__lt:
            filters.append(
                f'"{table_name}"."created" < to_timestamp({qp.add(self.created__lt)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.modified__gte:
            filters.append(
                f'"{table_name}"."modified" >= to_timestamp({qp.add(self.modified__gte)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.modified__lte:
            filters.append(
                f'"{table_name}"."modified" <= to_timestamp({qp.add(self.modified__lte)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.modified__gt:
            filters.append(
                f'"{table_name}"."modified" > to_timestamp({qp.add(self.modified__gt)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.modified__lt:
            filters.append(
                f'"{table_name}"."modified" < to_timestamp({qp.add(self.modified__lt)}, \'YYYY-MM-DD HH24:MI:SS\')'
            )

        if self.search_data:
            actor_filters = []
            search_value = self.search_data.get("value", "")
            search_operator = (
                "ILIKE" if self.search_data.get("ignore_case", True) else "LIKE"
            )
            base_fields = self.search_data.get("fields", {}).get("base", [])
            uinfo_fields = self.search_data.get("fields", {}).get("uinfo", [])
            params_fields = self.search_data.get("fields", {}).get("params", [])
            owner_uinfo_fields = (
                self.search_data.get("fields", {}).get("owner_uinfo", [])
                if table_name.startswith("entity")
                else []
            )

            if base_fields or uinfo_fields or params_fields or owner_uinfo_fields:
                if "first_name" in uinfo_fields and "last_name" in uinfo_fields:
                    actor_filters.append(
                        f"CONCAT(actor.uinfo->>'first_name', ' ', actor.uinfo->>'last_name') {search_operator} {qp.add(f'%{search_value}%')}"
                    )

                if "first_name" in uinfo_fields and "last_name" in owner_uinfo_fields:
                    actor_filters.append(
                        f"CONCAT(actor.uinfo->>'first_name', ' ', actor.uinfo->>'last_name') {search_operator} {qp.add(f'%{search_value}%')}"
                    )

                for field in base_fields:
                    actor_filters.append(
                        f'"{field}"::varchar(255) {search_operator} {qp.add(f"%{search_value}%")}'
                    )

                for field in uinfo_fields:
                    actor_filters.append(
                        f"actor.uinfo ->> '{field}' {search_operator} {qp.add(f'%{search_value}%')}"
                    )

                for field in owner_uinfo_fields:
                    actor_filters.append(
                        f"owner.uinfo ->> '{field}' {search_operator} {qp.add(f'%{search_value}%')}"
                    )

                for field in params_fields:
                    actor_filters.append(
                        f"\"{table_name}\".params ->> '{field}' {search_operator} {qp.add(f'%{search_value}%')}"
                    )

                if actor_filters:
                    filters.append(f"({' OR '.join(actor_filters)})")

        filter_query_str = " AND ".join(filters)

        order_by_str = ""
        if self.order_by_params:
            order_by_str = f'ORDER BY "{table_name}".params->\'{self.order_by_params}\' {self.order}, "{table_name}".uuid'
        elif self.order_by:
            order_by_str = f'ORDER BY "{table_name}"."{self.order_by}" {self.order}, "{table_name}".uuid'

        # NOTE: pagination (LIMIT/OFFSET) is intentionally NOT handled here.
        return filter_query_str, "", "", "", order_by_str


class NotificationPermsMixin:
    # Leave here opportunity to pass None as db if used in background tasks and such things,
    # where we dont have access to the per-request db connection
    def __init__(self, request: Request, db: Optional[AsyncDatabaseAdapter] = None):
        self.request: Request = request
        self.db: AsyncDatabaseAdapter = db
        self.actor: Actor = request.state.actor
        self.limit = None
        self.offset = None
        self.chat_uuid = None
        self.chat_uuids = None
        self.message_uuid = None
        self.message_uuids = None
        self.owner_uuid = None
        self.owner_partition = None

    async def check_notification_perms(self, permission):
        """Check permission for notifications"""

        # query base to find the chat parent and partition it belongs to
        if self.chat_uuids is not None:
            chat_uuid = self.chat_uuids if isinstance(self.chat_uuids, list) else [self.chat_uuids]
        elif self.chat_uuid is not None:
            chat_uuid = self.chat_uuid if isinstance(self.chat_uuid, list) else [self.chat_uuid]
        else:
            chat_uuid = None

        # Normalize message_uuid and message_uuids into a single list
        if self.message_uuids is not None:
            message_uuid = self.message_uuids if isinstance(self.message_uuids, list) else [self.message_uuids]
        elif self.message_uuid is not None:
            message_uuid = self.message_uuid if isinstance(self.message_uuid, list) else [self.message_uuid]
        else:
            message_uuid = None

        # get all tables, that have a notification_channel foreign key
        # to find chat parent and his partition
        qp = QueryParams()

        if chat_uuid:
            chat_query = f"""JOIN notification_chat as nc
                            ON uuid = ANY({qp.add(chat_uuid)}::uuid[])"""
        else:
            chat_query = f"""
                JOIN notification_message as nm
                    ON nm.uuid = ANY({qp.add(message_uuid)}::uuid[])
                JOIN notification_chat as nc
                    ON nc.uuid = nm.chat_uuid
            """

        query = f"""
            SELECT DISTINCT la.attrelid::regclass AS referencing_table
            FROM pg_constraint AS c
                JOIN pg_index AS i
                    ON i.indexrelid = c.conindid
                JOIN pg_attribute AS la
                    ON la.attrelid = c.conrelid
                        AND la.attnum = c.conkey[1]
                JOIN pg_attribute AS ra
                    ON ra.attrelid = c.confrelid
                        AND ra.attnum = c.confkey[1]
                {chat_query}
            WHERE c.confrelid = 'notification_chat'::regclass
                AND c.contype = 'f'
                AND ra.attname = 'uuid'
                AND cardinality(c.confkey) = 1
                AND la.attname = 'notification_channel';
        """
        tables_records = await self.db.fetchall(query, *qp.args)
        tables = [record.get("referencing_table") for record in tables_records]
        if not tables:
            return True

        # compile query components
        qp = QueryParams()
        withs = []
        case_uuids = []
        case_partitions = []
        joins = []

        for i, table in enumerate(tables):
            table_quoted = f'"{table}"'
            partition_name = table.lstrip("entity_")

            if chat_uuid:
                withs.append(f"""{table_quoted} AS (
                    SELECT uuid, '{partition_name}' as partition
                    FROM {table_quoted}
                    WHERE notification_channel = ANY({qp.add(chat_uuid)}::uuid[])
                )""")
            else:
                withs.append(f"""{table_quoted} AS (
                    SELECT {table_quoted}.uuid, '{partition_name}' as partition
                    FROM {table_quoted}
                    JOIN notification_message as nm
                        ON nm.chat_uuid = {table_quoted}.notification_channel
                    WHERE nm.uuid = ANY({qp.add(message_uuid)}::uuid[])
                )""")

            case_uuids.append(f"WHEN {table_quoted}.uuid IS NOT NULL THEN {table_quoted}.uuid")
            case_partitions.append(f"WHEN {table_quoted}.partition IS NOT NULL THEN {table_quoted}.partition")
            joins.append(f"FULL JOIN {table_quoted} ON true" if i != 0 else table_quoted)

        # collect query
        query = (
            "WITH "
            + ", ".join(withs)
            + """
            SELECT CASE """
            + " ".join(case_uuids)
            + """
            END as uuid, CASE """
            + " ".join(case_partitions)
            + """
            END as partition
            FROM """
            + " ".join(joins)
        )
        try:
            result = await self.db.fetchone(query, *qp.args)
        except Exception:
            result = None

        self.owner_uuid, self.owner_partition = (
            result.values() if result else (None, None)
        )
        if self.owner_uuid and not await check_perm(
            self.request, self.db, permission, self.owner_partition, self.actor, self.owner_uuid
        ):
            return False

        # check permission
        if await self.actor.is_admin(self.request, self.db) or self.actor.is_root(
            self.request
        ):
            return True
        # chat has no owner, so no permissions to check
        return True
