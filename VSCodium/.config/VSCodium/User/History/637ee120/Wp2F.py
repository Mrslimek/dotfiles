from typing import cast

from fastapi import Request

from service54.actions import NotificationPermsMixin
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.exceptions import Forbidden
from service54.core.validators.notification_validators import (
    MuteNotificationChatValidator,
    MuteMultipleNotificationChatsValidator,
)


class MuteNotificationChatAction(NotificationPermsMixin):
    """
    Action to mute or unmute a notification chat for a user.
    Updates the mute status in entity_users.params->'notifications'.
    """

    def __init__(
        self,
        data: MuteNotificationChatValidator,
        request: Request,
        db: AsyncDatabaseAdapter,
    ):
        super().__init__(request, db)
        self.chat_uuid: str = cast(str, data.chat_uuid)
        self.muted: bool = data.muted

    async def validate(self) -> None:
        if not await self.check_notification_perms("update"):
            raise Forbidden

    async def execute(self) -> dict:
        """
        Execute the mute/unmute operation.
        """
        actor = getattr(self.request.state, "actor", None)
        if not actor:
            raise Forbidden(description="Authentication required")

        # Build the data to update: {chat_uuid: {"muted": bool}}
        data: dict[str, dict[str, bool]] = {self.chat_uuid: {"muted": self.muted}}

        query = """
        UPDATE entity_users
        SET params = CASE
            WHEN params->'notifications' IS NULL
                THEN jsonb_set(coalesce(params, '{"notifications": {}}'::jsonb), '{notifications}', $1::jsonb)
            ELSE jsonb_set(params, '{notifications}', params->'notifications' || $1::jsonb)
            END
        WHERE actor = $2::uuid and entity_type = 'user'
        RETURNING params->'notifications' as notifications;
        """

        result = await self.db.fetchone(query, data, actor.uuid)

        return {
            "chat_uuid": self.chat_uuid,
            "muted": self.muted,
            "notifications": result.get("notifications", {}) if result else {}
        }


class MuteMultipleNotificationChatsAction(NotificationPermsMixin):
    """
    Action to mute or unmute multiple notification chats for a user.
    Updates the mute status in entity_users.params->'notifications'.
    """

    def __init__(
        self,
        data: MuteMultipleNotificationChatsValidator,
        request: Request,
        db: AsyncDatabaseAdapter,
    ):
        super().__init__(request, db)
        self.chat_uuids: list[str] = cast(list[str], data.chat_uuids)
        self.muted: bool = data.muted

    async def validate(self) -> None:
        if not await self.check_notification_perms("update"):
            raise Forbidden

    async def execute(self) -> dict:
        actor = getattr(self.request.state, "actor", None)
        if not actor:
            raise Forbidden(description="Authentication required")

        # Build the data to update: {chat_uuid: {"muted": bool}, ...}
        data: dict[str, dict[str, bool]] = {
            chat_uuid: {"muted": self.muted} for chat_uuid in self.chat_uuids
        }

        query = """
        UPDATE entity_users
        SET params = CASE
            WHEN params->'notifications' IS NULL
                THEN jsonb_set(coalesce(params, '{"notifications": {}}'::jsonb), '{notifications}', $1::jsonb)
            ELSE jsonb_set(params, '{notifications}', params->'notifications' || $1::jsonb)
            END
        WHERE actor = $2::uuid and entity_type = 'user'
        RETURNING params->'notifications' as notifications;
        """

        result = await self.db.fetchone(query, data, actor.uuid)

        return {
            "chat_uuids": self.chat_uuids,
            "muted": self.muted,
            "notifications": result.get("notifications", {}) if result else {}
        }
