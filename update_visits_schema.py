from sqlalchemy import create_engine, inspect, text
import os

# Correct DB URL from db.py
DATABASE_URL = "sqlite:///./swasth_v2.db"
engine = create_engine(DATABASE_URL)

try:
    inspector = inspect(engine)
    if not inspector.has_table("visits"):
        print("Table 'visits' does not exist.")
    else:
        columns = [c['name'] for c in inspector.get_columns("visits")]
        print(f"Existing columns: {columns}")
        
        with engine.connect() as conn:
            if "doctor_name" not in columns:
                print("Adding missing column: doctor_name")
                try:
                    conn.execute(text("ALTER TABLE visits ADD COLUMN doctor_name VARCHAR"))
                except Exception as e:
                    print(f"Error adding doctor_name: {e}")

            if "specialization" not in columns:
                print("Adding missing column: specialization")
                try:
                    conn.execute(text("ALTER TABLE visits ADD COLUMN specialization VARCHAR"))
                except Exception as e:
                    print(f"Error adding specialization: {e}")
                    
            if "attachments" not in columns:
                print("Adding missing column: attachments")
                try:
                    conn.execute(text("ALTER TABLE visits ADD COLUMN attachments VARCHAR"))
                except Exception as e:
                    print(f"Error adding attachments: {e}")

            conn.commit()
            print("Migration complete.")

except Exception as e:
    print(f"Migration failed: {e}")
