from security_mini.policy import is_allowed, list_allowed_actions


def test_admin_can_do_anything():
    assert is_allowed("admin", "llm:chat")
    assert is_allowed("admin", "llm:admin")
    assert is_allowed("admin", "rag:search")


def test_developer_can_chat_and_search():
    assert is_allowed("developer", "llm:chat")
    assert is_allowed("developer", "rag:search")
    assert not is_allowed("developer", "llm:admin")


def test_readonly_can_only_chat():
    assert is_allowed("readonly", "llm:chat")
    assert not is_allowed("readonly", "rag:search")
    assert not is_allowed("readonly", "llm:admin")


def test_unknown_role_denied():
    assert not is_allowed("guest", "llm:chat")


def test_list_permissions():
    assert list_allowed_actions("developer") == ["llm:chat", "rag:search"]
