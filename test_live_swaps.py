
import asyncio
import json
from datetime import datetime, timezone

import websockets

POOL_ADDRESS = (
    "EWiqwm9wXVoj5yyb8VV2FkS9rc5HWJ3PmtwCKuv94P24"
)

WS_URL = "wss://api.mainnet.solana.com"


async def main():
    async with websockets.connect(
        WS_URL,
        ping_interval=20,
        ping_timeout=20,
        open_timeout=15,
    ) as ws:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [POOL_ADDRESS]},
                {"commitment": "processed"},
            ],
        }

        await ws.send(json.dumps(request))
        reply = json.loads(await ws.recv())

        if "error" in reply:
            print("Subscription error:", reply["error"])
            return

        print("Subscription active:", reply.get("result"))
        print("Waiting for pool transactions...")

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
            error = value.get("err")
            logs = value.get("logs") or []

            now = datetime.now(timezone.utc).isoformat()

            print(f"\n[{now}] Pool transaction detected")
            print("Signature:", signature)
            print("Transaction error:", error)

            for log in logs:
                print(" ", log)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print("Connection failed:", repr(exc))
