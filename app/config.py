"""應用程式設定：全部由環境變數注入（12-Factor App）。

在 Cloud Run 上調整設定不必重新打包映像檔。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Exchange Rate Analytics & Conversion API"
    app_version: str = "1.0.0"
    environment: str = "local"

    # 第三方匯率 API（ExchangeRate-API 開放端點，免金鑰；資料約每日更新）
    rate_api_base_url: str = "https://open.er-api.com/v6"
    rate_api_timeout_seconds: float = 5.0
    rate_api_max_retries: int = 3

    # 快取存活時間（秒）。資料源每日更新，快取可大幅減少外部呼叫與延遲
    cache_ttl_seconds: int = 600

    cors_origins: str = "*"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
