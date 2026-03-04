from fastapi import Request

from ...core.utils import create_response_message, hash_md5, json_dumps
from ..actor import Actor
from ..database.async_manager import AsyncDatabaseAdapter
from ..utils import get_current_actor, logging_message


class UpdateProfileAction:
    def __init__(self, db: AsyncDatabaseAdapter, data: dict, request: Request) -> None:
        self.db: AsyncDatabaseAdapter = db
        self.request: Request = request
        self.data = data
        self.error = False
        self.response = create_response_message(message="Profile successfully updated")
        self.status_code = 200

    async def execute(self) -> tuple[dict, int]:
        self.actor = await get_current_actor(self.db, self.request)
        self.hash_password()
        await self.execute_query()
        self.check_error()
        return self.response, self.status_code

    def hash_password(self) -> None:
        password: str = self.data["password"]
        if password.strip():
            self.data["password"] = hash_md5(password)
        else:
            self.data.pop("password")

    async def execute_query(self):
        try:
            query = """UPDATE actor SET uinfo=uinfo || $1 WHERE uuid=$2"""
            values = [self.data, self.actor.uuid]
            await self.db.execute(query, *values)
        except Exception as e:
            logging_message(self.request, f"Exception on updating profile! {e}")
            self.error = True

    def check_error(self):
        if self.error:
            self.response = create_response_message(
                message="Some error occurred while profile updating.", error=True
            )
            self.status_code = 400


class UpdateActorAction:
    def __init__(
        self, request: Request, db: AsyncDatabaseAdapter, data: dict, uuid: str
    ) -> None:
        self.request: Request = request
        self.db: AsyncDatabaseAdapter = db
        self.uuid: str = uuid
        self.data = data
        self.error = False
        self.queries: list[tuple[str, list]] = []
        self.response = create_response_message(message="Actor successfully updated")
        self.status_code = 200

    async def execute(self) -> tuple[dict, int]:
        self.actor = await Actor.objects.get(self.request, self.db, uuid=self.uuid)
        self.select_query()
        await self.execute_query()
        self.check_error()
        return self.response, self.status_code

    def select_query(self) -> None:
        if self.actor.actor_type in ["classic_user", "user"]:
            self.hash_password()
            self.queries = [
                (
                    "UPDATE actor SET uinfo = uinfo || $1::jsonb WHERE uuid = $2::uuid",
                    [self.data, self.actor.uuid],
                )
            ]
            return

        if self.actor.actor_type == "group":
            users = self.data.get("users") or []
            # Ensure users is a list[str]
            if isinstance(users, tuple):
                users = list(users)

            group_meta_json = json_dumps(
                {
                    "group_name": self.data.get("group_name"),
                    "weight": self.data.get("weight"),
                    "description": self.data.get("description"),
                }
            )

            if not users:
                self.queries = [
                    (
                        """UPDATE actor
                           SET uinfo = jsonb_set(uinfo, '{groups}', (uinfo->'groups') - $1::text)
                           WHERE actor_type IN ('user', 'classic_user')""",
                        [self.actor.uuid],
                    ),
                    (
                        """UPDATE actor
                           SET uinfo = uinfo || $1::jsonb
                           WHERE uuid = $2::uuid""",
                        [group_meta_json, self.actor.uuid],
                    ),
                ]
            else:
                self.queries = [
                    (
                        """UPDATE actor
                           SET uinfo = jsonb_set(
                               uinfo,
                               '{groups}',
                               (uinfo->'groups') || $1::jsonb
                           )
                           WHERE actor_type IN ('user', 'classic_user')
                             AND NOT (uinfo->'groups') @> $2::jsonb
                             AND uuid = ANY($3::uuid[])""",
                        [
                            [self.actor.uuid],
                            [self.actor.uuid],
                            users,
                        ],
                    ),
                    (
                        """UPDATE actor
                           SET uinfo = jsonb_set(
                               uinfo,
                               '{groups}',
                               (uinfo->'groups') - $1::text
                           )
                           WHERE actor_type IN ('user', 'classic_user')
                             AND uuid <> ALL($2::uuid[])""",
                        [self.actor.uuid, users],
                    ),
                    (
                        """UPDATE actor
                           SET uinfo = uinfo || $1::jsonb
                           WHERE uuid = $2::uuid""",
                        [group_meta_json, self.actor.uuid],
                    ),
                ]

    def hash_password(self) -> None:
        pwd = self.data.get("password", "")
        if isinstance(pwd, str) and pwd.strip():
            self.data["password"] = hash_md5(pwd)
        else:
            self.data.pop("password", None)

    async def execute_query(self) -> None:
        try:
            async with self.db.connection.transaction():
                for query, values in self.queries:
                    await self.db.execute(query, *values)
        except Exception as e:
            logging_message(self.request, f"Exception on updating actor! {e}")
            self.error = True

    def check_error(self) -> None:
        if self.error:
            self.response = create_response_message(
                message="Some error occurred while actor updating.", error=True
            )
            self.status_code = 400
