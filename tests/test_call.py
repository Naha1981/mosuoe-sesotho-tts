from app.call import CallSession


def test_call_session_keeps_recent_history():
    session = CallSession("test-call")
    for i in range(25):
        session.add_turn("user", f"turn {i}")
    assert len(session.history) == 20
    assert session.history[0]["text"] == "turn 5"
