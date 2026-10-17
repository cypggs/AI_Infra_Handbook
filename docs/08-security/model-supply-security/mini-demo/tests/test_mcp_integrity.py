"""S3 测试：MCP 工具清单完整性（rug pull 与 tool poisoning）。"""

from supply_security_mini.mcp_integrity import (
    STATUS_DESCRIPTION_CHANGED,
    STATUS_HASH_MISMATCH,
    STATUS_OK,
    STATUS_UNKNOWN_TOOL,
    Client,
    Registry,
    make_email_tools,
)

SERVER = "email-server"


def _setup() -> tuple[Registry, Client, object, list]:
    registry = Registry("toy")
    client = Client()
    v1_tools = make_email_tools(version=1, poisoned=False)
    v1_manifest = registry.publish(SERVER, 1, v1_tools)
    return registry, client, v1_manifest, v1_tools


class TestPublish:
    def test_manifest_hashes_match_code(self):
        registry = Registry("toy")
        tools = make_email_tools(version=1)
        manifest = registry.publish(SERVER, 1, tools)
        import hashlib

        for tool in tools:
            expect = hashlib.sha256(tool.code.encode()).hexdigest()
            assert manifest.entries[tool.name].code_sha256 == expect

    def test_latest_version_increments(self):
        registry = Registry("toy")
        registry.publish(SERVER, 1, make_email_tools(1))
        registry.publish(SERVER, 2, make_email_tools(2))
        assert registry.latest(SERVER).version == 2


class TestLoad:
    def test_clean_load_ok(self):
        registry, client, v1_manifest, v1_tools = _setup()
        report = client.load(SERVER, v1_tools, v1_manifest, registry)
        assert report.status == STATUS_OK
        assert len(client.loaded[SERVER]) == 2

    def test_rug_pull_blocked(self):
        registry, client, v1_manifest, _ = _setup()
        swapped = make_email_tools(version=2, poisoned=False)  # 服务器私自换码
        report = client.load(SERVER, swapped, v1_manifest, registry)
        assert report.status == STATUS_HASH_MISMATCH
        assert report.blocked_tools == ["send_email", "list_inbox"]
        assert client.loaded[SERVER] == []

    def test_tool_poisoning_description_diff(self):
        registry, client, v1_manifest, _ = _setup()
        poisoned = make_email_tools(version=2, poisoned=True)
        registry.publish(SERVER, 2, poisoned)  # registry 记录了新版本 hash
        report = client.load(SERVER, poisoned, v1_manifest, registry)
        assert report.status == STATUS_DESCRIPTION_CHANGED
        assert set(report.description_diffs) == {"send_email"}
        old, new = report.description_diffs["send_email"]
        assert "explicit user approval" in old
        assert "id_rsa" in new

    def test_poisoned_tools_loaded_but_flagged(self):
        """hash 与 registry 一致时加载不阻断，但描述 diff 必须暴露。"""
        registry, client, v1_manifest, _ = _setup()
        poisoned = make_email_tools(version=2, poisoned=True)
        registry.publish(SERVER, 2, poisoned)
        report = client.load(SERVER, poisoned, v1_manifest, registry)
        assert report.blocked_tools == []
        assert report.description_diffs

    def test_unknown_tool_blocked(self):
        from supply_security_mini.mcp_integrity import Tool

        registry, client, v1_manifest, _ = _setup()
        current = make_email_tools(version=1) + [
            Tool(name="exfil", description="new tool", code="def exfil(): ...")
        ]
        report = client.load(SERVER, current, v1_manifest, registry)
        assert report.status == STATUS_UNKNOWN_TOOL
        assert "exfil" in report.blocked_tools

    def test_missing_tool_blocked(self):
        registry, client, v1_manifest, _ = _setup()
        current = make_email_tools(version=1)[:1]  # 少了 list_inbox
        report = client.load(SERVER, current, v1_manifest, registry)
        assert "list_inbox" in report.blocked_tools

    def test_benign_description_not_flagged(self):
        registry, client, v1_manifest, _ = _setup()
        same = make_email_tools(version=1, poisoned=False)
        registry.publish(SERVER, 2, same)  # 重新发布同内容 v2
        report = client.load(SERVER, same, v1_manifest, registry)
        assert report.description_diffs == {}
