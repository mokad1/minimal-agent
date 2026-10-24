from agent.session import SessionManager


def make_manager(**kw):
    kw.setdefault("system_prompt", "SYS")
    return SessionManager(**kw)


def test_get_or_create_same_id_returns_same_session():
    mgr = make_manager()
    assert mgr.get_or_create("a") is mgr.get_or_create("a")
    assert mgr.get_or_create("a") is not mgr.get_or_create("b")


def test_sessions_are_isolated():
    mgr = make_manager()
    s1 = mgr.get_or_create("w1")
    s2 = mgr.get_or_create("w2")
    s1.store["todos"] = [{"id": 1, "text": "x", "done": False}]
    assert "todos" not in s2.store
    s1.context.add_user("你好")
    assert s2.context.turn_count == 0
