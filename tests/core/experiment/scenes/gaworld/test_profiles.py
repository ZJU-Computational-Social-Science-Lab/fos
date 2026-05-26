from pathlib import Path

import json

from fos.core.experiment.scenes.gaworld.profiles import (
    GAWorldAgentProfile,
    export_profiles_csv,
    load_profiles,
    profiles_to_fos_agents,
)


def test_profile_can_be_created_with_all_required_fields() -> None:
    profile = GAWorldAgentProfile(
        id="agent-1",
        name="Lin",
        gender="female",
        age=29,
        hukou="urban",
        residence="Hangzhou",
        occupation="designer",
        income="medium",
        education="college",
        personality_traits="kind and careful",
        daily_routine="works and exercises",
        social_network="close friends",
        values="family and growth",
        policy_sensitivity=0.8,
        platform_dependence=0.5,
        risk_preference=0.3,
        voice_propensity=0.7,
        mobility_intent=0.4,
        emotion=0.6,
        stress=0.2,
        econ_security=0.7,
        city_identity=0.9,
    )

    assert profile.name == "Lin"


def test_load_profiles_reads_json_and_returns_profiles() -> None:
    profile_data = [
        {
            "id": "agent-1",
            "name": "Lin",
            "gender": "female",
            "age": 29,
            "hukou": "urban",
            "residence": "Hangzhou",
            "occupation": "designer",
            "income": "medium",
            "education": "college",
            "personality_traits": "kind and careful",
            "daily_routine": "works and exercises",
            "social_network": "close friends",
            "values": "family and growth",
            "policy_sensitivity": 0.8,
            "platform_dependence": 0.5,
            "risk_preference": 0.3,
            "voice_propensity": 0.7,
            "mobility_intent": 0.4,
            "emotion": 0.6,
            "stress": 0.2,
            "econ_security": 0.7,
            "city_identity": 0.9,
        }
    ]
    data_path = Path("tests/core/experiment/scenes/gaworld/profiles.json")
    data_path.write_text(json.dumps(profile_data), encoding="utf-8")

    profiles = load_profiles(data_path)

    assert len(profiles) == 1
    assert isinstance(profiles[0], GAWorldAgentProfile)


def test_load_profiles_returns_empty_list_when_file_does_not_exist() -> None:
    profiles = load_profiles(Path("tests/core/experiment/scenes/gaworld/does_not_exist.json"))

    assert profiles == []


def test_profiles_to_fos_agents_returns_expected_structure() -> None:
    profile = GAWorldAgentProfile(
        id="agent-1",
        name="Lin",
        gender="female",
        age=29,
        hukou="urban",
        residence="Hangzhou",
        occupation="designer",
        income="medium",
        education="college",
        personality_traits="kind and careful",
        daily_routine="works and exercises",
        social_network="close friends",
        values="family and growth",
        policy_sensitivity=0.8,
        platform_dependence=0.5,
        risk_preference=0.3,
        voice_propensity=0.7,
        mobility_intent=0.4,
        emotion=0.6,
        stress=0.2,
        econ_security=0.7,
        city_identity=0.9,
    )

    agents = profiles_to_fos_agents([profile])

    assert len(agents) == 1
    assert agents[0]["name"] == "Lin"
    assert agents[0]["properties"]["occupation"] == "designer"
    assert agents[0]["properties"]["income"] == "medium"
    assert agents[0]["properties"]["policy_sensitivity"] == 0.8
    assert "kind and careful" in agents[0]["role_prompt"]
    assert agents[0]["llm_config"] == {}


def test_export_profiles_csv_writes_name_and_age() -> None:
    profile = GAWorldAgentProfile(
        id="agent-1",
        name="Lin",
        gender="female",
        age=29,
        hukou="urban",
        residence="Hangzhou",
        occupation="designer",
        income="medium",
        education="college",
        personality_traits="kind and careful",
        daily_routine="works and exercises",
        social_network="close friends",
        values="family and growth",
        policy_sensitivity=0.8,
        platform_dependence=0.5,
        risk_preference=0.3,
        voice_propensity=0.7,
        mobility_intent=0.4,
        emotion=0.6,
        stress=0.2,
        econ_security=0.7,
        city_identity=0.9,
    )
    output_path = Path("tests/core/experiment/scenes/gaworld/profiles.csv")

    export_profiles_csv([profile], output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Lin" in content
    assert "29" in content
