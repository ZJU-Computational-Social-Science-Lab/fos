from __future__ import annotations

from fos.core.scene import Scene

from .base import PolicyCascadeBaseMixin
from .distortion import PolicyCascadeDistortionMixin
from .followup import PolicyCascadeFollowUpMixin
from .messages import PolicyCascadeMessageMixin
from .prompts import PolicyCascadePromptMixin
from .runtime import PolicyCascadeRuntimeMixin
from .state import PolicyCascadeStateMixin
from .threads import PolicyCascadeThreadMixin


class PolicyCascadeScene(
    PolicyCascadeRuntimeMixin,
    PolicyCascadePromptMixin,
    PolicyCascadeMessageMixin,
    PolicyCascadeFollowUpMixin,
    PolicyCascadeThreadMixin,
    PolicyCascadeStateMixin,
    PolicyCascadeDistortionMixin,
    PolicyCascadeBaseMixin,
    Scene,
):
    """Strict top→mid→low cascade, single action per tier, downstream-only delivery."""

    TYPE = "policy_cascade_scene"

    @classmethod
    def deserialize(cls, data: dict) -> "PolicyCascadeScene":
        scene = Scene.deserialize(data)
        scene.tier_order = list(scene.state.get("tier_order", []))
        scene._tier_map = {}
        scene._agents_by_tier = {t: [] for t in scene.tier_order}
        return scene
