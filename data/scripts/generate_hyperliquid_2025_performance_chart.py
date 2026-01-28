#!/usr/bin/env python3
"""Generate a median performance chart for Hyperliquid 2025 listings."""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import pathlib
import time
import urllib.request
from typing import Dict, List

import matplotlib.pyplot as plt

API_URL = "https://api.hyperliquid.xyz/info"
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
LISTINGS_CSV = DATA_DIR / "hyperliquid_2025_listings.csv"
OUTPUT_IMAGE = DATA_DIR / "hyperliquid_2025_median_performance.png"
OUTPUT_SUMMARY = DATA_DIR / "hyperliquid_2025_median_performance.csv"


def _post(payload: dict) -> object:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


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


def _ms_from_date(value: str) -> int:
    date = dt.datetime.fromisoformat(value)
    return int(date.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return math.nan
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _load_listings() -> Dict[str, str]:
    listings: Dict[str, str] = {}
    with LISTINGS_CSV.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            listings[row["symbol"]] = row["listing_date"]
    return listings


def main() -> None:
    listings = _load_listings()
    now_ms = int(dt.datetime.now(tz=dt.timezone.utc).timestamp() * 1000)

    performance_by_day: Dict[int, List[float]] = {}

    for symbol, listing_date in listings.items():
        candles = _fetch_candles(symbol, _ms_from_date(listing_date), now_ms)
        time.sleep(0.05)
        if not candles:
            continue
        listing_price = float(candles[0]["o"])
        for idx, candle in enumerate(candles):
            close_price = float(candle["c"])
            pct = (close_price - listing_price) / listing_price * 100
            performance_by_day.setdefault(idx, []).append(pct)

    days = sorted(performance_by_day.keys())
    medians: List[float] = []
    pct_25: List[float] = []
    pct_75: List[float] = []

    with OUTPUT_SUMMARY.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["days_since_listing", "median", "p25", "p75", "count"])
        for day in days:
            values = sorted(performance_by_day[day])
            med = _percentile(values, 0.5)
            low = _percentile(values, 0.25)
            high = _percentile(values, 0.75)
            medians.append(med)
            pct_25.append(low)
            pct_75.append(high)
            writer.writerow([day, f"{med:.4f}", f"{low:.4f}", f"{high:.4f}", len(values)])

    plt.figure(figsize=(12, 7))
    plt.plot(days, medians, color="#1f4bd1", label="Median Performance")
    plt.fill_between(days, pct_25, pct_75, color="#8c94f2", alpha=0.4, label="25th-75th Percentile")
    plt.axhline(0, color="#d97c7c", linestyle="--", linewidth=1)
    plt.title("Median Performance of Hyperliquid Listings (2025)")
    plt.xlabel("Days Since Listed")
    plt.ylabel("Performance (%)")
    plt.legend(loc="upper right")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=160)


if __name__ == "__main__":
    main()
