# CCTV AI Event Contract

**Contract Version:** 1.0

**Status:** Draft

---

## 1. Purpose

This document defines the communication contract between all
AI agents, backend services, and frontend components in the
CCTV AI Intelligent Surveillance System.

The system follows an event-driven architecture.

Components communicate through Redis Streams rather than
directly depending on each other's internal implementation.

---

# 2. Event Architecture

The basic communication pattern is:

CCTV Video
    ↓
AI Agent
    ↓
Event
    ↓
Redis Stream
    ↓
Consumer
    ↓
Processing / Incident / Backend
    ↓
Frontend

An event producer does not need to know how the consumer
internally processes the event.

---

# 3. General Event Structure

Every event MUST contain the following fields:

| Field | Type | Required | Description |
|---|---|---|---|
| event_id | string | Yes | Unique identifier for the event |
| event_type | string | Yes | Type of event |
| version | string | Yes | Event contract version |
| timestamp | string | Yes | UTC timestamp |
| source | object | Yes | Agent/service that generated the event |
| camera | object | Yes | CCTV camera information |
| data | object | Yes | Event-specific information |

Example:

```json
{
  "event_id": "evt_123456",

  "event_type": "person.detected",

  "version": "1.0",

  "timestamp": "2026-08-29T10:30:00Z",

  "source": {
    "agent_id": "person-detector-01"
  },

  "camera": {
    "camera_id": "CAM01"
  },

  "data": {}
}