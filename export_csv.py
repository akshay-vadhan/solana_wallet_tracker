import csv

from config import DB_PATH, EXPORT_DIR
from storage import connect_db


def export_events():
    output = EXPORT_DIR / "telegram_events.csv"

    with connect_db() as conn:
        cursor = conn.execute("""
            SELECT *
            FROM telegram_events
            ORDER BY id ASC
        """)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows([tuple(row) for row in rows])

    print(f"Exported {len(rows)} records to: {output}")


if __name__ == "__main__":
    export_events()