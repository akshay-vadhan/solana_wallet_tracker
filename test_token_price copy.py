
import csv
import time
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path

TOKEN_CA = "FEXGegqeVm5vZurqyC7qsmkLqWspVV1ACb9bbLvcpump"

POSITION_USD = 10.0
DURATION_SECONDS = 30
INTERVAL_SECONDS = 5

OUT_DIR = Path("exports")
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "ca_price_test.csv"

API_URL = (
    "https://api.dexscreener.com/token-pairs/v1/solana/"
    + TOKEN_CA
)


def fetch_price():
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "SolanaPaperPriceTest/1.0"}
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        pairs = json.loads(response.read().decode("utf-8"))

    if not isinstance(pairs, list):
        raise ValueError("Unexpected API response")

    # Use pools where the target token is the base token.
    candidates = [
        p for p in pairs
        if p.get("chainId") == "solana"
        and p.get("baseToken", {}).get("address") == TOKEN_CA
        and p.get("priceUsd") is not None
        and float(p.get("liquidity", {}).get("usd") or 0) > 0
    ]

    if not candidates:
        raise ValueError(
            "No suitable pool found with a USD price and liquidity."
        )

    # Choose the pool with the highest reported liquidity.
    pair = max(
        candidates,
        key=lambda p: float(p.get("liquidity", {}).get("usd") or 0)
    )

    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "price": float(pair["priceUsd"]),
        "liquidity": float(pair.get("liquidity", {}).get("usd") or 0),
        "pair": pair.get("pairAddress", ""),
        "dex": pair.get("dexId", ""),
        "volume_5m": float(pair.get("volume", {}).get("m5") or 0),
        "buys_5m": int(pair.get("txns", {}).get("m5", {}).get("buys") or 0),
        "sells_5m": int(pair.get("txns", {}).get("m5", {}).get("sells") or 0),
    }


print("Fetching initial market price...")

try:
    initial = fetch_price()
except Exception as e:
    print("Could not start test:", e)
    raise SystemExit(1)

entry_price = initial["price"]

if entry_price <= 0:
    print("Invalid entry price.")
    raise SystemExit(1)

print(f"Token CA: {TOKEN_CA}")
print(f"Pool: {initial['pair']} ({initial['dex']})")
print(f"Initial price: ${entry_price:.12f}")
print(f"Pool liquidity: ${initial['liquidity']:.2f}")
print(f"Virtual position: ${POSITION_USD:.2f}")
print("Mode: PAPER ONLY; no transaction will be sent.\n")

rows = []
rows.append({
    **initial,
    "elapsed_seconds": 0,
    "price_change_pct": 0.0,
    "gross_pnl_usd": 0.0,
})

start = time.monotonic()

while time.monotonic() - start < DURATION_SECONDS:
    remaining = INTERVAL_SECONDS - (
        (time.monotonic() - start) % INTERVAL_SECONDS
    )
    time.sleep(max(0, min(remaining, 1)))

    elapsed = time.monotonic() - start
    if elapsed >= DURATION_SECONDS:
        break

    try:
        snap = fetch_price()
        change_pct = (snap["price"] / entry_price - 1) * 100
        gross_pnl = POSITION_USD * change_pct / 100

        row = {
            **snap,
            "elapsed_seconds": round(elapsed, 1),
            "price_change_pct": change_pct,
            "gross_pnl_usd": gross_pnl,
        }
        rows.append(row)

        print(
            f"+{elapsed:5.1f}s | "
            f"Price ${snap['price']:.12f} | "
            f"Change {change_pct:+.3f}% | "
            f"Gross PnL ${gross_pnl:+.4f} | "
            f"Liquidity ${snap['liquidity']:.0f} | "
            f"5m buys/sells {snap['buys_5m']}/{snap['sells_5m']}"
        )

    except Exception as e:
        print(f"+{elapsed:.1f}s | Data fetch failed: {e}")

fields = [
    "time", "elapsed_seconds", "price", "price_change_pct",
    "gross_pnl_usd", "liquidity", "volume_5m", "buys_5m",
    "sells_5m", "pair", "dex"
]

with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in fields})

last = rows[-1]
print("\n--- RESULT ---")
print(f"Initial price: ${entry_price:.12f}")
print(f"Last sampled price: ${last['price']:.12f}")
print(f"Gross price-based PnL: ${last['gross_pnl_usd']:+.4f}")
print(f"CSV saved: {OUT_FILE}")
print("Fees, slippage and executable exit price are NOT included.")
