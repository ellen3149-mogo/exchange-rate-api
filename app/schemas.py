"""請求 / 回應模型（Pydantic v2），負責輸入驗證並自動產生 OpenAPI（Swagger）文件。

金額與匯率使用 Decimal，並在 JSON 中以「字串」輸出，避免浮點數精度誤差——
這是金融 API 常見的做法。
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

CurrencyCode = Annotated[
    str,
    Field(pattern=r"^[A-Za-z]{3}$", description="ISO 4217 三碼幣別代號", examples=["USD"]),
]


class LatestRatesResponse(BaseModel):
    base: str
    rates: dict[str, Decimal] = Field(description="1 單位 base 可兌換的各幣別數量")
    last_updated_utc: datetime
    next_update_utc: datetime
    provider: str
    cached: bool = Field(description="是否由快取回應")
    stale: bool = Field(description="資料源暫時無法連線時，回傳最後一次成功取得的資料")


class ConvertRequest(BaseModel):
    from_currency: CurrencyCode
    to_currency: CurrencyCode
    amount: Decimal = Field(gt=0, le=Decimal("1000000000000"), examples=["1000"])

    @field_validator("from_currency", "to_currency")
    @classmethod
    def to_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("amount")
    @classmethod
    def limit_precision(cls, v: Decimal) -> Decimal:
        if -v.as_tuple().exponent > 6:
            raise ValueError("金額最多 6 位小數")
        return v


class ConvertResponse(BaseModel):
    from_currency: str
    to_currency: str
    amount: Decimal
    rate: Decimal
    inverse_rate: Decimal
    result: Decimal
    last_updated_utc: datetime
    stale: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
