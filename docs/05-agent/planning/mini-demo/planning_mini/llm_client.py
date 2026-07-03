"""Deterministic mock LLM client for planning and replanning."""
from __future__ import annotations

from typing import Any, Dict, List


class MockLLMClient:
    """A deterministic stand-in for an LLM planner.

    The client never calls an external service. It maps task keywords to a
    hard-coded plan and returns a tailored alternative plan when a replan is
    requested.
    """

    def generate_plan(self, task: str, tools: List[str]) -> Dict[str, Any]:
        """Return a fixed plan JSON for recognized travel tasks.

        Args:
            task: User request in natural language.
            tools: Available tool names (ignored in this mock, but present for
                interface compatibility).

        Returns:
            A dictionary with a ``steps`` list.
        """
        if all(kw in task for kw in ("北京", "东京", "旅行")):
            return {
                "steps": [
                    {
                        "id": "search_flight",
                        "tool": "search_flight",
                        "args": {"origin": "北京", "dest": "东京"},
                        "deps": [],
                    },
                    {
                        "id": "search_hotel",
                        "tool": "search_hotel",
                        "args": {"city": "东京", "nights": 3},
                        "deps": [],
                    },
                    {
                        "id": "calculate_total",
                        "tool": "calculate_total",
                        "args": {
                            "flight_price": "search_flight",
                            "hotel_price": "search_hotel",
                        },
                        "deps": ["search_flight", "search_hotel"],
                    },
                    {
                        "id": "check_policy",
                        "tool": "check_policy",
                        "args": {"total": "calculate_total", "budget": 8000},
                        "deps": ["calculate_total"],
                    },
                    {
                        "id": "generate_itinerary",
                        "tool": "generate_itinerary",
                        "args": {
                            "origin": "北京",
                            "dest": "东京",
                            "days": 3,
                            "flight": "search_flight",
                            "hotel": "search_hotel",
                            "total": "calculate_total",
                        },
                        "deps": ["check_policy"],
                    },
                ]
            }

        # Fallback plan for any other task.
        return {
            "steps": [
                {
                    "id": "generate_itinerary",
                    "tool": "generate_itinerary",
                    "args": {
                        "origin": "北京",
                        "dest": "东京",
                        "days": 3,
                        "flight": {},
                        "hotel": {},
                        "total": 0,
                    },
                    "deps": [],
                }
            ]
        }

    def replan(
        self,
        plan: Any,
        failed_step: str,
        observation: str,
    ) -> Dict[str, Any]:
        """Return an alternative plan after a step failure.

        Args:
            plan: The current plan object (interface placeholder).
            failed_step: Id of the step that failed.
            observation: Short failure reason, e.g. ``sold_out``.

        Returns:
            A new ``steps`` dictionary that avoids the failing path.
        """
        if failed_step == "search_flight" and observation == "sold_out":
            return {
                "steps": [
                    {
                        "id": "search_flight_alt",
                        "tool": "search_flight",
                        "args": {"origin": "北京", "dest": "东京", "direct": True},
                        "deps": [],
                    },
                    {
                        "id": "search_hotel",
                        "tool": "search_hotel",
                        "args": {"city": "东京", "nights": 3},
                        "deps": [],
                    },
                    {
                        "id": "calculate_total",
                        "tool": "calculate_total",
                        "args": {
                            "flight_price": "search_flight_alt",
                            "hotel_price": "search_hotel",
                        },
                        "deps": ["search_flight_alt", "search_hotel"],
                    },
                    {
                        "id": "check_policy",
                        "tool": "check_policy",
                        "args": {"total": "calculate_total", "budget": 8000},
                        "deps": ["calculate_total"],
                    },
                    {
                        "id": "generate_itinerary",
                        "tool": "generate_itinerary",
                        "args": {
                            "origin": "北京",
                            "dest": "东京",
                            "days": 3,
                            "flight": "search_flight_alt",
                            "hotel": "search_hotel",
                            "total": "calculate_total",
                        },
                        "deps": ["check_policy"],
                    },
                ]
            }

        # Generic fallback: keep only the itinerary generation step.
        return {
            "steps": [
                {
                    "id": "generate_itinerary",
                    "tool": "generate_itinerary",
                    "args": {
                        "origin": "北京",
                        "dest": "东京",
                        "days": 3,
                        "flight": {},
                        "hotel": {},
                        "total": 0,
                    },
                    "deps": [],
                }
            ]
        }
