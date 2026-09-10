import json
import redis
from shared.schemas.event_schema import BaseEvent

r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
)

messages = r.xrange("events.alerts", "-", "+")

bad = []
good = []

for message_id, fields in messages:
    raw = fields.get("event", "")

    try:
        payload = json.loads(raw)
        BaseEvent.model_validate(payload)
        good.append(message_id)
    except Exception:
        bad.append(message_id)

print("TOTAL =", len(messages))
print("BAD   =", len(bad))
print("GOOD  =", len(good))

if bad:
    print("BAD IDS:")
    for message_id in bad:
        print(" ", message_id)

    acked = r.xack(
        "events.alerts",
        "evidence-workers",
        *bad,
    )

    print("ACKED_BAD =", acked)
else:
    print("No malformed events found.")
