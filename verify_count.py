import sqlite3

conn = sqlite3.connect("data/incidents.db")

count = conn.execute(
    "SELECT COUNT(*) FROM incidents"
).fetchone()[0]

print("COUNT:", count)

conn.close()
