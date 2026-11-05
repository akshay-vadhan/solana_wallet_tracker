#!/usr/bin/env python3
"""Solana PumpSwap live swap monitor. Analytics/paper only; no signing or trading."""
import asyncio, csv, json, os, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import websockets

RPC_HTTP = os.getenv("SOLANA_RPC_HTTP", "https://api.mainnet.solana.com")
RPC_WS = os.getenv("SOLANA_RPC_WS", "wss://api.mainnet.solana.com")
POOL_ADDRESS = os.getenv("POOL_ADDRESS", "EWiqwm9wXVoj5yyb8VV2FkS9rc5HWJ3PmtwCKuv94P24")
TOKEN_MINT = os.getenv("TOKEN_MINT", "FEXGegqeVm5vZurqyC7qsmkLqWspVV1ACb9bbLvcpump")
COMMITMENT = os.getenv("SOLANA_COMMITMENT", "confirmed")
OUT_DIR = os.getenv("SWAP_EXPORT_DIR", "exports")
EVENTS_CSV = os.path.join(OUT_DIR, "live_swap_events.csv")
ERRORS_CSV = os.path.join(OUT_DIR, "live_swap_errors.csv")
EVENT_FIELDS = ["observed_at_utc","signature","slot","block_time_utc","status","instruction_hint","direction","token_mint","token_delta","quote_mint_delta","signer","signer_sol_delta_lamports","tx_fee_lamports","estimated_sol_spent_or_received_lamports","price_sol_per_token_est","price_quality","error"]
ERROR_FIELDS = ["observed_at_utc","signature","slot","status","error","instruction_hint","logs"]
SEEN, IN_FLIGHT = set(), set()

def now():
    return datetime.now(timezone.utc).isoformat()

def ensure_csv(path, fields):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()

def append_csv(path, fields, row):
    ensure_csv(path, fields)
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fields, extrasaction="ignore").writerow({k: row.get(k, "") for k in fields})

def rpc_call(method, params, timeout=12):
    payload = json.dumps({"jsonrpc":"2.0","id":int(time.time()*1000)%1000000,"method":method,"params":params}).encode()
    req = Request(RPC_HTTP, data=payload, headers={"Content-Type":"application/json"})
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(f"RPC {method} error: {data['error']}")
    return data.get("result")

def amt(b):
    try: return int(b.get("uiTokenAmount", {}).get("amount", "0"))
    except (TypeError, ValueError): return 0

def dec(b):
    try: return int(b.get("uiTokenAmount", {}).get("decimals", 0))
    except (TypeError, ValueError): return 0

def keys(tx):
    raw = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])
    out = [{"pubkey": k.get("pubkey",""), "signer": bool(k.get("signer",False))} if isinstance(k,dict) else {"pubkey":str(k),"signer":False} for k in raw]
    if out and not any(x["signer"] for x in out): out[0]["signer"] = True
    return out

def signer_of(tx):
    ks = keys(tx)
    return next((k["pubkey"] for k in ks if k["signer"]), ks[0]["pubkey"] if ks else "")

def owner_delta(tx, mint, owner):
    meta = tx.get("meta") or {}
    pre, post = meta.get("preTokenBalances"), meta.get("postTokenBalances")
    if pre is None or post is None: return None, "missing_token_balance_metadata"
    def total(entries):
        value, decimals = 0, None
        for x in entries:
            if x.get("mint") == mint and x.get("owner") == owner:
                value += amt(x)
                if decimals is None: decimals = dec(x)
        return value, decimals
    a, da = total(pre); b, db = total(post)
    d = db if db is not None else da
    if d is None: return None, "no_signer_token_account_for_mint"
    return (b-a)/(10**d), "ok"

def sol_delta(tx, owner):
    meta = tx.get("meta") or {}
    ks = keys(tx); pubkeys = [x["pubkey"] for x in ks]
    if owner not in pubkeys: return None, meta.get("fee")
    i = pubkeys.index(owner); pre = meta.get("preBalances") or []; post = meta.get("postBalances") or []
    if i >= len(pre) or i >= len(post): return None, meta.get("fee")
    return int(post[i])-int(pre[i]), meta.get("fee")

def hint(logs):
    for line in logs or []:
        if "Instruction: BuyExactQuoteIn" in line: return "BuyExactQuoteIn"
        if "Instruction: Buy" in line: return "Buy"
        if "Instruction: Sell" in line: return "Sell"
    return ""

def quote_delta(tx, owner, target_mint):
    meta = tx.get("meta") or {}; allb = (meta.get("preTokenBalances") or []) + (meta.get("postTokenBalances") or [])
    mints = {x.get("mint") for x in allb if x.get("owner") == owner and x.get("mint") and x.get("mint") != target_mint}
    found = []
    for mint in mints:
        delta, _ = owner_delta(tx, mint, owner)
        if delta is not None and abs(delta) > 0: found.append((mint, delta))
    if len(found) == 1: return found[0][1], "single_non_target_mint:" + found[0][0]
    if len(found) > 1: return None, "multiple_non_target_mints"
    return None, "no_non_target_token_delta"

def process(signature, tx, logs):
    meta = tx.get("meta") or {}; err = meta.get("err"); slot = tx.get("slot","")
    bt = tx.get("blockTime"); bt = datetime.fromtimestamp(bt, timezone.utc).isoformat() if bt else ""
    ih = hint(logs); observed = now(); signer = signer_of(tx)
    if err is not None:
        append_csv(ERRORS_CSV, ERROR_FIELDS, {"observed_at_utc":observed,"signature":signature,"slot":slot,"status":"failed","error":json.dumps(err,separators=(",",":")),"instruction_hint":ih,"logs":" | ".join(logs or [])})
        print(f"[FAILED — excluded from stats] {signature[:12]}... error={err}")
        return
    td, tq = owner_delta(tx, TOKEN_MINT, signer)
    sd, fee = sol_delta(tx, signer)
    qd, qq = quote_delta(tx, signer, TOKEN_MINT)
    direction = "unknown" if td is None else ("BUY" if td > 0 else "SELL" if td < 0 else "no_target_token_delta")
    # Signer SOL delta includes possible fees, rent, account closure and unrelated transfers.
    # This is a diagnostic ratio only, never an exact quote or a reliable net-PnL calculation.
    price, price_quality, estimated = "", "not_calculated", ""
    if td is not None and abs(td) > 0 and sd is not None:
        estimated = -sd
        price = abs(sd)/1_000_000_000/abs(td)
        price_quality = "rough_signer_balance_ratio_not_exact_quote"
    elif qd is not None:
        price_quality = "quote_mint_delta_detected_but_exact_price_not_calculated"
    append_csv(EVENTS_CSV, EVENT_FIELDS, {"observed_at_utc":observed,"signature":signature,"slot":slot,"block_time_utc":bt,"status":"success","instruction_hint":ih,"direction":direction,"token_mint":TOKEN_MINT,"token_delta":td if td is not None else "","quote_mint_delta":qd if qd is not None else "","signer":signer,"signer_sol_delta_lamports":sd if sd is not None else "","tx_fee_lamports":fee if fee is not None else "","estimated_sol_spent_or_received_lamports":estimated,"price_sol_per_token_est":price,"price_quality":price_quality+";"+tq+";"+qq,"error":""})
    print(f"[SUCCESS] {direction} sig={signature[:12]}... token_delta={td if td is not None else 'unknown'} price_est={price or 'n/a'} (rough only)")

async def fetch_process(signature, logs):
    try:
        tx = None
        for attempt in range(4):
            try:
                tx = await asyncio.to_thread(rpc_call, "getTransaction", [signature, {"encoding":"jsonParsed","commitment":COMMITMENT,"maxSupportedTransactionVersion":0}], 12)
                if tx is not None: break
            except Exception:
                if attempt == 3: raise
            await asyncio.sleep(0.35*(attempt+1))
        if tx is None:
            append_csv(ERRORS_CSV, ERROR_FIELDS, {"observed_at_utc":now(),"signature":signature,"status":"transaction_not_available","error":"getTransaction returned null after retries","instruction_hint":hint(logs),"logs":" | ".join(logs or [])})
            print(f"[NOT AVAILABLE YET] {signature[:12]}...")
        else: process(signature, tx, logs)
    except Exception as exc:
        append_csv(ERRORS_CSV, ERROR_FIELDS, {"observed_at_utc":now(),"signature":signature,"status":"processing_error","error":repr(exc),"instruction_hint":hint(logs),"logs":" | ".join(logs or [])})
        print(f"[PROCESS ERROR] {signature[:12]}... {exc}")
    finally:
        IN_FLIGHT.discard(signature)

async def main():
    ensure_csv(EVENTS_CSV, EVENT_FIELDS); ensure_csv(ERRORS_CSV, ERROR_FIELDS)
    print("Solana PumpSwap live swap monitor — analytics only, NO TRADING")
    print("Pool:", POOL_ADDRESS); print("Target mint:", TOKEN_MINT)
    print("Success CSV:", EVENTS_CSV); print("Errors CSV:", ERRORS_CSV)
    print("Ctrl+C to stop. Public RPC can be rate-limited.")
    while True:
        try:
            async with websockets.connect(RPC_WS, ping_interval=20, ping_timeout=20, close_timeout=5, max_size=2**22) as ws:
                await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"logsSubscribe","params":[{"mentions":[POOL_ADDRESS]},{"commitment":COMMITMENT}]}))
                reply = json.loads(await ws.recv())
                if "error" in reply: raise RuntimeError(reply["error"])
                print("Subscribed:", reply.get("result"))
                async for raw in ws:
                    try:
                        msg = json.loads(raw); value = msg.get("params",{}).get("result",{}).get("value",{})
                        sig = value.get("signature")
                        if not sig or sig in SEEN or sig in IN_FLIGHT: continue
                        SEEN.add(sig)
                        if len(SEEN) > 100000: SEEN.clear(); SEEN.add(sig)
                        logs = value.get("logs") or []
                        IN_FLIGHT.add(sig)
                        asyncio.create_task(fetch_process(sig, logs))
                    except Exception as exc: print("[MESSAGE ERROR]", exc)
        except asyncio.CancelledError: raise
        except KeyboardInterrupt: raise
        except Exception as exc:
            print("[WS ERROR]", exc, "— reconnecting in 3 sec")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\nStopped cleanly.")
