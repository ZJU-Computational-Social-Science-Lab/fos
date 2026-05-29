"""This file checks the public GAWorld scenario parameter contract.

- test_gaworld_scenario_exposes_execution_profile_parameter checks the
  scenario schema includes a user-facing execution profile control.
"""

from __future__ import annotations

from fos.core.scenarios.registry import get_scenario


def test_gaworld_scenario_exposes_execution_profile_parameter() -> None:
    scenario = get_scenario("gaworld")

    assert scenario is not None
    parameters = {item["key"]: item for item in scenario["parameters"]}
    assert "execution_profile" in parameters
    assert parameters["execution_profile"]["type"] == "string"
    assert parameters["execution_profile"]["ui_hint"] == "select"
    assert parameters["execution_profile"]["default"] == "fast"
    assert parameters["execution_profile"]["options"] == [
        "fast",
        "balanced",
        "full_fidelity",
    ]
