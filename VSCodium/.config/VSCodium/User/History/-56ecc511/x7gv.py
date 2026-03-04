from __future__ import annotations
import tempfile
import os

from vkbottle.tools import DocMessagesUploader

from app.bot_instance import get_bot
from app.services.podruchniy_service import PodruchniyService


class ExportAction:
    def __init__(self, action: str, inn: str, peer_id: int) -> None:
        self.action = action
        self.inn = inn
        self.peer_id = peer_id

    async def execute(self) -> bytes:
        async with PodruchniyService() as service:
            return await (service.export_pdf(self.inn) if self.action == "export_pdf" else service.export_csv(self.inn))

    async def confirm_event(self, event_id: str | None, user_id: int | None) -> None:
        if event_id and user_id:
            try:
                await get_bot().api.messages.send_message_event_answer(
                    event_id=event_id, user_id=user_id, peer_id=self.peer_id
                )
            except Exception:
                pass

    async def upload_doc(self, file_bytes: bytes, filename: str) -> None | bool:
        max_size = 200 * 1024 * 1024
        if len(file_bytes) > max_size:
            return False

        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, filename)

        try:
            with open(temp_file_path, "wb") as f:
                f.write(file_bytes)

            uploader = DocMessagesUploader(get_bot().api)
            attachment = await uploader.upload(file_source=temp_file_path, peer_id=self.peer_id)
            await get_bot().api.messages.send(peer_id=self.peer_id, attachment=attachment, random_id=0)
            return True
        finally:
            try:
                os.unlink(temp_file_path)
                os.rmdir(temp_dir)
            except OSError:
                pass
