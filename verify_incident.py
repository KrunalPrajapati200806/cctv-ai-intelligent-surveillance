import sqlite3

incident_id = "acd81208-a681-40b1-b92b-0b99a1c41888"

conn = sqlite3.connect("data/incidents.db")

row = conn.execute(
    """
    SELECT
        incident_id,
        alert_event_id,
        camera_id,
        event_type,
        severity,
        status
    FROM incidents
    WHERE incident_id = ?
    """,
    (incident_id,),
).fetchone()

print("RESULT:", row)

conn.close()
