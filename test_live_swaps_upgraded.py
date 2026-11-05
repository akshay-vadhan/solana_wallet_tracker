

def append_csv(row):
    fields = [
        "observed_at", "signature", "status", "error", "slot",
        "block_time_utc", "signer", "side", "token_amount",
        "sol_amount_est", "price_sol_per_token_est", "token_ca",
        "pool", "fee_sol",
    ]
    exists = OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fields})


async def main():
    try:
        import websockets
    except ImportError:
        print("Missing dependency. Install it with: python3 -m pip install websockets")
        return

    print("Free public Solana RPC live pool monitor")
    print("Pool:", POOL_ADDRESS)
    print("Token mint:", TOKEN_CA)
    print("Output CSV:", OUT_CSV)
    print("Monitoring only; no transactions are sent.")
    print("Connecting to public WebSocket RPC...")

    while True:
        try:
            async with websockets.connect(
                RPC_WS,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=15,
                close_timeout=5,
            ) as ws:
                await ws.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [
                        {"mentions": [POOL_ADDRESS]},
                        {"commitment": "confirmed"},
                    ],
                }))

                reply = json.loads(await ws.recv())
                if "error" in reply:
                    raise RuntimeError(f"Subscription error: {reply['error']}")

                print("Subscription active. Waiting for confirmed pool transactions...")

                while True:
                    message = json.loads(await ws.recv())
                    if message.get("method") != "logsNotification":
                        continue

                    value = (
                        message.get("params", {})
                        .get("result", {})
                        .get("value", {})
                    )
                    signature = value.get("signature")
                    if not signature:
                        continue

                    if signature in SEEN_SIGNATURES:
                        continue
                    SEEN_SIGNATURES.add(signature)
                    if len(SEEN_SIGNATURES) > MAX_SEEN:
                        SEEN_SIGNATURES.clear()
                        SEEN_SIGNATURES.add(signature)

                    print(f"\nTransaction: {signature}")
                    if value.get("err") is not None:
                        print("Notification reports failure; skipping price parse.")
                        continue

                    tx = await asyncio.to_thread(get_transaction, signature)
                    if tx is None:
                        print("Transaction metadata unavailable from public RPC.")
                        continue

                    row = parse_transaction(signature, tx)
                    if not row:
                        print("Could not parse transaction metadata.")
                        continue

                    append_csv(row)

                    print("Status:", row["status"])
                    print("Slot / block time:", row.get("slot"), row.get("block_time_utc"))
                    print("Signer:", row.get("signer", ""))
                    print("Side:", row.get("side", ""))
                    print("Token amount:", row.get("token_amount", ""))
                    print("Estimated SOL amount:", row.get("sol_amount_est", ""))
                    print("Estimated SOL/token:", row.get("price_sol_per_token_est", ""))
                    print("Fee (SOL):", row.get("fee_sol", ""))
                    if row.get("status") == "success_unparsed":
                        print("Note:", row.get("error"))

        except KeyboardInterrupt:
            print("\nStopped by user.")
            return
        except Exception as exc:
            print(f"WebSocket disconnected/error: {exc}")
            print("Retrying in 3 seconds...")
            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
