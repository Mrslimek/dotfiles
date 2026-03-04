import httpx

from app.config import config


class AuthService:
    def __init__(self) -> None:
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.base_url = config.API_BASE_URL.rstrip("/")
        self.token_endpoint = config.API_TOKEN_ENDPOINT
        self.refresh_endpoint = config.API_REFRESH_ENDPOINT
        self.username = config.API_USERNAME
        self.password = config.API_PASSWORD

    async def authenticate(self) -> None:
        url = f"{self.base_url}{self.token_endpoint}"
        payload = {
            "username": self.username,
            "password": self.password
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise ValueError(f"Authentication failed: {response.text}")

            data = response.json()

            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")

            if not self.access_token or not self.refresh_token:
                raise ValueError("Invalid response: missing tokens")

    async def refresh_tokens(self) -> None:
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        url = f"{self.base_url}{self.refresh_endpoint}"
        payload = {
            "refresh": self.refresh_token
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise ValueError(f"Token refresh failed: {response.text}")

            data = response.json()

            self.access_token = data.get("access")
            new_refresh = data.get("refresh")

            if new_refresh:
                self.refresh_token = new_refresh

            if not self.access_token:
                raise ValueError("Invalid response: missing access token")

    async def get_access_token(self) -> str:
        if not self.access_token:
            await self.authenticate()

        return self.access_token

    def set_tokens(self, access: str, refresh: str) -> None:
        self.access_token = access
        self.refresh_token = refresh

    def clear_tokens(self) -> None:
        self.access_token = None
        self.refresh_token = None
