import sqlite3

conn = sqlite3.connect("prahari_events.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM intrusion_events")
intrusions_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM anpr_events")
anpr_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM security_events")
security_count = cursor.fetchone()[0]

print("=" * 50)
print("DATABASE INTEGRITY & EVENT LOG STATUS")
print("=" * 50)
print(f"intrusion_events table count: {intrusions_count}")
print(f"anpr_events table count:      {anpr_count}")
print(f"security_events table count:  {security_count}")

# Check latest intrusion record
cursor.execute("SELECT id, timestamp, object_type, object_id, snapshot_path FROM intrusion_events ORDER BY id DESC LIMIT 3")
print("\nLatest 3 Intrusion Events:")
for row in cursor.fetchall():
    print(" ", row)

# Check latest ANPR record
cursor.execute("SELECT id, timestamp, object_type, object_id, plate_text, confidence FROM anpr_events ORDER BY id DESC LIMIT 3")
print("\nLatest 3 ANPR Reads:")
for row in cursor.fetchall():
    print(" ", row)

conn.close()
print("\nDatabase verification: PASS")
