import aiohttp
from typing import Any

from app.config import config
from app.services.auth_service import AuthService


class DaDataService:
    def __init__(self) -> None:
        self.auth_service = AuthService()
        self.base_url = config.API_BASE_URL
        self.endpoint = config.API_FIND_BY_ID_PARTY_ENDPOINT

    async def find_by_id_party(self, inn: str) -> Any:
        return await self._make_request(inn)

    async def _make_request(self, inn: str, is_retry: bool = False) -> Any:
        url = f"{self.base_url}{self.endpoint}"
        payload = {"query": inn}
        token = await self.auth_service.get_access_token()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 401 and not is_retry:
                    await self.auth_service.refresh_tokens()
                    return await self._make_request(inn, is_retry=True)

                response.raise_for_status()
                return await response.json()

    async def find_by_id_party_safe(self, inn: str) -> Any | None:
        try:
            return await self.find_by_id_party(inn)
        except (aiohttp.ClientError, ValueError) as e:
            print(f"Error fetching data for INN {inn}: {e}")
            return None
