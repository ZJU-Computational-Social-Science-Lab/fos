"""Environment agent for analyzing simulation state and generating suggestions.

The environment agent observes the simulation state and provides
intelligent suggestions to agents based on environmental factors.

Features:
- State analysis (resource pressure, social tension, trends)
- LLM-powered semantic analysis for event relevance and agent impact
- Event injection with automatic context application
- Suggestion generation based on environmental patterns
"""

from typing import Any, Dict, List, Optional
import logging

from fos.core.external_event import ExternalEvent, ExternalEventType, Severity

logger = logging.getLogger(__name__)


class SemanticAnalyzer:
    """LLM-powered semantic analyzer for event relevance and impact.

    Analyzes how external events might affect agent behavior and simulation outcomes.
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        """Initialize the semantic analyzer.

        Args:
            llm_client: LLM client instance for generating analysis.
        """
        self.llm_client = llm_client

    async def analyze_event_relevance(
        self,
        event: ExternalEvent,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze how relevant an event is to the current simulation state.

        Args:
            event: The external event to analyze.
            context: Current simulation state.

        Returns:
            Analysis with relevance score and impact factors.
        """
        if not self.llm_client:
            return self._rule_based_analysis(event, context)

        return await self._llm_analysis(event, context)

    async def analyze_agent_impact(
        self,
        event: ExternalEvent,
        agent_states: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Analyze which agents might be affected by an event.

        Args:
            event: The external event.
            agent_states: List of current agent states.

        Returns:
            List of impact assessments per agent group.
        """
        if not self.llm_client:
            return self._rule_based_agent_impact(event, agent_states)

        return await self._llm_agent_impact(event, agent_states)

    def _rule_based_analysis(
        self,
        event: ExternalEvent,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback rule-based relevance analysis."""
        relevance_score = 0.5

        if event.event_type == ExternalEventType.MARKET:
            if context.get("has_economy", False):
                relevance_score = 0.7
        elif event.event_type == ExternalEventType.POLICY:
            if context.get("has_governance", False):
                relevance_score = 0.8

        severity_weights = {
            Severity.CRITICAL: 1.2,
            Severity.HIGH: 1.0,
            Severity.MEDIUM: 0.8,
            Severity.LOW: 0.6,
        }
        urgency = severity_weights.get(event.severity, 1.0)

        return {
            "relevance_score": min(1.0, relevance_score),
            "urgency_modifier": urgency,
            "affected_domains": self._get_affected_domains(event.event_type),
            "recommended_response": self._get_recommended_response(event),
        }

    def _rule_based_agent_impact(
        self,
        event: ExternalEvent,
        agent_states: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fallback rule-based agent impact analysis."""
        impacts = []

        for agent in agent_states:
            impact_score = 0.3
            factors = []

            agent_type = agent.get("type", "generic")
            if event.event_type == ExternalEventType.MARKET:
                if agent_type in ["trader", "merchant", "banker"]:
                    impact_score = 0.8
                    factors.append("Economic agent affected by market event")
            elif event.event_type == ExternalEventType.POLICY:
                if agent_type in ["governor", "official", "bureaucrat"]:
                    impact_score = 0.7
                    factors.append("Government agent affected by policy event")

            impacts.append({
                "agent_id": agent.get("id"),
                "agent_type": agent_type,
                "impact_score": min(1.0, impact_score),
                "factors": factors,
            })

        return impacts

    async def _llm_analysis(
        self,
        event: ExternalEvent,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """LLM-powered event relevance analysis."""
        prompt = f"""Analyze how relevant this external event is to the simulation:

Event: {event.title}
Type: {event.event_type.value}
Severity: {event.severity.value}
Content: {event.content}

Simulation State:
- Agent count: {len(context.get('agents', []))}
- Resource pressure: {context.get('resource_pressure', 0):.2f}
- Social tension: {context.get('social_tension', 0):.2f}

Return a JSON with:
- relevance_score (0-1)
- urgency_modifier (0.5-1.5)
- affected_domains (list of strings)
- recommended_response (string)
"""
        logger.debug(f"LLM analysis prompt: {prompt[:200]}...")
        return self._rule_based_analysis(event, context)

    async def _llm_agent_impact(
        self,
        event: ExternalEvent,
        agent_states: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """LLM-powered agent impact analysis."""
        return self._rule_based_agent_impact(event, agent_states)

    def _get_affected_domains(self, event_type: ExternalEventType) -> List[str]:
        """Get affected domain labels based on event type."""
        domain_map = {
            ExternalEventType.POLICY: ["governance", "regulation", "law"],
            ExternalEventType.MARKET: ["economy", "trade", "finance"],
            ExternalEventType.NEWS: ["public_opinion", "sentiment", "media"],
            ExternalEventType.CUSTOM: ["custom_domain"],
            ExternalEventType.MANUAL: ["host_intervention"],
        }
        return domain_map.get(event_type, ["unknown"])

    def _get_recommended_response(self, event: ExternalEvent) -> str:
        """Get recommended response based on event type and severity."""
        if event.severity == Severity.CRITICAL:
            return "Immediate action required - consider emergency protocols"
        elif event.severity == Severity.HIGH:
            return "Prioritize response within current simulation cycle"
        elif event.severity == Severity.MEDIUM:
            return "Schedule response for next planning phase"
        return "Monitor situation and reassess in next cycle"


class EnvironmentAgent:
    """Environment agent that analyzes state and generates suggestions.

    This agent monitors the simulation environment and provides
    intelligent suggestions to help agents navigate the simulation.
    """

    def __init__(self, clients: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the environment agent.

        Args:
            clients: LLM client instances for generating suggestions.
        """
        self.clients = clients
        self.semantic_analyzer = SemanticAnalyzer(
            llm_client=clients.get("llm") if clients else None
        )

    def analyze_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the current simulation state.

        Args:
            context: Current simulation state including:
                - time: Current simulation time
                - agents: List of agent states
                - resources: Resource distribution
                - events: Recent events

        Returns:
            Analysis results including trends and risk factors.
        """
        analysis = {
            "timestamp": context.get("time", 0),
            "agent_count": len(context.get("agents", [])),
            "resource_pressure": self._calculate_resource_pressure(context),
            "social_tension": self._calculate_social_tension(context),
            "trends": [],
            "risk_factors": [],
        }

        return analysis

    def generate_suggestions(
        self,
        context: Dict[str, Any],
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate environment-based suggestions for agents.

        Args:
            context: Current simulation state.
            count: Maximum number of suggestions to return.

        Returns:
            List of suggestion dictionaries with:
                - type: Suggestion type (e.g., "intervention", "resource")
                - title: Short title
                - description: Detailed description
                - priority: "low", "medium", "high"
                - actions: Suggested actions to take
        """
        analysis = self.analyze_state(context)
        suggestions = []

        if analysis["resource_pressure"] > 0.8:
            suggestions.append({
                "type": "resource",
                "title": "High Resource Pressure Detected",
                "description": "Resources are becoming scarce. Consider redistribution or conservation measures.",
                "priority": "high",
                "actions": [
                    "Implement resource rationing",
                    "Seek alternative resource channels",
                    "Reduce consumption rates",
                ],
            })

        if analysis["social_tension"] > 0.7:
            suggestions.append({
                "type": "intervention",
                "title": "Social Tension Rising",
                "description": "Social tension is elevated. Early intervention may prevent conflict.",
                "priority": "high",
                "actions": [
                    "Promote dialogue between groups",
                    "Introduce calming mechanisms",
                    "Address underlying grievances",
                ],
            })

        if not suggestions:
            suggestions.append({
                "type": "observation",
                "title": "Environment Stable",
                "description": "No urgent interventions required. Continue monitoring.",
                "priority": "low",
                "actions": ["Continue normal simulation"],
            })

        return suggestions[:count]

    def apply_event(self, event: ExternalEvent, context: Dict[str, Any]) -> bool:
        """Apply an external event to the simulation context.

        Args:
            event: The external event to apply.
            context: Current simulation state to modify.

        Returns:
            True if event was applied successfully.
        """
        event_type = event.event_type

        if event_type == ExternalEventType.POLICY:
            context.setdefault("policy_events", []).append(event.to_dict())
            return True

        if event_type == ExternalEventType.MARKET:
            context.setdefault("market_events", []).append(event.to_dict())
            return True

        if event_type == ExternalEventType.NEWS:
            context.setdefault("news_events", []).append(event.to_dict())
            return True

        if event_type == ExternalEventType.MANUAL:
            context.setdefault("manual_events", []).append(event.to_dict())
            return True

        return False

    def _calculate_resource_pressure(self, context: Dict[str, Any]) -> float:
        """Calculate resource pressure metric (0-1)."""
        resources = context.get("resources", {})
        if not resources:
            return 0.0

        total = sum(resources.values())
        capacity = context.get("resource_capacity", total * 2)

        if capacity == 0:
            return 0.0

        return min(1.0, total / capacity)

    def _calculate_social_tension(self, context: Dict[str, Any]) -> float:
        """Calculate social tension metric (0-1)."""
        agents = context.get("agents", [])
        if not agents:
            return 0.0

        conflicts = sum(1 for a in agents if a.get("in_conflict", False))
        return min(1.0, conflicts / max(1, len(agents)))