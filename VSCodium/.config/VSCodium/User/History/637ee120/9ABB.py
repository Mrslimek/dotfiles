from typing import TYPE_CHECKING

from fastapi import Request

from service54.actions import NotificationPermsMixin
from service54.auth_perms.fast_api.database.async_manager import AsyncDatabaseAdapter
from service54.auth_perms.fast_api.exceptions import Forbidden
from service54.core.datatypes import UUID

if TYPE_CHECKING:
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
        self.chat_uuid: UUID = data.chat_uuid
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
        data: dict[str, dict[str, bool]] = {str(self.chat_uuid): {"muted": self.muted}}

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

        # Propagate the notification event via WebSocket
        await self.db.execute(
            "SELECT propagate_notification_event($1, $2, $3)",
            "mute_update",
            [str(self.chat_uuid)],
            [actor.uuid],
        )

        return {
            "chat_uuid": str(self.chat_uuid),
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
        self.chat_uuids: list[UUID] = data.chat_uuids
        self.muted: bool = data.muted

    async def validate(self) -> None:
        """
        Validate permission to modify notification subscriptions.
        This method should be called separately before execute().
        """
        # Check permission to modify notification subscriptions
        if not await self.check_notification_perms("update"):
            raise Forbidden

    async def execute(self) -> dict:
        """
        Execute the mute/unmute operation for multiple chats.
        This method assumes validate() has already been called.
        """
        # Ensure actor is available
        actor = getattr(self.request.state, "actor", None)
        if not actor:
            raise Forbidden(description="Authentication required")

        # Build the data to update: {chat_uuid: {"muted": bool}, ...}
        data: dict[str, dict[str, bool]] = {
            str(chat_uuid): {"muted": self.muted} for chat_uuid in self.chat_uuids
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

        # Propagate the notification event via WebSocket
        await self.db.execute(
            "SELECT propagate_notification_event($1, $2, $3)",
            "mute_update",
            [str(uuid) for uuid in self.chat_uuids],
            [actor.uuid],
        )

        return {
            "chat_uuids": [str(uuid) for uuid in self.chat_uuids],
            "muted": self.muted,
            "notifications": result.get("notifications", {}) if result else {}
        }
