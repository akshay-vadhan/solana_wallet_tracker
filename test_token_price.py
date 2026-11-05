
import csv
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Token and the EXACT PumpSwap pool shown in your screenshot
TOKEN_CA = "FEXGegqeVm5vZurqyC7qsmkLqWspVV1ACb9bbLvcpump"

PAIR_ADDRESS = "EWiqwm9wXVoj5yyb8VV2FkS9rc5HWJ3PmtwCKuv94P24"

POSITION_USD = 10.0
DURATION_SECONDS = 30
INTERVAL_SECONDS = 5

OUT_DIR = Path("exports")
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "ca_price_test.csv"

API_URL = (
    "https://api.dexscreener.com/latest/dex/pairs/"
    f"solana/{PAIR_ADDRESS}"
)


def fetch_price():
    request_started = time.monotonic()

    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "SolanaPaperPriceTest/2.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
        headers = response.headers

        http_status = response.status
        server_date = headers.get("Date", "")
        cache_control = headers.get("Cache-Control", "")
        cache_age = headers.get("Age", "")
        cache_status = (
            headers.get("CF-Cache-Status")
            or headers.get("X-Cache", "")
        )

    latency_ms = round(
        (time.monotonic() - request_started) * 1000, 1
    )

    data = json.loads(body)
    pairs = data.get("pairs") or []

    if not pairs:
        raise ValueError(
            "No pair returned. Check the pool address."
        )

    # Exact pair endpoint should return the requested pool.
    pair = next(
        (
            p for p in pairs
            if p.get("pairAddress", "").lower()
            == PAIR_ADDRESS.lower()
        ),
        None,
    )

    if pair is None:
        raise ValueError(
            "Requested pool was not found in API response."
        )

    if pair.get("chainId") != "solana":
        raise ValueError("Returned pool is not on Solana.")

    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}
    liquidity = pair.get("liquidity") or {}
    volume = pair.get("volume") or {}
    txns = pair.get("txns") or {}
    txns_5m = txns.get("m5") or {}
    price_change = pair.get("priceChange") or {}

    # The base token must be the token whose price we want.
    if base.get("address", "").lower() != TOKEN_CA.lower():
        raise ValueError(
            "Pool base token does not match TOKEN_CA. "
            f"Base token returned: {base.get('address')}"
        )

    price_raw = pair.get("priceUsd")
    if price_raw is None:
        raise ValueError("API returned no USD price.")

    price = float(price_raw)
    if price <= 0:
        raise ValueError(f"Invalid USD price: {price}")

    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "server_date": server_date,
        "http_status": http_status,
        "latency_ms": latency_ms,
        "cache_control": cache_control,
        "cache_age": cache_age,
        "cache_status": cache_status,
        "price": price,
        "price_native": pair.get("priceNative"),
        "liquidity": float(liquidity.get("usd") or 0),
        "pair": pair.get("pairAddress", ""),
        "dex": pair.get("dexId", ""),
        "base_symbol": base.get("symbol", ""),
        "quote_symbol": quote.get("symbol", ""),
        "volume_5m": float(volume.get("m5") or 0),
        "buys_5m": int(txns_5m.get("buys") or 0),
        "sells_5m": int(txns_5m.get("sells") or 0),
        "change_5m": price_change.get("m5"),
    }


def print_snapshot(snap, elapsed):
    print(
        f"+{elapsed:5.1f}s | "
        f"Price ${snap['price']:.12f} | "
        f"5m volume ${snap['volume_5m']:.2f} | "
        f"Buys/sells {snap['buys_5m']}/{snap['sells_5m']} | "
        f"Liquidity ${snap['liquidity']:.0f} | "
        f"Latency {snap['latency_ms']}ms"
    )

    print(
        f"       API Date={snap['server_date'] or 'n/a'} | "
        f"Age={snap['cache_age'] or 'n/a'} | "
        f"Cache={snap['cache_status'] or 'n/a'}"
    )


print("Fetching initial price from exact pool...")
print("Mode: PAPER ONLY — no transaction will be sent.")
print("Pool:", PAIR_ADDRESS)

try:
    initial = fetch_price()
except Exception as e:
    print("Could not start test:", repr(e))
    raise SystemExit(1)

entry_price = initial["price"]

print("DEX:", initial["dex"])
print("Base token:", initial["base_symbol"])
print("Quote token:", initial["quote_symbol"])
print(f"Initial price: ${entry_price:.12f}")
print(f"Liquidity: ${initial['liquidity']:.2f}")
print(f"Virtual position: ${POSITION_USD:.2f}\n")

rows = []

def save_snapshot(snap, elapsed):
    change_pct = (snap["price"] / entry_price - 1) * 100
    gross_pnl = POSITION_USD * change_pct / 100

    row = {
        **snap,
        "elapsed_seconds": round(elapsed, 2),
        "price_change_pct": change_pct,
        "gross_pnl_usd": gross_pnl,
    }

    rows.append(row)
    print_snapshot(snap, elapsed)
    print(
        f"       Change={change_pct:+.4f}% | "
        f"Gross PnL=${gross_pnl:+.4f}"
    )


save_snapshot(initial, 0.0)

start = time.monotonic()
next_sample = start + INTERVAL_SECONDS

while True:
    now = time.monotonic()
    if now >= start + DURATION_SECONDS:
        break

    time.sleep(max(0, min(next_sample - now, 0.5)))

    if time.monotonic() >= start + DURATION_SECONDS:
        break

    try:
        snap = fetch_price()
        elapsed = time.monotonic() - start
        save_snapshot(snap, elapsed)

    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"+{elapsed:.1f}s | Fetch failed: {repr(e)}")

    next_sample += INTERVAL_SECONDS

    # Avoid a burst of requests if one request was delayed.
    while next_sample <= time.monotonic():
        next_sample += INTERVAL_SECONDS


fields = [
    "time", "server_date", "elapsed_seconds", "http_status",
    "latency_ms", "cache_control", "cache_age", "cache_status",
    "price", "price_native", "price_change_pct", "gross_pnl_usd",
    "liquidity", "volume_5m", "buys_5m", "sells_5m",
    "change_5m", "pair", "dex", "base_symbol", "quote_symbol",
]

with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(
        {key: row.get(key) for key in fields}
        for row in rows
    )

last = rows[-1]

print("\n--- RESULT ---")
print(f"Initial price: ${entry_price:.12f}")
print(f"Last sampled price: ${last['price']:.12f}")
print(f"Last price change: {last['price_change_pct']:+.4f}%")
print(f"Gross price-based PnL: ${last['gross_pnl_usd']:+.4f}")
print(f"CSV saved: {OUT_FILE}")
print("Note: API polling is not guaranteed to be real-time.")
print("Fees, slippage and executable exit price are NOT included.")
