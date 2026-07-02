from __future__ import annotations


def run_demo() -> None:
    """Run a small multi-session memory demonstration."""
    from agent_memory_mini.memory_service import MemoryService

    service = MemoryService()

    print("=" * 60)
    print("Agent Memory Mini Demo")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Session A: the user states a preference.
    # ------------------------------------------------------------------
    session_a = "session-a"
    user_a = "我喜欢 Python，不喜欢 Java"
    service.working.add_message("user", user_a)
    service.working.add_message(
        "assistant", "收到，已记录您对 Python 的偏好和对 Java 的排斥。"
    )
    fact_id = service.remember(
        "fact", user_a, metadata={"session": session_a}
    )
    service.remember(
        "session",
        {
            "session_id": session_a,
            "messages": service.working.get_messages(),
        },
    )
    print(f"\n[Session A] user: {user_a}")
    print(f"Remembered fact id: {fact_id}")

    # ------------------------------------------------------------------
    # Session B: the user asks for a recommendation.
    # ------------------------------------------------------------------
    session_b = "session-b"
    query_b = "推荐一门编程语言"
    service.working.clear()
    service.working.add_message("user", query_b)

    print(f"\n[Session B] user: {query_b}")
    print("\n--- Long-term / hybrid recall ---")
    recalled_facts = service.recall(
        query_b, memory_type="fact", top_k=3
    )
    for r in recalled_facts:
        score = r["score"] if r["score"] is not None else 0.0
        print(
            f"  [{r['memory_type']}] {r['id']} score={score:.3f}: {r['text']}"
        )

    # ------------------------------------------------------------------
    # Episodic memory: recall a similar successful task.
    # ------------------------------------------------------------------
    service.remember(
        "task",
        {
            "goal": "recommend a programming language based on user preference",
            "actions": ["recalled long-term preference", "recommended Python"],
            "outcome": "user accepted the recommendation",
        },
    )
    print("\n--- Episodic recall ---")
    episodes = service.recall(query_b, memory_type="task", top_k=2)
    for ep in episodes:
        print(f"  [{ep['memory_type']}] {ep['id']}:\n{ep['text']}")

    # Build a personalized answer using the recalled preference.
    if recalled_facts:
        preference = recalled_facts[0]["text"]
        answer = (
            f"根据您的记忆（{preference}），我推荐 Python，它语法简洁，"
            "与您喜欢的风格一致。"
        )
    else:
        answer = "我推荐 Python，它是一门通用且社区活跃的编程语言。"
    service.working.add_message("assistant", answer)
    print(f"\n[Final answer]\n{answer}")

    # ------------------------------------------------------------------
    # Hybrid retrieval demo: vector + keyword.
    # ------------------------------------------------------------------
    print("\n--- Hybrid retrieval (vector + keyword) ---")
    service.remember("fact", "Python 适合数据科学与脚本自动化")
    service.remember("fact", "Java 适合大型企业级后端系统")
    service.remember("fact", "Rust 适合高性能系统编程")
    hybrid_results = service.recall(
        "Python 数据", memory_type="fact", top_k=3
    )
    for r in hybrid_results:
        score = r["score"] if r["score"] is not None else 0.0
        print(f"  {r['id']} score={score:.3f}: {r['text']}")

    # ------------------------------------------------------------------
    # Summarization: long working memory -> short-term memory.
    # ------------------------------------------------------------------
    print("\n--- Working memory summarization ---")
    service.working.clear()
    service.working.add_message("system", "你是一个 helpful 助手。")
    for i in range(1, 6):
        service.working.add_message("user", f"问题 {i}: 请解释概念 {i}。")
        service.working.add_message(
            "assistant", f"概念 {i} 是……（此处省略若干字）"
        )
    print(f"Working memory has {len(service.working.get_messages())} messages")
    summary = service.consolidate()
    print(f"Consolidated summary:\n{summary}")
    print("\nShort-term memory context:")
    print(service.short_term.get_context())

    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
