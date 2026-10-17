# 9. 最佳实践

> 一句话理解：写好 MCP Server 的关键是 Schema 清晰、幂等、状态less、错误明确、资源 URI 稳定、Prompt 版本化、观测完整。

## 1. Tool 设计 10 条

1. **命名清晰**：使用动词 + 名词，例如 `read_file`、`search_documents`，避免缩写。
2. **描述具体**：说明 Tool 做什么、返回什么、是否有副作用、需要什么权限。
3. **参数最小化**：只暴露必要参数，避免让模型面对过多选择。
4. **类型明确**：每个参数都要有 JSON Schema 类型、约束、枚举值。
5. **幂等优先**：相同输入应产生相同结果，避免重复调用导致重复副作用。
6. **超时可控**：每个 Tool 都应设置合理的超时，避免阻塞会话。
7. **错误可恢复**：业务错误通过 `isError=true` 返回，附带清晰 message，让模型能重试或换策略。
8. **权限标签**：给 Tool 打标签（read/write/sensitive/external），便于 Host 做授权策略。
9. **输入校验**：Server 层做严格参数校验，不要依赖模型自觉遵守 schema。
10. **避免“万能 Tool”**：一个 Tool 只做一件事，不要把读、写、删、执行混在一个接口里。

示例：好的 Tool schema

```json
{
  "name": "read_file",
  "description": "读取本地文本文件内容，返回文件文本。不会修改文件。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "文件绝对路径，必须在允许的根目录内"
      }
    },
    "required": ["path"]
  }
}
```

## 2. Resource URI 与 MIME 设计

- **URI 稳定**：同一个资源在不同时间用同一个 URI，便于缓存与审计。
- **scheme 语义化**：`file://`、`sqlite://`、`https://`、`kb://` 等。
- **路径分层**：例如 `file:///project/docs/guide.md`，不要在一个 URI 里塞太多参数。
- **MIME type 准确**：文本用 `text/plain`、`text/markdown`，JSON 用 `application/json`，二进制用对应类型。
- **大资源分片**：对于大文件，支持 `offset`/`limit` 或返回摘要链接，避免一次性撑爆上下文。

反例：

```text
# 不好
resource://getUser?id=123&includeOrders=true

# 更好
user://123
user://123/orders
```

## 3. Prompt 模板版本

Prompt 模板也应像 API 一样管理版本：

- 给每个 Prompt 增加 `version` 字段或命名空间，例如 `summarize/v1`。
- Prompt 参数使用 JSON Schema 描述，避免自由文本导致注入。
- Prompt 渲染结果返回结构化 messages，而不是纯字符串。

```json
{
  "name": "summarize/v1",
  "description": "对给定文本生成中文摘要",
  "arguments": [
    {
      "name": "text",
      "description": "需要摘要的文本",
      "required": true,
      "schema": { "type": "string", "maxLength": 10000 }
    }
  ]
}
```

## 4. Capability 声明最小化

Server 应只声明真正支持的能力：

- 不要声明 `listChanged` 如果你不会主动推送变更。
- 不要声明 `subscribe` 如果你不支持 Resource 订阅。
- Capability 声明过多会让 Client 产生错误预期，增加调试成本。

## 5. 错误处理

- **协议级错误**：用 JSON-RPC error code，例如参数错误返回 `-32602`。
- **业务级错误**：用 `tools/call` 的 `isError=true`，并把错误信息放在 `content` 里。
- **不要泄露敏感信息**：错误 message 中不要包含堆栈、密钥、内部路径。
- **统一错误格式**：所有 Tool 返回的错误结构保持一致。

```json
{
  "content": [
    {
      "type": "text",
      "text": "文件 /secret.txt 不存在或无权访问"
    }
  ],
  "isError": true
}
```

## 6. Tracing

从 Day 0 开始设计观测：

- 每个 Tool 调用生成一个 span，包含 tool name、arguments hash、duration、status。
- 记录 capability 协商结果，便于排查版本不兼容问题。
- 记录 Notification 事件，尤其是 `list_changed` 和 `updated`。
- 把 MCP trace 与 Host/Runtime 的 trace 关联起来，使用同一个 trace_id。

## 7. 测试策略

- **单元测试**：每个 Tool/Resource/Prompt Handler 独立测试。
- **协议测试**：模拟 Client 发送 initialize、list、call，验证响应格式。
- **集成测试**：启动真实 Server 子进程，跑完整会话。
- **安全测试**：越权参数、路径遍历、SQL 注入、命令注入。
- **性能测试**：大 Resource 读取、高并发 Tool 调用、长连接稳定性。

## 8. 避免 MCP 成为“另一个 RPC”

MCP 的价值在于“模型视角的能力发现”，而不是替代 gRPC/REST：

- 不要为了用 MCP 而用 MCP，适合的场景是“模型需要动态发现外部能力”。
- 内部微服务之间的调用仍然可以用 gRPC/REST。
- MCP Server 内部可以调用 gRPC/REST/数据库，但对外暴露的是模型友好的 schema。

## 9. 安全红线

- 不要把 Host 的 LLM API key 直接传给 Server。
- Server 不应直接访问网络，除非明确需要（如 fetch Server）。
- 写操作必须做路径白名单、参数校验、HITL。
- 不要在 Server 里执行不受信任的代码，危险操作必须进沙箱。
- Server 进程应以最小权限运行，避免继承 Host 的全部权限。
- **工具描述也可能带毒**：描述文本是给模型读的“提示词”，投毒者会在描述里藏指令。Host/网关应对 `tools/list` 结果做完整性基线（哈希指纹），检测定义被静默替换（rug pull）。
- **不要把 STDIO Server 配置当成普通配置**：`command`/`args` 会被原样执行，配置入口必须白名单校验，防命令注入（2026 年多起 CVE 的根因）。

## 10. 供应链与依赖治理

- **版本锁定**：`--save-exact`、lockfile、升级时做 SBOM diff；不追“latest”。
- **安装前扫描**：用 mcp-scan / Snyk Agent Scan 检查工具投毒、影子化、有毒数据流；扫描在隔离沙箱中执行。
- **私有 Registry 白名单**：企业内部只允许从私有 Registry 安装 Server，公共目录（官方 Registry、Smithery、mcp.so）只作发现层。
- **每台 Server 有 owner**：登记维护人、权限标签、最近扫描时间与审批状态。
- **遵循 OWASP MCP Top 10**：把工具投毒（MCP03）、敏感数据泄露、权限过大等条目纳入发布检查单。

## 11. 面向 2026-07-28 的新实践

- **无状态优先**：新 Server 直接按 2026-07-28 实现，不引入会话存储；需要用户输入时用 MRTR（`resultType: "input_required"` + `requestState`），不要再依赖 Server 反向调用 Client。
- **声明缓存提示**：`tools/list` 等结果给出合理的 `ttlMs`/`cacheScope`，帮 Client 与网关缓存目录、降低发现开销。
- **能力目录确定性排序**：保证列表按稳定顺序返回，让指纹比对与缓存生效。
- **迁移期双模**：用官方 SDK v2 让同一端点服务两代客户端；把 `Mcp-Method`/`Mcp-Name` 头的存在性作为路由与观测标签。
- **弃用项不新建**：不要再在新 Server 中实现 Roots、Sampling、Logging 与 HTTP+SSE（有 12 个月兼容义务的是存量，不是新代码）。

## 12. 文档与示例

- 每个 Server 都应提供 README，说明如何安装、配置、运行。
- 提供示例 Host 配置（Claude Desktop、Cursor、OpenAI Agents SDK）。
- 列出所需权限、环境变量、已知限制。
- 提供测试命令与预期输出。

## 本章小结

写好 MCP Server 不仅是实现几个 Tool，而是要从协议语义、模型友好性、安全边界、可观测性、版本管理、供应链治理等多个维度做设计。核心原则是：Server 声明清晰、Client 调用简单、Host 控制安全。2026 年的新增命题是：把 Server 当作不可信第三方来防——哈希基线工具定义、沙箱扫描、网关代理、凭证短期化，遵循这些最佳实践，才能避免 MCP 沦为“又一个 RPC 层”或“下一个供应链破口”。

**参考来源**

- [MCP Specification（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28)
- [CSA: Agentic MCP Security Best Practices](https://labs.cloudsecurityalliance.org/agentic/agentic-mcp-security-best-practices-v1/)
- [MCP Tool Poisoning: Enterprise Defense Playbook 2026](https://beyondscale.tech/blog/mcp-tool-poisoning-enterprise-defense)
- [MCP Tool Poisoning Attacks and Defenses 2026](https://safeguard.sh/resources/blog/mcp-tool-poisoning-attacks-2026)
- [Cloudflare: The next generation of MCP](https://blog.cloudflare.com/mcp-v2)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Claude Code MCP Docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [MCP Reference Servers](https://github.com/modelcontextprotocol/servers)
