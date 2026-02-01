import sqlite3
import os

DB_FILE = "migrant.db"

def fix_db():
    if not os.path.exists(DB_FILE):
        print("DB file not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Get columns
        cursor.execute("PRAGMA table_info(visits)")
        cols = [row[1] for row in cursor.fetchall()]
        print(f"Current columns: {cols}")

        if "created_at" not in cols:
            print("Adding created_at...")
            cursor.execute("ALTER TABLE visits ADD COLUMN created_at DATETIME")
            print("Success.")
        else:
            print("created_at exists.")

        if "synced" not in cols:
            print("Adding synced...")
            cursor.execute("ALTER TABLE visits ADD COLUMN synced BOOLEAN")
            print("Success.")
        else:
            print("synced exists.")

        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_db()
