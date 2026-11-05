
import os
import time
import json
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# Existing token from your SQLite database
TOKEN_CA = "HfPVTUsSd55Aab6BACWCy6dXo5pQgTUFnyGzgspFpump"

# Wrapped SOL mint used by Jupiter swaps
SOL_MINT = "So11111111111111111111111111111111111111112"

POSITION_USD = 10.0
LAMPORTS_PER_SOL = 1_000_000_000

BASE_URL = "https://lite-api.jup.ag"
API_KEY = os.getenv("JUPITER_API_KEY", "").strip()
TAKER = os.getenv("JUPITER_TAKER", "").strip()

session = requests.Session()
session.headers.update({"Accept": "application/json"})

if API_KEY:
    session.headers["x-api-key"] = API_KEY


def get_json(url, params=None):
    response = session.get(url, params=params, timeout=20)

    if response.status_code == 429:
        raise RuntimeError(
            "Jupiter rate limit reached. Wait before retrying."
        )

    response.raise_for_status()
    return response.json()


def get_sol_usd_price():
    url = f"{BASE_URL}/price/v3"
    data = get_json(url, {"ids": SOL_MINT})

    # V3 normally returns a mint-keyed object.
    item = data.get(SOL_MINT)

    if item is None and isinstance(data.get("data"), dict):
        item = data["data"].get(SOL_MINT)

    if not isinstance(item, dict) or not item.get("usdPrice"):
        raise RuntimeError(
            f"SOL USD price missing in Price API response: {data}"
        )

    price = float(item["usdPrice"])

    if price <= 0:
        raise RuntimeError("Invalid SOL USD price.")

    return price, item


def get_order(input_mint, output_mint, amount_raw):
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "taker": TAKER,
    }

    # GET /order returns a quote/order. This code never signs or executes it.
    return get_json(f"{BASE_URL}/swap/v2/order", params)


def raw_amount(order, key):
    value = order.get(key)

    if value is None:
        raise RuntimeError(
            f"Quote missing {key}. Response: "
            + json.dumps(order, ensure_ascii=False)[:1500]
        )

    return int(value)


def print_order_summary(label, order):
    print(f"\n{label}")
    print("-" * 48)
    print("Router:", order.get("router"))
    print("Input raw amount:", order.get("inAmount"))
    print("Output raw amount:", order.get("outAmount"))
    print("Fee BPS:", order.get("feeBps"))
    print("Gas estimate:", order.get("gasEstimation"))
    print("Error code:", order.get("errorCode"))
    if order.get("errorMessage"):
        print("Error message:", order.get("errorMessage"))

    # Deliberately do not sign, submit, or execute order.transaction.


def main():
    if not TAKER:
        print(
            "Set JUPITER_TAKER in .env to your own public Solana "
            "wallet address. Do not use a private key."
        )
        return

    print("JUPITER PAPER QUOTE TEST")
    print("Time UTC:", datetime.now(timezone.utc).isoformat())
    print("Token:", TOKEN_CA)
    print("Paper position: $", POSITION_USD)
    print("REAL SWAPS: DISABLED")
    print("Fetching reference price...")

    sol_usd, price_info = get_sol_usd_price()
    print(f"SOL reference price: ${sol_usd:.4f}")
    print("Price API block ID:", price_info.get("blockId"))

    # Convert $10 to SOL lamports using the reference price.
    buy_lamports = int((POSITION_USD / sol_usd) * LAMPORTS_PER_SOL)

    # Stay within the keyless API's documented rate limit.
    time.sleep(2.1)

    print("\nRequesting BUY quote...")
    buy = get_order(SOL_MINT, TOKEN_CA, buy_lamports)
    print_order_summary("BUY QUOTE", buy)

    if not buy.get("outAmount"):
        print("BUY quote has no output amount; cannot continue.")
        return

    buy_input_lamports = raw_amount(buy, "inAmount")
    token_out_raw = raw_amount(buy, "outAmount")

    if token_out_raw <= 0:
        print("BUY output amount is zero.")
        return

    buy_cost_usd = (
        buy_input_lamports / LAMPORTS_PER_SOL
    ) * sol_usd

    print(f"\nReference BUY cost: ${buy_cost_usd:.6f}")
    print("Estimated token output (raw units):", token_out_raw)

    time.sleep(2.1)

    print("\nRequesting SELL quote for the BUY's estimated output...")
    sell = get_order(TOKEN_CA, SOL_MINT, token_out_raw)
    print_order_summary("SELL QUOTE", sell)

    if not sell.get("outAmount"):
        print("SELL quote has no output amount; cannot calculate PnL.")
        return

    sell_output_lamports = raw_amount(sell, "outAmount")
    sell_proceeds_usd = (
        sell_output_lamports / LAMPORTS_PER_SOL
    ) * sol_usd

    gross_pnl_usd = sell_proceeds_usd - buy_cost_usd
    gross_pnl_pct = (
        gross_pnl_usd / buy_cost_usd * 100
        if buy_cost_usd else 0
    )

    print("\n" + "=" * 48)
    print("PAPER ROUND-TRIP RESULT")
    print("=" * 48)
    print(f"Reference SOL/USD: ${sol_usd:.4f}")
    print(f"Estimated BUY cost: ${buy_cost_usd:.6f}")
    print(f"Estimated SELL proceeds: ${sell_proceeds_usd:.6f}")
    print(f"Quote-based PnL: ${gross_pnl_usd:+.6f}")
    print(f"Quote-based return: {gross_pnl_pct:+.3f}%")
    print("\nNo transaction was signed or sent.")
    print(
        "This is a sequential quote simulation, not a guaranteed "
        "executable round trip. Network fees, timing changes, "
        "and actual fill differences may affect realized PnL."
    )


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print("Jupiter HTTP/network error:", exc)
    except (ValueError, RuntimeError, KeyError) as exc:
        print("Test could not complete:", exc)
