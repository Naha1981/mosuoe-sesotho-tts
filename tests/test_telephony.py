from app.call import calls
from app.telephony import CallEvent, TelephonyGateway


def test_telephony_gateway_start_and_end():
    gateway = TelephonyGateway()
    result = gateway.start(
        CallEvent(
            event_type="call.started",
            call_id="gateway-test",
            caller="+26600000000",
            metadata={"provider": "test"},
        )
    )

    assert result["action"] == "speak"
    assert "Lesotho" in result["text"]
    assert calls.get("gateway-test") is not None

    ended = gateway.end("gateway-test")
    assert ended["action"] == "hangup"
    assert calls.get("gateway-test") is None
