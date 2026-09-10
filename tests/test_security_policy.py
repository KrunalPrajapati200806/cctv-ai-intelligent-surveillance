import os

CAMERAS_JSON = r'''
[
  {
    "camera_id": "CAM01",
    "name": "Entrance Camera",
    "source": "0",
    "enabled": true,
    "location": "entrance",
    "policy": {
      "normal_objects": ["person"],
      "restricted_objects": [],
      "alert_events": ["intrusion.detected"],
      "sensitivity": 0.7,
      "security_severity": "high",
      "restricted_zone": {
        "x1": 50,
        "y1": 50,
        "x2": 700,
        "y2": 450
      }
    }
  },
  {
    "camera_id": "CAM02",
    "name": "Bank Locker Camera",
    "source": "1",
    "enabled": true,
    "location": "bank-locker",
    "policy": {
      "normal_objects": [],
      "restricted_objects": ["person"],
      "alert_events": ["person.detected"],
      "sensitivity": 0.9,
      "security_severity": "critical",
      "restricted_zone": {
        "x1": 100,
        "y1": 100,
        "x2": 500,
        "y2": 400
      }
    }
  }
]
'''

os.environ["CAMERAS_JSON"] = CAMERAS_JSON

from agents.security.main import SecurityAgent


def test_policy_zones():
    agent = SecurityAgent(agent_id="security-test")

    zone_cam01 = agent._get_security_zone("CAM01")
    zone_cam02 = agent._get_security_zone("CAM02")

    print("CAM01 zone:", zone_cam01)
    print("CAM02 zone:", zone_cam02)

    assert zone_cam01 == (50.0, 50.0, 700.0, 450.0)
    assert zone_cam02 == (100.0, 100.0, 500.0, 400.0)
    assert zone_cam01 != zone_cam02

    print("PASS: camera-specific zones are different")


def test_point_inside_zone():
    agent = SecurityAgent(agent_id="security-test")

    assert agent.point_inside_zone("CAM01", 100, 100) is True
    assert agent.point_inside_zone("CAM01", 800, 500) is False

    assert agent.point_inside_zone("CAM02", 200, 200) is True
    assert agent.point_inside_zone("CAM02", 800, 500) is False

    print("PASS: zone geometry works")


def test_camera_state_isolation():
    agent = SecurityAgent(agent_id="security-test")

    agent.alerted_tracks["CAM01"] = {"track-1"}
    agent.track_last_seen["CAM01"] = {"track-1": 123.0}

    assert agent.alerted_tracks.get("CAM01") == {"track-1"}
    assert "CAM02" not in agent.alerted_tracks

    assert agent.track_last_seen.get("CAM01") == {"track-1": 123.0}
    assert "CAM02" not in agent.track_last_seen

    print("PASS: camera state is isolated")


def test_severity_is_camera_specific():
    agent = SecurityAgent(agent_id="security-test")

    severity_cam01 = agent._get_security_severity("CAM01")
    severity_cam02 = agent._get_security_severity("CAM02")

    print("CAM01 severity:", severity_cam01)
    print("CAM02 severity:", severity_cam02)

    assert severity_cam01 == "high"
    assert severity_cam02 == "critical"

    print("PASS: camera-specific severity works")


if __name__ == "__main__":
    try:
        print("=" * 70)
        print("SECURITY AGENT POLICY TEST")
        print("=" * 70)

        test_policy_zones()
        test_point_inside_zone()
        test_camera_state_isolation()
        test_severity_is_camera_specific()

        print("=" * 70)
        print("RESULT: ALL SECURITY POLICY TESTS PASSED")
        print("=" * 70)

    finally:
        os.environ.pop("CAMERAS_JSON", None)
