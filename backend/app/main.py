from fastapi import FastAPI

from app.messaging.redis_client import redis_client
from app.messaging.event_consumer import get_events


app = FastAPI(
    title="CCTV AI Intelligent Surveillance",
    version="1.0.0"
)


@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }


@app.get("/redis-test")
async def redis_test():

    result = await redis_client.ping()

    return {
        "redis": "connected" if result else "not connected"
    }


@app.get("/events/detection")
async def detection_events():

    events = await get_events()

    return {
        "stream": "events.detection",
        "count": len(events),
        "events": events
    }