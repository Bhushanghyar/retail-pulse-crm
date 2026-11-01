import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('database.db')
# Create a Sales Staff member (Password: sales123)
pw = generate_password_hash('sales123')
conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
             ('bhushan_sales', pw, 'Sales Staff'))
conn.commit()
conn.close()
print("Sales account created!")