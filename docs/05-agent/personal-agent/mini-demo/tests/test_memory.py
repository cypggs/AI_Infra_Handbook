from personal_agent_mini.clock import FakeClock
from personal_agent_mini.memory import PersonalMemory

TS = FakeClock("2026-10-17T08:00:00").now()


def _memory_with(*contents: str) -> PersonalMemory:
    mem = PersonalMemory()
    for c in contents:
        mem.add_episode("user", c, TS)
    return mem


def test_episode_ids_start_at_one():
    mem = PersonalMemory()
    ep1 = mem.add_episode("user", "第一条", TS)
    ep2 = mem.add_episode("agent", "第二条", TS)
    assert ep1.id == "ep1"
    assert ep2.id == "ep2"


def test_recall_matches_by_token_overlap():
    mem = _memory_with("周末在咖啡馆喝了燕麦拿铁", "今天天气不错")
    hits = mem.recall("咖啡")
    assert len(hits) == 1
    assert "燕麦拿铁" in hits[0].content


def test_recall_orders_by_score_then_id():
    mem = _memory_with("咖啡 咖啡", "咖啡")
    hits = mem.recall("咖啡")
    assert hits[0].id == "ep1"  # higher score first
    assert hits[1].id == "ep2"


def test_recall_limit():
    mem = _memory_with("咖啡A", "咖啡B", "咖啡C")
    assert len(mem.recall("咖啡", limit=2)) == 2


def test_recall_empty_when_no_overlap():
    mem = _memory_with("今天天气不错")
    assert mem.recall("咖啡") == []


def test_recall_day_filter():
    mem = PersonalMemory()
    clock = FakeClock("2026-10-14T09:00:00")
    mem.add_episode("user", "周记一", clock.now())
    clock.advance(days=3)
    mem.add_episode("user", "周记二", clock.now())
    assert [ep.content for ep in mem.recall_day("2026-10-14")] == ["周记一"]
    assert [ep.content for ep in mem.recall_day("2026-10-17")] == ["周记二"]


def test_recall_kind_filter():
    mem = PersonalMemory()
    mem.add_episode("user", "咖啡续杯", TS)
    mem.add_episode("email", "咖啡促销邮件", TS)
    hits = mem.recall("咖啡", kind="email")
    assert len(hits) == 1
    assert hits[0].kind == "email"


def test_profile_extracted_from_remember_marker():
    mem = PersonalMemory()
    mem.add_episode("user", "记住：咖啡偏好=燕麦拿铁", TS)
    fact = mem.profile()["咖啡偏好"]
    assert fact.value == "燕麦拿铁"
    assert fact.source == "ep1"  # provenance kept


def test_remember_marker_does_not_fire_on_non_user_episodes():
    mem = PersonalMemory()
    mem.add_episode("email", "记住：咖啡偏好=燕麦拿铁", TS)
    assert mem.profile() == {}


def test_explicit_remember_and_forget():
    mem = PersonalMemory()
    mem.remember("过敏", "坚果", TS)
    assert mem.profile()["过敏"].value == "坚果"
    assert mem.forget("过敏") is True
    assert mem.forget("过敏") is False
    assert mem.profile() == {}


def test_profile_match_query():
    mem = PersonalMemory()
    mem.add_episode("user", "记住：咖啡偏好=燕麦拿铁", TS)
    mem.add_episode("user", "记住：重要联系人=老板 <boss@corp.com>", TS)
    hits = mem.profile_match("咖啡喝什么")
    assert len(hits) == 1
    assert hits[0].key == "咖啡偏好"
