#!/usr/bin/env python3
"""Fetch Hyperliquid listings with first trading day in 2025 and export performance."""
from __future__ import annotations

import csv
import datetime as dt
import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List

API_URL = "https://api.hyperliquid.xyz/info"


@dataclass
class ListingPerformance:
    symbol: str
    listing_date: dt.date
    listing_price: float
    latest_date: dt.date
    latest_price: float
    price_impact_pct: float
    days_since_listing: int


def _post(payload: dict) -> object:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _fetch_universe() -> List[str]:
    meta = _post({"type": "meta"})
    return [asset["name"] for asset in meta["universe"]]


def _fetch_candles(symbol: str, start_ms: int, end_ms: int) -> List[dict]:
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": symbol,
            "interval": "1d",
            "startTime": start_ms,
            "endTime": end_ms,
        },
    }
    return _post(payload)


def _date_from_ms(ts_ms: int) -> dt.date:
    return dt.datetime.utcfromtimestamp(ts_ms / 1000).date()


def _performance_from_candles(symbol: str, candles: Iterable[dict]) -> ListingPerformance | None:
    candles = list(candles)
    if not candles:
        return None
    first = candles[0]
    last = candles[-1]
    listing_date = _date_from_ms(first["t"])
    latest_date = _date_from_ms(last["t"])
    listing_price = float(first["o"])
    latest_price = float(last["c"])
    price_impact_pct = (latest_price - listing_price) / listing_price * 100
    days_since_listing = (latest_date - listing_date).days
    return ListingPerformance(
        symbol=symbol,
        listing_date=listing_date,
        listing_price=listing_price,
        latest_date=latest_date,
        latest_price=latest_price,
        price_impact_pct=price_impact_pct,
        days_since_listing=days_since_listing,
    )


def main() -> None:
    start_2024 = int(dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    end_2024 = int(dt.datetime(2024, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc).timestamp() * 1000)
    start_2025 = int(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    now_ms = int(dt.datetime.now(tz=dt.timezone.utc).timestamp() * 1000)

    listings: List[ListingPerformance] = []
    for symbol in _fetch_universe():
        candles_2024 = _fetch_candles(symbol, start_2024, end_2024)
        time.sleep(0.05)
        if candles_2024:
            continue
        candles_2025 = _fetch_candles(symbol, start_2025, now_ms)
        time.sleep(0.05)
        perf = _performance_from_candles(symbol, candles_2025)
        if perf and perf.listing_date.year == 2025:
            listings.append(perf)

    listings.sort(key=lambda item: abs(item.price_impact_pct), reverse=True)

    with open("data/hyperliquid_2025_listings.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "symbol",
                "listing_date",
                "listing_price",
                "latest_date",
                "latest_price",
                "price_impact_pct",
                "days_since_listing",
            ]
        )
        for item in listings:
            writer.writerow(
                [
                    item.symbol,
                    item.listing_date.isoformat(),
                    f"{item.listing_price:.8f}",
                    item.latest_date.isoformat(),
                    f"{item.latest_price:.8f}",
                    f"{item.price_impact_pct:.4f}",
                    item.days_since_listing,
                ]
            )


if __name__ == "__main__":
    main()
