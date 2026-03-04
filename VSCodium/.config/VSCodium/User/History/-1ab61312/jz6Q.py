from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    VK_TOKEN: str = Field(...)
    GROUP_ID: str | None = Field(default=None)

    PODRUCHNIY_BACKEND_API_BASE_URL: str = Field(...)
    PODRUCHNIY_BACKEND_API_FIND_BY_ID_PARTY_ENDPOINT: str = Field(
        default="/api/v1.0/portal/dadata/find-by-id-party/"
    )
    PODRUCHNIY_BACKEND_API_USERNAME: str = Field(...)
    PODRUCHNIY_BACKEND_API_PASSWORD: str = Field(...)
    PODRUCHNIY_BACKEND_API_TOKEN_ENDPOINT: str = Field(
        default="/api/token"
    )
    PODRUCHNIY_BACKEND_API_REFRESH_ENDPOINT: str = Field(
        default="/api/token/refresh"
    )

    LOG_LEVEL: str = Field(default="INFO")

    @computed_field
    @property
    def api_base_url(self) -> str:
        return self.PODRUCHNIY_BACKEND_API_BASE_URL.rstrip("/")

    @computed_field
    @property
    def api_find_by_id_party_endpoint(self) -> str:
        v = self.PODRUCHNIY_BACKEND_API_FIND_BY_ID_PARTY_ENDPOINT.strip()
        if not v.startswith("/"):
            v = "/" + v
        if v != "/" and v.endswith("/"):
            v = v.rstrip("/")
        return v

    @computed_field
    @property
    def api_token_endpoint(self) -> str:
        v = self.PODRUCHNIY_BACKEND_API_TOKEN_ENDPOINT.strip()
        if not v.startswith("/"):
            v = "/" + v
        if v != "/" and v.endswith("/"):
            v = v.rstrip("/")
        return v

    @computed_field
    @property
    def api_refresh_endpoint(self) -> str:
        v = self.PODRUCHNIY_BACKEND_API_REFRESH_ENDPOINT.strip()
        if not v.startswith("/"):
            v = "/" + v
        if v != "/" and v.endswith("/"):
            v = v.rstrip("/")
        return v


config = Settings()
