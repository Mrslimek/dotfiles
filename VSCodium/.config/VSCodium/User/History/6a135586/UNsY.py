from typing import Any

import aiohttp

from app.config import config


class PodruchniyService:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self.base_url = config.API_BASE_URL
        self.token_endpoint = config.API_TOKEN_ENDPOINT
        self.refresh_endpoint = config.API_REFRESH_ENDPOINT
        self.find_by_id_party_endpoint = config.API_FIND_BY_ID_PARTY_ENDPOINT
        self.username = config.API_USERNAME
        self.password = config.API_PASSWORD

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _authenticate(self) -> None:
        url = f"{self.base_url}{self.token_endpoint}"
        payload = {
            "username": self.username,
            "password": self.password
        }

        session = await self._get_session()
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ValueError(f"Authentication failed: {error_text}")

            data = await response.json()

            self._access_token = data.get("access")
            self._refresh_token = data.get("refresh")

            if not self._access_token or not self._refresh_token:
                raise ValueError("Invalid response: missing tokens")

    async def _refresh_tokens(self) -> None:
        if not self._refresh_token:
            raise ValueError("No refresh token available")

        url = f"{self.base_url}{self.refresh_endpoint}"
        payload = {
            "refresh": self._refresh_token
        }

        session = await self._get_session()
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ValueError(f"Token refresh failed: {error_text}")

            data = await response.json()

            self._access_token = data.get("access")
            new_refresh = data.get("refresh")

            if new_refresh:
                self._refresh_token = new_refresh

            if not self._access_token:
                raise ValueError("Invalid response: missing access token")

    async def _get_access_token(self) -> str:
        if not self._access_token:
            await self._authenticate()
        return self._access_token

    async def find_by_id_party(self, inn: str) -> Any:
        return await self._make_request(inn)

    async def _make_request(self, inn: str, is_retry: bool = False) -> Any:
        url = f"{self.base_url}{self.find_by_id_party_endpoint}"
        payload = {"query": inn}
        token = await self._get_access_token()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        session = await self._get_session()
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 401 and not is_retry:
                await self._refresh_tokens()
                return await self._make_request(inn, is_retry=True)

            response.raise_for_status()
            return await response.json()

    async def find_by_id_party_safe(self, inn: str) -> Any | None:
        try:
            return await self.find_by_id_party(inn)
        except (aiohttp.ClientError, ValueError) as e:
            print(f"Error fetching data for INN {inn}: {e}")
            return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
