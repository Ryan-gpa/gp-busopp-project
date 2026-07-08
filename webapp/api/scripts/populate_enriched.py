import sqlite3
import os
db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'companies.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("INSERT OR REPLACE INTO enriched_data VALUES ('123456789', 4000000000, 8066, '[]', '2026-07-08')")
c.execute("INSERT OR REPLACE INTO enriched_data VALUES ('987654321', 5215304000, 11000, '[]', '2026-07-08')")
c.execute("INSERT OR REPLACE INTO enriched_data VALUES ('111222333', 35000000, 600, '[]', '2026-07-08')")

conn.commit()
conn.close()
print("Populated enriched_data with mock data!")
