import asyncio

from telethon import TelegramClient
from config import API_ID, API_HASH, PHONE, SESSION_PATH


async def main():
    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)
    await client.start(phone=PHONE)

    async for dialog in client.iter_dialogs():
        print(
            f"ID={dialog.id} | "
            f"NAME={dialog.name} | "
            f"ENTITY={type(dialog.entity).__name__}"
        )

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())