from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta
from litestar import Router, get, post
from litestar.connection import Request
from litestar.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from fos.i18n import T
from fos.backend.core.database import get_session
from fos.backend.dependencies import extract_bearer_token, resolve_current_user
from fos.backend.services.environment_suggestion_service import (
    get_simulation_state,
    generate_environment_suggestions,
    broadcast_environment_event,
    dismiss_suggestions,
)
from fos.core.event_queue import EventQueue
from fos.core.external_event import ExternalEvent, EventFilter, ExternalEventType, Severity

logger = logging.getLogger(__name__)


def _parse_node_id_param(request: Request) -> int | None:
    node_id_param = request.query_params.get("node_id")
    if node_id_param is None:
        return None
    try:
        return int(node_id_param)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=T("api.errors.invalid_node_id_param"))


@get("/simulations/{simulation_id:str}/suggestions/status")
async def get_suggestion_status(
    simulation_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Check if environment suggestions are available for the current turn."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)
        node_id = _parse_node_id_param(request)
        state = await get_simulation_state(simulation_id, session, current_user.id, node_id)

        if not state:
            return {"available": False, "turn": None, "enabled": False}

        config = state["config"]
        if not config.get("enabled"):
            return {"available": False, "turn": None, "enabled": False}

        turns = state["turns"]
        interval = config.get("turn_interval", 5)
        current_interval_milestone = (turns // interval) * interval
        viewed_intervals = state.get("_suggestions_viewed_intervals", set())

        available = (
            turns > 0
            and turns >= interval
            and current_interval_milestone not in viewed_intervals
        )

        return {"available": available, "turn": turns if available else None, "enabled": True}


@post("/simulations/{simulation_id:str}/suggestions/generate")
async def generate_suggestions(
    simulation_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Generate environment event suggestions based on current simulation context."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)
        node_id = _parse_node_id_param(request)
        suggestions = await generate_environment_suggestions(simulation_id, session, current_user.id, node_id)

        # Ensure suggestions are JSON-serializable (convert to list of dicts with str values)
        cleaned_suggestions = [
            {
                "event_type": str(s.get("event_type", "")),
                "description": str(s.get("description", "")),
                "severity": str(s.get("severity", "mild")),
            }
            for s in suggestions
        ]
        return {"suggestions": cleaned_suggestions}


@post("/simulations/{simulation_id:str}/events/environment")
async def apply_environment_event(
    simulation_id: str,
    data: Dict[str, Any],
    request: Request,
) -> Dict[str, Any]:
    """Apply an environment event to the simulation."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)
        try:
            await broadcast_environment_event(
                simulation_id,
                data,
                session,
                current_user.id,
            )
            return {"success": True, "message": T('api.environment.event_broadcast')}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@post("/simulations/{simulation_id:str}/suggestions/dismiss")
async def dismiss_suggestions_endpoint(
    simulation_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Dismiss environment suggestions for the current interval."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)
        try:
            await dismiss_suggestions(simulation_id, session, current_user.id)
            return {"success": True, "message": T('api.environment.suggestions_dismissed')}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


# In-memory rules store for MVP (persists until server restart)
_rules_store: list[Any] = []

@get("/rules")
async def get_rules(request: Request) -> Dict[str, Any]:
    """Get all configured rules."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)
    return {"rules": _rules_store}

@post("/rules")
async def save_rules(
    data: Dict[str, Any],
    request: Request,
) -> Dict[str, Any]:
    """Save/replace all rules."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)
    global _rules_store
    _rules_store = data.get("rules", [])
    return {"saved": len(_rules_store)}


# Per-simulation event queues to avoid leaking events across simulations
_simulation_event_queues: dict[str, EventQueue] = {}

# Default queue for non-simulation contexts
_default_event_queue: EventQueue | None = None


def _get_default_queue() -> EventQueue:
    global _default_event_queue
    if _default_event_queue is None:
        _default_event_queue = EventQueue(max_size=1000, dedup_window_hours=24)
    return _default_event_queue


def _get_simulation_queue(simulation_id: str) -> EventQueue:
    """Get or create an event queue for a specific simulation."""
    if simulation_id not in _simulation_event_queues:
        _simulation_event_queues[simulation_id] = EventQueue(max_size=1000, dedup_window_hours=24)
    return _simulation_event_queues[simulation_id]


@get("/events/external")
async def get_external_events(
    request: Request,
    simulation_id: str | None = None,
    type: str | None = None,
    min_severity: str | None = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Get external events for a simulation.

    Args:
        simulation_id: Optional simulation ID to scope events (required for isolation)
        type: Optional event type filter (policy, market, news, custom, manual)
        min_severity: Optional minimum severity filter (low, medium, high, critical)
        limit: Maximum number of events to return (default 50)
    """
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)

        # Use simulation_id if provided, otherwise require simulation context
        queue = _get_simulation_queue(simulation_id) if simulation_id else EventQueue(max_size=100, dedup_window_hours=1)

        # Build filter if parameters provided
        event_filter = None
        if type or min_severity:
            type_map = {
                "policy": ExternalEventType.POLICY,
                "market": ExternalEventType.MARKET,
                "news": ExternalEventType.NEWS,
                "custom": ExternalEventType.CUSTOM,
                "manual": ExternalEventType.MANUAL,
            }
            type_filter = [type_map[t]] if type and type in type_map else None
            min_sev = min_severity if min_severity and min_severity in ("low", "medium", "high", "critical") else None

            if type_filter or min_sev:
                severity_enum = Severity[min_sev.upper()] if min_sev else None
                event_filter = EventFilter(
                    types=type_filter,
                    min_severity=severity_enum,
                )

        if event_filter:
            events = queue.get_by_filter(event_filter)
        else:
            events = queue.get_pending(limit=limit)

        return {
            "events": [e.to_dict() for e in events],
            "total": len(events),
        }


@post("/events/external")
async def add_external_event(
    data: Dict[str, Any],
    request: Request,
    simulation_id: str | None = None,
) -> Dict[str, Any]:
    """Add an external event to a simulation's event queue.

    This endpoint allows manual injection of events or forwarding
    from external sources.
    """
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)

        queue = _get_simulation_queue(simulation_id) if simulation_id else None

        try:
            event = ExternalEvent.from_dict(data)
            if queue:
                success = queue.enqueue(event)
            else:
                success = False
            return {
                "success": success,
                "event_id": event.id,
                "message": "Event added" if success else "No simulation context - event not stored",
            }
        except (KeyError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid event data: {e}")


@post("/events/seed")
async def seed_demo_events(
    request: Request,
    simulation_id: str | None = None,
) -> Dict[str, Any]:
    """Seed demo events for testing the event panel UI."""
    token = extract_bearer_token(request)
    async with get_session() as session:
        current_user = await resolve_current_user(session, token)

    queue = _get_simulation_queue(simulation_id) if simulation_id else _get_default_queue()

    demo_events = [
        ExternalEvent.create(
            event_type=ExternalEventType.MARKET,
            source=EventSource.YAHOO_FINANCE,
            title="股市大幅波动",
            content="上证指数单日下跌 3.2%，市场恐慌情绪蔓延",
            severity=Severity.HIGH,
            metadata={"index": "000001.SS", "change_pct": -3.2},
        ),
        ExternalEvent.create(
            event_type=ExternalEventType.POLICY,
            source=EventSource.NATIONAL_BUREAU,
            title="政府发布新能源汽车补贴政策",
            content="财政部宣布延续新能源汽车购置税减免政策至 2027 年",
            severity=Severity.MEDIUM,
            metadata={"region": "全国", "category": "industrial"},
        ),
        ExternalEvent.create(
            event_type=ExternalEventType.NEWS,
            source=EventSource.NEWS_API,
            title="社交媒体舆论风暴",
            content="某企业家微博发言引发广泛讨论，相关话题阅读量突破 5 亿",
            severity=Severity.HIGH,
            metadata={"platform": "微博", "views": 500000000},
        ),
        ExternalEvent.create(
            event_type=ExternalEventType.MARKET,
            source=EventSource.YAHOO_FINANCE,
            title="银行利率上调",
            content="央行宣布一年期存贷款利率上调 25 个基点",
            severity=Severity.MEDIUM,
            metadata={"rate_change_bp": 25},
        ),
        ExternalEvent.create(
            event_type=ExternalEventType.MANUAL,
            source=EventSource.MANUAL,
            title="突发自然灾害",
            content="某地区发生 5.1 级地震，暂无人员伤亡报告",
            severity=Severity.CRITICAL,
            metadata={"magnitude": 5.1, "region": "某地区"},
        ),
    ]

    added = 0
    for event in demo_events:
        if queue.enqueue(event):
            added += 1

    return {"added": added, "total": queue.size()}


def get_external_event_queue(simulation_id: str | None = None) -> EventQueue:
    """Get the event queue for a simulation, or a default queue if none specified."""
    if simulation_id:
        return _get_simulation_queue(simulation_id)
    # Return a module-level default queue for backward compatibility
    return _external_event_queue


# Backward compatibility - module-level default queue
_external_event_queue: EventQueue = EventQueue(max_size=1000, dedup_window_hours=24)


router = Router(
    path="",
    route_handlers=[
        get_suggestion_status,
        generate_suggestions,
        apply_environment_event,
        dismiss_suggestions_endpoint,
        get_rules,
        save_rules,
        get_external_events,
        add_external_event,
        seed_demo_events,
    ],
)
