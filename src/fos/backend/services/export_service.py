"""
Export service for simulation data.

Handles transformation of simulation events into clean CSV/JSON export format
with scenario parameters and simplified log types.
"""
import csv
import io
import json
from datetime import datetime


def generate_export_filename(scenario_id: str, format: str) -> str:
    """Generate export filename with scenario ID and timestamp.

    Args:
        scenario_id: Scenario identifier (e.g., "public_goods")
        format: Export format ("csv" or "json")

    Returns:
        Filename like "Scenario_public_goods_2026_03_30_1430.csv"
    """
    now = datetime.now()
    date_str = now.strftime("%Y_%m_%d")
    time_str = now.strftime("%H_%M")
    return f"Scenario_{scenario_id}_{date_str}_{time_str}.{format}"


def simplify_log_type(event_type: str) -> str:
    """Simplify log types to AGENT_ACTION or SYSTEM.

    Args:
        event_type: Original event type from logs

    Returns:
        Simplified type: "AGENT_ACTION" or "SYSTEM"
    """
    # Agent-related action types
    if event_type in ("AGENT_SAY", "AGENT_ACTION", "experiment_action", "agent_action"):
        return "AGENT_ACTION"
    return "SYSTEM"


def extract_action_and_follow_up(event: dict) -> tuple[str, str]:
    """Extract action name and follow-up value from event.

    Args:
        event: Event dictionary with action data

    Returns:
        Tuple of (action_name, follow_up_value)
        follow_up_value is semicolon-separated for multiple params
    """
    data = event.get("data", {})

    # Handle multiple formats:
    # 1. Nested action: data = {"action": {"name": "allocate", "parameters": {...}}}
    # 2. Direct action: data = {"action": "allocate", "parameters": {...}}
    # 3. Direct fields: data = {"agent": "Agent 1", "action": "allocate", ...}
    action_field = data.get("action")

    if isinstance(action_field, dict):
        # Nested action format
        action_name = action_field.get("name", "")
        parameters = action_field.get("parameters", {})
    elif isinstance(action_field, str):
        # Direct action string
        action_name = action_field
        parameters = data.get("parameters", {})
    else:
        action_name = ""
        parameters = {}

    if not parameters:
        return (action_name, "")

    # Extract parameter values, semicolon-separated
    values = [str(v) for v in parameters.values()]
    follow_up = "; ".join(values)

    return (action_name, follow_up)


def transform_event_for_export(event: dict, scenario_params: dict) -> dict:
    """Transform a log event into export format with scenario params.

    Args:
        event: Log event dictionary
        scenario_params: Scenario parameters to include in export

    Returns:
        Dictionary with export columns
    """
    payload = event.get("payload", {})

    # Extract basic fields
    # Normalize agent_id to lowercase with underscores (e.g., "Agent 1" -> "agent_1")
    # This ensures consistent merging with agent demographic data
    raw_agent_id = payload.get("agent", "")
    normalized_agent_id = raw_agent_id.lower().replace(" ", "_") if raw_agent_id else ""

    result = {
        "sequence": event.get("sequence"),
        "timestamp": event.get("created_at").isoformat() if hasattr(event.get("created_at"), "isoformat") else (str(event.get("created_at")) if event.get("created_at") is not None else ""),
        "node_id": str(event.get("tree_node_id", "")),
        "round": payload.get("round", event.get("round", "")),
        "agent_id": normalized_agent_id,
        "type": simplify_log_type(event.get("event_type", "SYSTEM")),
    }

    # extract_action_and_follow_up expects {"data": <action-containing-dict>}
    # payload is the event's payload, which contains the "action" key at top level
    action, follow_up = extract_action_and_follow_up({"data": payload})
    result["action"] = action
    result["follow_up"] = follow_up

    # Add scenario parameters (prefer per-node params if attached)
    params = event.get("_node_scenario_params") or scenario_params
    result.update(params)

    # Pass through agent metadata fields from payload (added by headless_council.py)
    _agent_meta_fields = (
        "model", "archetype_id", "archetype_label",
        "Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism",
        "degree", "network_label",
    )
    for field in _agent_meta_fields:
        if field in payload:
            result[field] = payload[field]

    return result


def build_results_metrics(transformed_events: list[dict]) -> dict:
    """Build reproducible result metrics from transformed export rows."""
    agent_event_counts: dict[str, int] = {}
    round_event_counts: dict[str, int] = {}
    metric_points: dict[str, dict[str, dict[str, float]]] = {}

    for event in transformed_events:
        agent_id = str(event.get("agent_id") or "")
        round_id = str(event.get("round") or "")

        if agent_id:
            agent_event_counts[agent_id] = agent_event_counts.get(agent_id, 0) + 1
        if round_id:
            round_event_counts[round_id] = round_event_counts.get(round_id, 0) + 1

        payload = event.get("_raw_payload") or {}
        outcome = payload.get("outcome") if isinstance(payload, dict) else None
        if not isinstance(outcome, dict) or not agent_id or not round_id:
            continue

        for metric_name, value in outcome.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            metric_points.setdefault(str(metric_name), {}).setdefault(agent_id, {})[round_id] = float(value)

    trajectories = []
    for metric_name in sorted(metric_points):
        agents = []
        for agent_id in sorted(metric_points[metric_name]):
            round_values = metric_points[metric_name][agent_id]
            values = [
                {"round": round_id, "value": round_values[round_id]}
                for round_id in sorted(round_values, key=_round_sort_key)
            ]
            agents.append({"agent_id": agent_id, "values": values})
        trajectories.append({"metric": metric_name, "agents": agents})

    return {
        "agent_event_counts": [
            {"agent_id": agent_id, "count": count}
            for agent_id, count in sorted(agent_event_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "round_event_counts": [
            {"round": round_id, "count": count}
            for round_id, count in sorted(round_event_counts.items(), key=lambda item: _round_sort_key(item[0]))
        ],
        "trajectories": trajectories,
    }


def _round_sort_key(value: str) -> tuple[int, str]:
    try:
        return (0, f"{int(value):020d}")
    except Exception:
        return (1, value)


def deduplicate_events(events: list[dict]) -> list[dict]:
    """Deduplicate events that appear in multiple tree nodes due to log inheritance.

    When child nodes are created, they inherit all parent logs. This causes
    the same event to appear in multiple nodes. We deduplicate using the
    original event identity, not semantic content, so branch-specific actions
    that happen to look the same are still exported.

    Args:
        events: List of raw export events before transformation

    Returns:
        Deduplicated list of events, keeping the first occurrence
    """
    seen = set()
    deduplicated = []

    for event in events:
        # Inherited logs keep the original originating node_id/timestamp/payload.
        # Distinct branch events may have identical semantic content, so we must
        # include the originating node and payload in the identity key.
        key = (
            event.get("event_type"),
            event.get("created_at"),
            json.dumps(event.get("payload", {}), sort_keys=True, default=str),
        )

        if key not in seen:
            seen.add(key)
            deduplicated.append(event)

    return deduplicated


def export_events(events: list[dict], scenario_params: dict, format: str, include_metrics: bool = False) -> str:
    """Export events to CSV or JSON format.

    Args:
        events: List of log events
        scenario_params: Scenario parameters to include
        format: "csv" or "json"

    Returns:
        Formatted export content
    """
    deduplicated_events = deduplicate_events(events)
    transformed = []
    for event in deduplicated_events:
        row = transform_event_for_export(event, scenario_params)
        if include_metrics:
            row["_raw_payload"] = event.get("payload", {})
        transformed.append(row)

    metrics = build_results_metrics(transformed) if include_metrics else None
    if include_metrics:
        for row in transformed:
            row.pop("_raw_payload", None)

    if include_metrics:
        agent_counts = {
            item["agent_id"]: item["count"]
            for item in (metrics or {}).get("agent_event_counts", [])
        }
        round_counts = {
            str(item["round"]): item["count"]
            for item in (metrics or {}).get("round_event_counts", [])
        }
        for row in transformed:
            row["agent_event_count"] = agent_counts.get(str(row.get("agent_id") or ""), 0)
            row["round_event_count"] = round_counts.get(str(row.get("round") or ""), 0)

    if format == "json":
        if include_metrics:
            return json.dumps({"events": transformed, "metrics": metrics}, indent=2, default=str)
        return json.dumps(transformed, indent=2, default=str)

    # CSV format
    if not transformed:
        # Return header row only, using scenario params as column reference
        output = io.StringIO()
        base_cols = ["timestamp", "node_id", "round", "agent_id", "type", "action", "follow_up"]
        metric_cols = ["agent_event_count", "round_event_count"] if include_metrics else []
        fieldnames = base_cols + list(scenario_params.keys()) + metric_cols
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        return output.getvalue()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=transformed[0].keys())
    writer.writeheader()
    writer.writerows(transformed)

    return output.getvalue()
