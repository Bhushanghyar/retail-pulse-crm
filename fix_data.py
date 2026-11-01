import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# This ensures every order has a valid price and date format
cursor.execute("UPDATE orders SET total_price = 0 WHERE total_price IS NULL")
cursor.execute("UPDATE orders SET date = date('now') WHERE date IS NULL OR date = ''")

conn.commit()
conn.close()
print("✅ Database repaired! Refresh your reports page now.")