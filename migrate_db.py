from sqlalchemy import create_engine, inspect, text
import os

DATABASE_URL = "sqlite:///./migrant.db"
engine = create_engine(DATABASE_URL)

try:
    inspector = inspect(engine)
    if not inspector.has_table("visits"):
        print("Table 'visits' does not exist. It will be created by main.py.")
    else:
        columns = [c['name'] for c in inspector.get_columns("visits")]
        print(f"Existing columns: {columns}")
        
        with engine.connect() as conn:
            if "created_at" not in columns:
                print("Adding missing column: created_at")
                try:
                    conn.execute(text("ALTER TABLE visits ADD COLUMN created_at DATETIME"))
                except Exception as e:
                    print(f"Error adding created_at: {e}")

            if "synced" not in columns:
                print("Adding missing column: synced")
                try:
                    conn.execute(text("ALTER TABLE visits ADD COLUMN synced BOOLEAN"))
                except Exception as e:
                    print(f"Error adding synced: {e}")
                    
            if "referred" not in columns:
                 # Check other fields just in case
                 print("Adding missing column: referred")
                 conn.execute(text("ALTER TABLE visits ADD COLUMN referred BOOLEAN"))

            print("Migration check complete.")

except Exception as e:
    print(f"Migration failed: {e}")
