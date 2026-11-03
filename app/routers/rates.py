"""v1 匯率相關端點。"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.exceptions import UnsupportedCurrencyError
from app.schemas import ConvertRequest, ConvertResponse, LatestRatesResponse
from app.services import converter
from app.services.rate_client import PROVIDER_NAME, RateClient

router = APIRouter(prefix="/api/v1", tags=["rates"])
CODE_RE = re.compile(r"^[A-Z]{3}$")


def get_rate_client(request: Request) -> RateClient:
    return request.app.state.rate_client


# Annotated 依賴注入寫法：型別與依賴宣告在一起，可重複使用，測試時也容易替換
RateClientDep = Annotated[RateClient, Depends(get_rate_client)]


def parse_symbols(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    bad = [s for s in symbols if not CODE_RE.match(s)]
    if bad:
        raise UnsupportedCurrencyError(f"幣別代號格式錯誤：{', '.join(bad)}")
    return symbols


@router.get("/rates/latest", response_model=LatestRatesResponse, summary="取得最新匯率")
async def latest_rates(
    client: RateClientDep,
    base: Annotated[str, Query(pattern=r"^[A-Za-z]{3}$", description="基準幣別")] = "USD",
    symbols: Annotated[
        str | None, Query(description="只回傳指定幣別，以逗號分隔，例如 TWD,JPY")
    ] = None,
):
    wanted = parse_symbols(symbols)
    table = await client.get_rates(base)
    return LatestRatesResponse(
        base=table.base,
        rates=converter.filter_symbols(table, wanted),
        last_updated_utc=table.last_updated_utc,
        next_update_utc=table.next_update_utc,
        provider=PROVIDER_NAME,
        cached=table.cached,
        stale=table.stale,
    )


@router.post("/convert", response_model=ConvertResponse, summary="幣別換算")
async def convert(body: ConvertRequest, client: RateClientDep):
    table = await client.get_rates(body.from_currency)
    calc = converter.convert(table, body.to_currency, body.amount)
    return ConvertResponse(
        from_currency=body.from_currency,
        to_currency=body.to_currency,
        amount=body.amount,
        last_updated_utc=table.last_updated_utc,
        stale=table.stale,
        **calc,
    )
