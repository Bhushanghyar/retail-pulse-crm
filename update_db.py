import sqlite3

def force_update():
    try:
        conn = sqlite3.connect('database.db')
        # This is the specific command to fix your error
        conn.execute("ALTER TABLE products ADD COLUMN market_price REAL DEFAULT 0")
        conn.commit()
        conn.close()
        print("✅ Success! The 'market_price' column has been added to the database.")
    except sqlite3.OperationalError:
        print("ℹ️ The column already exists or the database was already updated.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    force_update()