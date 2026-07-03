"""Mock tool registry with deterministic, CPU-only tool implementations."""
from __future__ import annotations

from typing import Any, Callable, Dict


class ToolError(Exception):
    """Raised when a tool is missing or invoked incorrectly."""


class ToolRegistry:
    """Registers and executes mock tools for the travel-planning assistant.

    Attributes:
        tools: Mapping from tool name to implementation.
        sold_out: When ``True``, ``search_flight`` returns a sold-out result.
            This lets the demo exercise the replanning path.
    """

    def __init__(self) -> None:
        self.tools: Dict[str, Callable[..., Any]] = {}
        self.sold_out = False
        self._register_defaults()

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Add a new tool to the registry."""
        self.tools[name] = fn

    def execute(self, name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool by name with the supplied keyword arguments."""
        if name not in self.tools:
            raise ToolError(f"Tool '{name}' is not registered")
        return self.tools[name](**args)

    def _register_defaults(self) -> None:
        """Register the built-in travel-planning tools."""

        def search_flight(
            origin: str,
            dest: str,
            date: str | None = None,
            direct: bool = False,
        ) -> Dict[str, Any]:
            """Return a deterministic flight result.

            When ``self.sold_out`` is ``True`` and ``direct`` is ``False``,
            the outbound flight is reported as sold out so the executor can
            trigger a replan.
            """
            if self.sold_out and not direct:
                return {
                    "status": "sold_out",
                    "message": f"航班 {origin}->{dest} 已售罄",
                }
            return {
                "flight": f"{origin}->{dest}{'直达' if direct else '中转'}航班",
                "price": 3500,
                "date": date,
            }

        def search_hotel(city: str, nights: int) -> Dict[str, Any]:
            """Return a deterministic hotel result."""
            return {
                "hotel": f"{city}商务酒店",
                "price": 500 * nights,
            }

        def calculate_total(
            flight_price: Any,
            hotel_price: Any,
        ) -> Dict[str, Any]:
            """Sum the flight and hotel prices.

            Accepts either numeric values or result dictionaries containing a
            ``price`` key.
            """
            flight = (
                flight_price
                if isinstance(flight_price, (int, float))
                else flight_price["price"]
            )
            hotel = (
                hotel_price
                if isinstance(hotel_price, (int, float))
                else hotel_price["price"]
            )
            return {"total": flight + hotel}

        def check_policy(total: Any, budget: float) -> Dict[str, Any]:
            """Check whether the total cost respects the budget ceiling."""
            value = total if isinstance(total, (int, float)) else total["total"]
            approved = value <= budget
            return {
                "approved": approved,
                "budget": budget,
                "total": value,
                "message": "预算内" if approved else "超出预算",
            }

        def generate_itinerary(
            origin: str,
            dest: str,
            days: int,
            flight: Any,
            hotel: Any,
            total: Any,
        ) -> str:
            """Produce a short human-readable itinerary."""
            total_value = total if isinstance(total, (int, float)) else total["total"]
            flight_name = flight.get("flight", "未知航班") if isinstance(flight, dict) else str(flight)
            hotel_name = hotel.get("hotel", "未知酒店") if isinstance(hotel, dict) else str(hotel)
            return (
                f"{origin}>{dest} {days}天行程："
                f"入住{hotel_name}，"
                f"乘坐{flight_name}，"
                f"总花费{total_value}元。"
            )

        self.register("search_flight", search_flight)
        self.register("search_hotel", search_hotel)
        self.register("calculate_total", calculate_total)
        self.register("check_policy", check_policy)
        self.register("generate_itinerary", generate_itinerary)
