import sqlite3

def check_db():
    conn = sqlite3.connect('migrant.db')
    cursor = conn.cursor()
    with open('db_dump.txt', 'w', encoding='utf-8') as f:
        try:
            # List all tables
            f.write("--- ALL TABLES ---\n")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            for row in cursor.fetchall():
                f.write(f"{row[0]}\n")

            f.write("\n--- PROFILES ---\n")
            cursor.execute("SELECT id, mobile, name FROM profiles")
            for row in cursor.fetchall():
                f.write(f"Profile: ID={row[0]}, Mobile='{row[1]}', Name='{row[2]}'\n")
                
            f.write("\n--- HEALTH IDs ---\n")
            cursor.execute("SELECT id, mobile, health_id FROM health_ids")
            for row in cursor.fetchall():
                f.write(f"HealthID: ID={row[0]}, Mobile='{row[1]}', HID='{row[2]}'\n")

            f.write("\n--- OTPs (If exists) ---\n")
            try:
                cursor.execute("SELECT * FROM otps") # Assuming table name is 'otps' or 'otp'
                for row in cursor.fetchall():
                    f.write(f"OTP Row: {row}\n")
            except Exception as e:
                f.write(f"Could not read otps table: {e}\n")

        except Exception as e:
            f.write(f"Error: {e}\n")
        finally:
            conn.close()

if __name__ == "__main__":
    check_db()
