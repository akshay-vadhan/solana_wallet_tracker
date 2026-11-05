import json
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            message_date TEXT,
            received_at TEXT NOT NULL,
            sender_id TEXT,
            sender_name TEXT,
            raw_text TEXT NOT NULL,
            side TEXT,
            wallet_address TEXT,
            wallet_label TEXT,
            addresses_json TEXT,
            tx_signature TEXT,
            token_amount TEXT,
            sol_amount TEXT,
            usdc_amount TEXT,
            usd_amount TEXT,
            price_usd TEXT,
            reported_pnl TEXT,
            parser_status TEXT NOT NULL,
            UNIQUE(chat_id, message_id)
        )
        """)
        # Existing table mein missing column add karega.
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(telegram_events)")
        }

        if "trader_label" not in existing:
            conn.execute(
                "ALTER TABLE telegram_events ADD COLUMN trader_label TEXT"
            )

def ensure_trade_columns():
    new_columns = {
        "trader_label": "TEXT",
        "token_name": "TEXT",
        "token_ca": "TEXT",
        "market_cap_raw": "TEXT",
        "market_cap_usd": "REAL",
        "buy_mc_usd": "REAL",
        "sell_mc_usd": "REAL",
        "size_usd": "REAL",
        "price_raw": "TEXT",
        "pnl_usd": "REAL",
        "pnl_percent": "REAL",
    }

    with connect_db() as conn:
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(telegram_events)")
        }

        for name, sql_type in new_columns.items():
            if name not in existing:
                conn.execute(
                    f"ALTER TABLE telegram_events "
                    f"ADD COLUMN {name} {sql_type}"
                )



def save_event(
    chat_id, message_id, message_date, sender_id,
    sender_name, raw_text, parsed
):
    with connect_db() as conn:
        cursor = conn.execute("""
        INSERT OR IGNORE INTO telegram_events (
            chat_id, message_id, message_date, received_at,
            sender_id, sender_name, raw_text,
            side, wallet_address, wallet_label, addresses_json,
            tx_signature, token_amount, sol_amount, usdc_amount,
            usd_amount, price_usd, reported_pnl, parser_status,
            trader_label, token_name, token_ca,
            market_cap_raw, market_cap_usd, buy_mc_usd, sell_mc_usd,
            size_usd, price_raw, pnl_usd, pnl_percent
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            str(chat_id),
            int(message_id),
            message_date,
            utc_now(),
            str(sender_id) if sender_id is not None else None,
            sender_name,
            raw_text,
            parsed.get("side"),
            parsed.get("wallet_address"),
            parsed.get("wallet_label"),
            json.dumps(parsed.get("addresses_found", [])),
            None,  # tx_signature: this alert format doesn't show one
            None,  # token_amount
            None,  # sol_amount
            None,  # usdc_amount
            parsed.get("size_usd"),
            parsed.get("price_raw"),
            (
                f'{parsed["pnl_usd"]:+.2f}'
                if parsed.get("pnl_usd") is not None else None
            ),
            parsed.get("parser_status", "needs_review"),
            parsed.get("trader_label"),
            parsed.get("token_name"),
            parsed.get("token_ca"),
            parsed.get("market_cap_raw"),
            parsed.get("market_cap_usd"),
            parsed.get("buy_mc_usd"),
            parsed.get("sell_mc_usd"),
            parsed.get("size_usd"),
            parsed.get("price_raw"),
            parsed.get("pnl_usd"),
            parsed.get("pnl_percent"),
        ))

        return cursor.rowcount == 1
