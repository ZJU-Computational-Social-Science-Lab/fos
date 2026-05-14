"""Minimal facilitator for council experiment phase management."""


class SystemFacilitator:
    """Manages discussion/voting phase transitions for CouncilExperimentScene."""

    def __init__(self, scene):
        self.scene = scene
        self.current_round_num = 1
        self._deliberation_rounds = 3

    def set_deliberation_rounds(self, n: int):
        self._deliberation_rounds = n
