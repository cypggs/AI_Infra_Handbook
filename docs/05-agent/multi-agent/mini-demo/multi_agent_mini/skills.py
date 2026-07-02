"""Built-in skills that agents can execute."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multi_agent_mini.blackboard import Blackboard


def search_facts(query: str, blackboard: "Blackboard") -> str:
    """Write mock research facts to the blackboard."""
    facts = [
        f"Fact 1: {query} improves modularity.",
        "Fact 2: Clear role definitions reduce conflicts.",
        "Fact 3: Shared workspaces enable loose coupling.",
    ]
    blackboard.write("facts", "\n".join(facts), scope="shared")
    return "Facts collected."


def draft_section(topic: str, blackboard: "Blackboard") -> str:
    """Write an outline and draft section to the blackboard."""
    facts = blackboard.read("facts") or "No facts available"
    outline = [
        f"# {topic}",
        "## 1. Introduction",
        "## 2. Key Principles",
        "## 3. Conclusion",
    ]
    draft = "\n".join(outline) + "\n\nDraft:\n" + str(facts)
    blackboard.write("draft", draft, scope="shared")
    return "Draft written."


def review_draft(blackboard: "Blackboard") -> str:
    """Write review comments to the blackboard."""
    draft = blackboard.read("draft")
    if draft is None:
        blackboard.write("review", "No draft to review.", scope="shared")
        return "No draft to review."
    comments = [
        "- Add concrete examples.",
        "- Clarify the conclusion.",
        "- Fix passive voice in section 2.",
    ]
    review = "Review comments:\n" + "\n".join(comments)
    blackboard.write("review", review, scope="shared")
    return "Review complete."


def finalize_post(blackboard: "Blackboard") -> str:
    """Assemble the final blog post from facts, draft, and review."""
    facts = blackboard.read("facts") or ""
    draft = blackboard.read("draft") or ""
    review = blackboard.read("review") or ""
    post = "\n\n".join(
        [
            "# Multi-Agent Collaboration Best Practices",
            "## Research",
            facts,
            "## Draft",
            draft,
            "## Review",
            review,
            "## Status",
            "Finalized and ready for publishing.",
        ]
    )
    blackboard.write("final_post", post, scope="shared")
    return "Final post written."


def handoff_to(target: str, blackboard: "Blackboard") -> str:
    """Record the next agent to take a turn."""
    blackboard.write("next_agent", target, scope="private")
    return f"Handoff to {target}."
