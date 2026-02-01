from sqlalchemy import create_engine, text
import os

DATABASE_URL = "sqlite:///./migrant.db"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Forcing migration...")
    
    # Try adding created_at
    try:
        print("Adding created_at...")
        conn.execute(text("ALTER TABLE visits ADD COLUMN created_at DATETIME"))
        print("created_at added.")
    except Exception as e:
        print(f"Skipping created_at: {e}")

    # Try adding synced
    try:
        print("Adding synced...")
        conn.execute(text("ALTER TABLE visits ADD COLUMN synced BOOLEAN"))
        print("synced added.")
    except Exception as e:
        print(f"Skipping synced: {e}")

    print("Migration complete.")
