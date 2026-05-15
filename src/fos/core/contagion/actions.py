"""
Contagion scene action definitions for Pipeline A.

Provides minimal action stubs for ContagionScene: MoveAdjacentAction lets
an agent move to an adjacent cell; SpeakToAction directs speech at a nearby
agent and triggers a transmission check via ContagionScene.check_action_transmission.

Contains: MoveAdjacentAction, SpeakToAction
"""


class MoveAdjacentAction:
    """Move to an adjacent cell on the grid."""

    name = "move"
    description = "Move to an adjacent position on the map."

    def get_description(self, agent=None) -> str:
        return self.description


class SpeakToAction:
    """Direct speech at a nearby agent, potentially triggering contagion transmission."""

    name = "speak"
    description = "Speak to a nearby agent."

    def get_description(self, agent=None) -> str:
        return self.description
