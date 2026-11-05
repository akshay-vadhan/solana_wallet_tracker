import asyncio
import logging
import random


from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    RPCError,
)

from config import (
    API_HASH,
    API_ID,
    PHONE,
    SESSION_PATH,
    TELEGRAM_CHAT_ID,
    TRACKED_WALLETS,
)
from parser import parse_notification
from storage import init_db, ensure_trade_columns, save_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("wallet_tracker")


def validate_config():
    if not API_ID.isdigit() or not API_HASH or not PHONE:
        raise RuntimeError(
            "Set TELEGRAM_API_ID, TELEGRAM_API_HASH and "
            "TELEGRAM_PHONE in .env"
        )
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Set TELEGRAM_CHAT_ID in .env. "
            "Run the chat-discovery command first."
        )


async def main():
    validate_config()
    init_db()
    ensure_trade_columns()

    client = TelegramClient(
        SESSION_PATH,
        int(API_ID),
        API_HASH,
        auto_reconnect=True,
        connection_retries=10,
        retry_delay=3,
    )

    await client.start(phone=PHONE)

    # Resolve the exact chat configured in .env.
    chat = await client.get_entity(TELEGRAM_CHAT_ID)
    chat_id = str(chat.id)

    log.info("Connected to Telegram.")
    log.info("Monitoring configured chat ID: %s", chat_id)
    log.info("Tracked wallets configured: %d", len(TRACKED_WALLETS))
    log.info("Paper-trading execution is NOT enabled in this step.")

    @client.on(events.NewMessage(chats=chat))
    async def on_new_message(event):
        try:
            raw_text = event.raw_text or ""

            sender = await event.get_sender()
            sender_name = (
                getattr(sender, "username", None)
                or getattr(sender, "first_name", None)
                or type(sender).__name__
                if sender is not None
                else None
            )

            parsed = parse_notification(raw_text, TRACKED_WALLETS)

            saved = save_event(
                chat_id=event.chat_id,
                message_id=event.id,
                message_date=(
                    event.message.date.isoformat()
                    if event.message.date else None
                ),
                sender_id=event.sender_id,
                sender_name=sender_name,
                raw_text=raw_text,
                parsed=parsed,
            )

            if saved:
                log.info(
                    "Saved message=%s side=%s wallet=%s status=%s",
                    event.id,
                    parsed["side"],
                    parsed["wallet_label"],
                    parsed["parser_status"],
                )
            else:
                log.info("Duplicate ignored: message=%s", event.id)

        except FloodWaitError as exc:
            log.error("Telegram rate limit: wait %s seconds", exc.seconds)
            await asyncio.sleep(exc.seconds)
        except (RPCError, OSError):
            log.exception("Telegram/database I/O error processing message")
        except Exception:
            # Keep the listener running if a single message is malformed.
            log.exception("Unexpected message-processing error")

    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    delay = 3

    while True:
        try:
            asyncio.run(main())
            break  # Normal disconnect; stop instead of reconnecting forever.
        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception:
            log.exception("Listener failed; retrying shortly.")
            wait = min(delay, 60) + random.uniform(0, 1)
            import time
            time.sleep(wait)
            delay = min(delay * 2, 60)