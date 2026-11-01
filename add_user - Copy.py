import sqlite3
from werkzeug.security import generate_password_hash

def create_sales_user():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Hash the password 'sales123' so it matches your login logic
    hashed_pw = generate_password_hash('sales123')

    try:
        # Re-adding the user lost during the hard reset
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       ('bhushan_sales', hashed_pw, 'Employee'))
        conn.commit()
        print("✅ User 'bhushan_sales' successfully created!")
        print("You can now log in with username: bhushan_sales and password: sales123")
    except sqlite3.IntegrityError:
        print("❌ Error: That username already exists.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

    conn.close()

if __name__ == "__main__":
    create_sales_user()