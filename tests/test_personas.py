# Contract tests for `fos.experiments.personas`, the persona generation kit
# of the Gui & Toubia (2025) unblinding study (Web Appendix D). Design
# (task 1459): each persona is generated ONCE at max depth — one joint
# completion fills the 11 demographic fields plus all 5 behavioral measures —
# and the depth axis only truncates RENDERING of that same persona dict. The
# tests for the bundled census file data/configs/census_marginals_us_approx.json
# skip (pytest.skip) while that file is missing, so they stay independent of
# the module state.
#
# Coverage per spec item (see the test classes below for the details):
#   1. PERSONA_FIELDS — 11 paper fields in order.
#   2. build_persona_elicitation_prompt() — Prompt-10: category+product,
#      every field with a blank placeholder — all 11 demographics and all 5
#      behavioral measures — plus the price blank as the literal
#      "[a number with up to 2 decimal points]", fields in order, one joint
#      completion.
#   3. parse_persona(raw) — the 11 keys, int casts, $/comma stripping,
#      wrapper/preamble tolerance, None when a field is missing.
#   4. generate_personas(...) — exactly n chat_fn calls, (personas, skipped),
#      deterministic per seed.
#   5. render_demographics_block(persona) — 11 "Field: value" lines in order.
#   6. BEHAVIORAL_MEASURES — five measures (risk_aversion and loss_aversion
#      joined the original three) — plus render_extended_block(persona): the
#      demographics block followed by "name: score (P<n> percentile)" and a
#      <note: ...> per present measure; missing measures skipped silently.
#   6b. render_persona_fields(persona, depth) — the depth-truncation renderer:
#      the SAME fully populated persona dict rendered at each of the five
#      depth tiers ("none", "demographics", "tightwad", "time_preference",
#      "risk_preference") shows exactly that tier's field set, the rendered
#      field sets nest strictly, and partial persona dicts render without
#      KeyError (the TASK-1456 behavior).
#   7. check_persona_diversity(personas) — the five diversity stats.
#   8. check_persona_coherence(personas) — violations/rates/examples over the
#      five paper rules (names pinned below).
#   9. compare_to_census(...) + load_census_marginals(path=None).
#  10. scripts/generate_personas.py — main(argv=None), __main__ guard, the
#      eight flags with defaults, socket-free import, --help exits 0.
#
# API assumptions pinned by this file (documented for the implement agent):
#   * Coherence "rates" keys: age_range, children_capacity,
#     income_nonnegative, retirement_age, household_size_min.
#   * "n_violations" counts events (a persona breaking two rules counts
#     twice); "examples" lists each violating persona dict once.
#   * "distinct_ratio" is (unique - 1) / (n - 1).
#   * compare_to_census "gap" is sample mean - census mean (numeric) or the
#     total-variation distance 0.5 * sum(|sample - census|) (shares);
#     "sample" is the sample mean or sample share dict.
#   * The CLI script exposes _parse_args(argv=None) -> argparse.Namespace
#     (same seam test_persona_depth.py pins on unblinding_sweep.py).


import importlib.util
import inspect
import re
import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_personas.py"
CENSUS_PATH = REPO_ROOT / "data" / "configs" / "census_marginals_us_approx.json"

EXPECTED_FIELDS = [
    "age",
    "gender",
    "education",
    "household_income",
    "occupation",
    "ethnicity",
    "marital_status",
    "household_size",
    "number_of_children",
    "state",
    "home_ownership",
]

# The five behavioral measures (risk_aversion and loss_aversion joined the
# original three in the five-tier depth design).
EXPECTED_MEASURES = [
    "tightwad_spendthrift",
    "discount_rate",
    "present_bias",
    "risk_aversion",
    "loss_aversion",
]

# The five persona depth tiers, shallowest first. Each tier's rendered field
# set adds the tier's own fields on top of the tier below it.
DEPTHS = ["none", "demographics", "tightwad", "time_preference", "risk_preference"]

# The field names render_persona_fields must show per depth for a persona
# that carries every field (11 demographics + 5 measures). The tiers are
# strictly nested: demographics adds the 11 canonical fields to "none",
# tightwad adds tightwad_spendthrift, time_preference adds discount_rate and
# present_bias, risk_preference adds risk_aversion and loss_aversion.
DEPTH_FIELD_SETS = {
    "none": set(),
    "demographics": set(EXPECTED_FIELDS),
    "tightwad": set(EXPECTED_FIELDS) | {"tightwad_spendthrift"},
    "time_preference": set(EXPECTED_FIELDS)
    | {"tightwad_spendthrift", "discount_rate", "present_bias"},
    "risk_preference": set(EXPECTED_FIELDS) | set(EXPECTED_MEASURES),
}

# One canned, fully-formed eleven-field answer the fake chat returns.
_CANNED_RAW = "\n".join(
    [
        "age: 35",
        "gender: female",
        "education: college",
        "household_income: $86,500",
        "occupation: teacher",
        "ethnicity: white",
        "marital_status: married",
        "household_size: 4",
        "number_of_children: 2",
        "state: CA",
        "home_ownership: own",
    ]
)

# The dict parse_persona(_CANNED_RAW) must produce.
_CANNED_PERSONA = {
    "age": 35,
    "gender": "female",
    "education": "college",
    "household_income": 86500,
    "occupation": "teacher",
    "ethnicity": "white",
    "marital_status": "married",
    "household_size": 4,
    "number_of_children": 2,
    "state": "CA",
    "home_ownership": "own",
}


def _personas_module():
    """Return the fos.experiments.personas module (imported per test).

    The module does not exist yet, so a top-level import would kill the whole
    file at collection time. Importing it per test lets each test fail on its
    own with the same ModuleNotFoundError and keeps the census skip tests
    independent of the module import.
    """
    from fos.experiments import personas  # noqa: PLC0415

    return personas


def _persona(**overrides):
    """One valid eleven-field persona dict; overrides win per key."""
    base = {
        "age": 35,
        "gender": "female",
        "education": "college",
        "household_income": 86500,
        "occupation": "teacher",
        "ethnicity": "white",
        "marital_status": "married",
        "household_size": 4,
        "number_of_children": 2,
        "state": "CA",
        "home_ownership": "own",
    }
    base.update(overrides)
    return base


def _full_persona(**overrides):
    """A fully populated persona: 11 demographics plus all five measures.

    This is the max-depth (risk_preference) persona the generator is supposed
    to produce; the depth-truncation tests slice it at every tier.
    """
    persona = _persona(
        age=60,
        occupation="retired professor",
        household_income=42000,
        household_size=2,
        number_of_children=0,
    )
    persona.update(
        {
            "tightwad_spendthrift": {"score": 42, "percentile": 18},
            "discount_rate": {"score": 6.2, "percentile": 71},
            "present_bias": {"score": 33, "percentile": 9},
            "risk_aversion": {"score": 7.5, "percentile": 88},
            "loss_aversion": {"score": 4.0, "percentile": 62},
        }
    )
    persona.update(overrides)
    return persona


class _FakeChat:
    """Injected chat function: records every call, never touches a network.

    Answers are drawn from a list that cycles, so a run is fully reproducible
    for the same call sequence. Each call is stored as (messages, temperature)
    so tests can inspect what was sent.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, messages, temperature):
        self.calls.append((messages, temperature))
        return self.answers[len(self.calls) % len(self.answers)]


# 1. PERSONA_FIELDS


class TestPersonaFields:
    def test_persona_fields_lists_all_eleven_paper_fields_in_order(self):
        assert _personas_module().PERSONA_FIELDS == EXPECTED_FIELDS

    def test_persona_fields_holds_unique_strings(self):
        fields = _personas_module().PERSONA_FIELDS
        assert len(fields) == len(set(fields))
        assert all(isinstance(field, str) for field in fields)


# 2. build_persona_elicitation_prompt()


class TestBuildPersonaElicitationPrompt:
    def test_prompt_names_the_category_and_the_product(self):
        prompt = _personas_module().build_persona_elicitation_prompt(
            "Soft Drinks - Carbonated", "Coca-Cola Soda Pop, 12 fl oz"
        )
        assert "Soft Drinks - Carbonated" in prompt
        assert "Coca-Cola Soda Pop, 12 fl oz" in prompt

    def test_prompt_mentions_every_one_of_the_sixteen_fields(self):
        # Max-depth generation: the 11 demographics AND all 5 measures appear.
        all_fields = [
            *_personas_module().PERSONA_FIELDS,
            *_personas_module().BEHAVIORAL_MEASURES,
        ]
        prompt = (
            _personas_module()
            .build_persona_elicitation_prompt("Snacks", "Lay's Classic Potato Chips")
            .lower()
        )
        for field in all_fields:
            assert field in prompt, f"field {field!r} missing from the prompt"

    def test_prompt_leaves_the_price_blank_with_the_paper_literal(self):
        prompt = _personas_module().build_persona_elicitation_prompt("Snacks", "Chips")
        assert "[a number with up to 2 decimal points]" in prompt

    def test_every_demographic_and_behavioral_field_sits_next_to_a_blank(self):
        all_fields = [
            *_personas_module().PERSONA_FIELDS,
            *_personas_module().BEHAVIORAL_MEASURES,
        ]
        prompt = (
            _personas_module()
            .build_persona_elicitation_prompt("Snacks", "Chips")
            .lower()
        )
        for field in all_fields:
            hits = [m.start() for m in re.finditer(re.escape(field), prompt)]
            assert hits, f"field {field!r} missing from the prompt"
            window = 25
            assert any(
                "[" in prompt[max(0, hit - window) : hit + window] for hit in hits
            ), f"field {field!r} has no blank placeholder near it"

    def test_fields_are_named_in_persona_fields_order(self):
        prompt = (
            _personas_module()
            .build_persona_elicitation_prompt("Snacks", "Chips")
            .lower()
        )
        positions = []
        for field in _personas_module().PERSONA_FIELDS:
            match = re.search(rf"(?<![a-z0-9_]){re.escape(field)}(?![a-z0-9_])", prompt)
            assert match, f"field {field!r} not named in the prompt"
            positions.append(match.start())
        assert positions == sorted(positions)
        # The demographics all come before the first behavioral measure.
        measure_positions = []
        for field in _personas_module().BEHAVIORAL_MEASURES:
            match = re.search(
                rf"(?<![a-z0-9_]){re.escape(field)}(?![a-z0-9_])", prompt
            )
            assert match, f"measure {field!r} not named in the prompt"
            measure_positions.append(match.start())
        assert positions[-1] < min(measure_positions)

    def test_prompt_asks_for_the_fields_in_one_joint_completion(self):
        prompt = (
            _personas_module()
            .build_persona_elicitation_prompt("Snacks", "Chips")
            .lower()
        )
        joint_phrases = (
            "one completion",
            "single completion",
            "one message",
            "one response",
            "all at once",
            "all together",
            "jointly",
            "in a single",
        )
        assert any(phrase in prompt for phrase in joint_phrases), (
            "prompt must say all fields are completed together in one completion"
        )
        assert any(word in prompt for word in ("fill", "complete", "blank"))


# 3. parse_persona()


class TestParsePersona:
    def test_parse_persona_reads_a_canned_eleven_field_answer(self):
        parsed = _personas_module().parse_persona(_CANNED_RAW)
        assert parsed == _CANNED_PERSONA

    def test_parse_persona_returns_exactly_the_eleven_persona_keys(self):
        parsed = _personas_module().parse_persona(_CANNED_RAW)
        assert set(parsed) == set(_personas_module().PERSONA_FIELDS)

    def test_parse_persona_int_casts_the_numeric_fields(self):
        parsed = _personas_module().parse_persona(_CANNED_RAW)
        assert parsed["age"] == 35 and isinstance(parsed["age"], int)
        assert parsed["household_size"] == 4 and isinstance(
            parsed["household_size"], int
        )
        assert parsed["number_of_children"] == 2 and isinstance(
            parsed["number_of_children"], int
        )
        assert parsed["household_income"] == 86500 and isinstance(
            parsed["household_income"], int
        )

    def test_parse_persona_keeps_the_text_fields_as_strings(self):
        parsed = _personas_module().parse_persona(_CANNED_RAW)
        for field in (
            "gender",
            "education",
            "occupation",
            "ethnicity",
            "marital_status",
            "state",
            "home_ownership",
        ):
            assert isinstance(parsed[field], str), field

    def test_parse_persona_strips_dollar_signs_and_commas_from_income(self):
        raw = _CANNED_RAW.replace("$86,500", "$45,000")
        parsed = _personas_module().parse_persona(raw)
        assert parsed["household_income"] == 45000

    def test_parse_persona_tolerates_a_reasoning_channel_wrapper(self):
        raw = "<|channel>the respondent is a teacher\n<channel|>" + _CANNED_RAW
        parsed = _personas_module().parse_persona(raw)
        assert parsed == _CANNED_PERSONA

    def test_parse_persona_tolerates_special_token_tails(self):
        raw = _CANNED_RAW + "\n<|im_end|>\n<|im_start|>system\nYou are a"
        parsed = _personas_module().parse_persona(raw)
        assert parsed == _CANNED_PERSONA

    def test_parse_persona_ignores_preamble_lines_before_the_answer(self):
        raw = "Here is the completed persona profile.\n" + _CANNED_RAW
        parsed = _personas_module().parse_persona(raw)
        assert parsed == _CANNED_PERSONA

    def test_parse_persona_returns_none_when_any_field_is_missing(self):
        missing = _CANNED_RAW.replace("state: CA\n", "")
        assert _personas_module().parse_persona(missing) is None
        assert _personas_module().parse_persona("not a persona at all") is None
        assert _personas_module().parse_persona("") is None


# 4. generate_personas()


class TestGeneratePersonas:
    def test_generate_personas_signature_matches_the_contract(self):
        params = inspect.signature(_personas_module().generate_personas).parameters
        assert list(params)[:4] == ["category", "product", "n", "chat_fn"]
        assert params["temperature"].default == 1.0
        assert params["seed"].default is None

    def test_generate_personas_calls_chat_exactly_n_times(self):
        chat = _FakeChat([_CANNED_RAW] * 3)
        personas, skipped = _personas_module().generate_personas(
            "Snacks", "Chips", 3, chat
        )
        assert len(chat.calls) == 3
        assert skipped == 0
        assert personas == [_CANNED_PERSONA] * 3

    def test_generate_personas_returns_a_personas_and_skipped_tuple(self):
        chat = _FakeChat([_CANNED_RAW])
        result = _personas_module().generate_personas("Snacks", "Chips", 2, chat)
        assert isinstance(result, tuple) and len(result) == 2
        personas, skipped = result
        assert isinstance(personas, list)
        assert isinstance(skipped, int)

    def test_generate_personas_counts_unparseable_answers_as_skipped(self):
        chat = _FakeChat([_CANNED_RAW, "I refuse to answer.", _CANNED_RAW])
        personas, skipped = _personas_module().generate_personas(
            "Snacks", "Chips", 3, chat
        )
        assert len(chat.calls) == 3
        assert skipped == 1
        assert personas == [_CANNED_PERSONA, _CANNED_PERSONA]

    def test_generate_personas_sends_a_prompt_that_names_the_product(self):
        chat = _FakeChat([_CANNED_RAW])
        _personas_module().generate_personas(
            "Snacks", "Lay's Classic Potato Chips", 1, chat
        )
        assert chat.calls
        prompt = " ".join(m["content"] for m in chat.calls[0][0])
        assert "Lay's Classic Potato Chips" in prompt

    def test_generate_personas_forwards_the_temperature_to_chat(self):
        chat = _FakeChat([_CANNED_RAW])
        _personas_module().generate_personas(
            "Snacks", "Chips", 2, chat, temperature=0.8
        )
        assert chat.calls
        assert {t for _messages, t in chat.calls} == {0.8}

    def test_generate_personas_defaults_temperature_to_one(self):
        chat = _FakeChat([_CANNED_RAW])
        _personas_module().generate_personas("Snacks", "Chips", 2, chat)
        assert chat.calls
        assert {t for _messages, t in chat.calls} == {1.0}

    def test_generate_personas_is_deterministic_for_the_same_seed(self):
        answers = [_CANNED_RAW, _CANNED_RAW.replace("teacher", "nurse")]
        first, _ = _personas_module().generate_personas(
            "Snacks", "Chips", 4, _FakeChat(answers), seed=42
        )
        second, _ = _personas_module().generate_personas(
            "Snacks", "Chips", 4, _FakeChat(answers), seed=42
        )
        assert first == second

    def test_generate_personas_with_zero_n_makes_no_calls(self):
        chat = _FakeChat([_CANNED_RAW])
        personas, skipped = _personas_module().generate_personas(
            "Snacks", "Chips", 0, chat
        )
        assert chat.calls == []
        assert personas == []
        assert skipped == 0


# 5. render_demographics_block()


class TestRenderDemographicsBlock:
    def test_render_demographics_block_emits_one_line_per_field_in_order(self):
        persona = _persona()
        expected = [
            f"{field}: {persona[field]}" for field in _personas_module().PERSONA_FIELDS
        ]
        rendered = _personas_module().render_demographics_block(persona)
        assert rendered.splitlines() == expected

    def test_render_demographics_block_reflects_the_persona_values(self):
        persona = _persona(age=71, state="TX", household_income=120000)
        rendered = _personas_module().render_demographics_block(persona)
        assert "age: 71" in rendered
        assert "state: TX" in rendered
        assert "household_income: 120000" in rendered


# 6. BEHAVIORAL_MEASURES and render_extended_block()


class TestBehavioralMeasures:
    def test_behavioral_measures_lists_the_five_paper_measures(self):
        assert _personas_module().BEHAVIORAL_MEASURES == EXPECTED_MEASURES

    def test_behavioral_measures_names_are_unique_strings(self):
        measures = _personas_module().BEHAVIORAL_MEASURES
        assert len(measures) == len(set(measures))
        assert all(isinstance(name, str) and name for name in measures)


class TestRenderExtendedBlock:
    def test_extended_block_opens_with_the_full_demographics_block(self):
        persona = _full_persona()
        extended = _personas_module().render_extended_block(persona)
        demographic = _personas_module().render_demographics_block(persona)
        assert extended.splitlines()[: len(demographic.splitlines())] == (
            demographic.splitlines()
        )

    def test_extended_block_reports_score_and_percentile_per_measure(self):
        rendered = _personas_module().render_extended_block(_full_persona())
        assert "tightwad_spendthrift: 42 (P18 percentile)" in rendered
        assert "discount_rate: 6.2 (P71 percentile)" in rendered
        assert "present_bias: 33 (P9 percentile)" in rendered
        assert "risk_aversion: 7.5 (P88 percentile)" in rendered
        assert "loss_aversion: 4.0 (P62 percentile)" in rendered

    def test_extended_block_notes_the_scale_direction_of_each_measure(self):
        rendered = _personas_module().render_extended_block(_full_persona())
        lines = rendered.splitlines()
        direction_words = ("higher", "lower", "more", "less")
        for name in _personas_module().BEHAVIORAL_MEASURES:
            index = next(
                i for i, line in enumerate(lines) if line.startswith(name + ":")
            )
            note = lines[index + 1]
            assert note.startswith("<note:"), name
            assert any(word in note for word in direction_words), name
            assert name in note, name

    def test_extended_block_skips_missing_measures_silently(self):
        persona = _full_persona()
        del persona["tightwad_spendthrift"]
        del persona["present_bias"]
        del persona["risk_aversion"]
        rendered = _personas_module().render_extended_block(persona)
        assert "discount_rate: 6.2 (P71 percentile)" in rendered
        assert "loss_aversion: 4.0 (P62 percentile)" in rendered
        assert "<note:" in rendered
        assert "tightwad_spendthrift" not in rendered
        assert "present_bias" not in rendered
        assert "risk_aversion" not in rendered

    def test_extended_block_without_measures_is_just_the_demographics(self):
        persona = _persona()
        extended = _personas_module().render_extended_block(persona)
        assert (
            extended.splitlines()
            == _personas_module().render_demographics_block(persona).splitlines()
        )


# 6b. render_persona_fields(persona, depth) — depth-truncation rendering


def _rendered_field_names(rendered: str) -> set[str]:
    """Return the field names that head a "name: value" line in a block.

    Notes (lines starting "<note:") and prose never count, so the result is
    exactly the persona fields the renderer chose to show.
    """
    names: set[str] = set()
    for line in rendered.splitlines():
        name, separator, _ = line.partition(":")
        name = name.strip()
        if separator and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            names.add(name)
    return names


class TestRenderPersonaFields:
    """The depth-truncation renderer: one persona, five depth cut-points.

    render_persona_fields(persona, depth) renders the SAME persona dict with
    the fields of one depth tier: "none" renders nothing, and each deeper
    tier adds that tier's fields, so the rendered field sets must nest
    strictly (demographics < tightwad < time_preference < risk_preference).
    Partial personas keep the TASK-1456 tolerance: missing keys are skipped,
    never KeyError.
    """

    def test_none_depth_renders_no_fields(self):
        rendered = _personas_module().render_persona_fields(_full_persona(), "none")
        assert rendered == ""
        assert _rendered_field_names(rendered) == set()

    def test_each_depth_renders_exactly_its_own_field_set(self):
        for depth, expected in DEPTH_FIELD_SETS.items():
            rendered = _personas_module().render_persona_fields(_full_persona(), depth)
            assert _rendered_field_names(rendered) == expected, depth

    def test_rendered_field_sets_nest_strictly_across_the_five_depths(self):
        sets = [
            _rendered_field_names(
                _personas_module().render_persona_fields(_full_persona(), depth)
            )
            for depth in DEPTHS
        ]
        for shallower, deeper in zip(sets, sets[1:]):
            assert shallower < deeper, "rendered field sets must nest strictly"

    def test_render_persona_fields_rejects_an_unknown_depth(self):
        render = _personas_module().render_persona_fields
        # "extended" was the superseded third tier; it must no longer render.
        for depth in ("extended", "deep", "occluded"):
            with pytest.raises(ValueError):
                render(_full_persona(), depth)

    def test_partial_persona_renders_without_keyerror_at_every_depth(self):
        # TASK-1456 behavior: a dict missing most fields still renders the
        # fields it carries — the canonical ones it has plus extra scalar keys
        # such as city — and never raises KeyError, at any depth. Measures the
        # persona lacks are skipped, so they can never appear either.
        partial = {
            "age": 35,
            "occupation": "teacher",
            "city": "Hangzhou",
            "tightwad_spendthrift": {"score": 42, "percentile": 18},
        }
        for depth in DEPTHS:
            rendered = _personas_module().render_persona_fields(partial, depth)
            names = _rendered_field_names(rendered)
            if depth == "none":
                assert names == set()
                continue
            assert names >= {"age", "occupation", "city"}, depth
            expected = {"age", "occupation", "city"}
            if depth != "demographics":
                expected.add("tightwad_spendthrift")
            assert names == expected, depth


# 7. check_persona_diversity()


class TestCheckPersonaDiversity:
    def test_identical_personas_report_zero_distinctness(self):
        result = _personas_module().check_persona_diversity([_persona()] * 500)
        assert set(result) == {
            "n",
            "unique",
            "top_repeat_count",
            "top_repeat_share",
            "distinct_ratio",
        }
        assert result["n"] == 500
        assert result["unique"] == 1
        assert result["top_repeat_count"] == 500
        assert result["top_repeat_share"] == pytest.approx(1.0)
        assert result["distinct_ratio"] == pytest.approx(0.0)

    def test_all_distinct_personas_report_full_distinctness(self):
        personas = [_persona(age=age) for age in range(20, 520)]
        result = _personas_module().check_persona_diversity(personas)
        assert result["n"] == 500
        assert result["unique"] == 500
        assert result["top_repeat_count"] == 1
        assert result["top_repeat_share"] == pytest.approx(1 / 500)
        assert result["distinct_ratio"] == pytest.approx(1.0)

    def test_diversity_report_breaks_ties_by_exact_dict_content(self):
        personas = [_persona()] * 3 + [_persona(age=44)] * 2 + [_persona(age=55)]
        result = _personas_module().check_persona_diversity(personas)
        assert result["n"] == 6
        assert result["unique"] == 3
        assert result["top_repeat_count"] == 3
        assert result["top_repeat_share"] == pytest.approx(0.5)
        assert result["distinct_ratio"] == pytest.approx(0.4)


# 8. check_persona_coherence()


COHERENCE_RULES = {
    "age_range",
    "children_capacity",
    "income_nonnegative",
    "retirement_age",
    "household_size_min",
}


class TestCheckPersonaCoherence:
    def test_clean_personas_report_no_violations(self):
        personas = [
            _persona(),
            _persona(age=18, household_size=1, number_of_children=0),
        ]
        result = _personas_module().check_persona_coherence(personas)
        assert set(result) == {"n_violations", "rates", "examples"}
        assert result["n_violations"] == 0
        assert set(result["rates"]) == COHERENCE_RULES
        assert all(rate == 0.0 for rate in result["rates"].values())
        assert result["examples"] == []

    def test_age_outside_the_paper_range_is_a_violation(self):
        personas = [_persona(), _persona(age=17)]
        result = _personas_module().check_persona_coherence(personas)
        assert result["rates"]["age_range"] == pytest.approx(0.5)

    def test_too_many_children_for_the_household_is_a_violation(self):
        personas = [_persona(), _persona(household_size=1, number_of_children=1)]
        result = _personas_module().check_persona_coherence(personas)
        assert result["rates"]["children_capacity"] == pytest.approx(0.5)

    def test_negative_income_is_a_violation(self):
        personas = [_persona(), _persona(household_income=-5)]
        result = _personas_module().check_persona_coherence(personas)
        assert result["rates"]["income_nonnegative"] == pytest.approx(0.5)

    def test_retired_occupation_below_age_fifty_is_a_violation(self):
        personas = [_persona(), _persona(age=40, occupation="Retired Teacher")]
        result = _personas_module().check_persona_coherence(personas)
        assert result["rates"]["retirement_age"] == pytest.approx(0.5)

    def test_empty_household_is_a_violation(self):
        personas = [_persona(), _persona(household_size=0)]
        result = _personas_module().check_persona_coherence(personas)
        assert result["rates"]["household_size_min"] == pytest.approx(0.5)

    def test_n_violations_counts_events_and_examples_list_offenders_once(self):
        double_offender = _persona(age=17, household_income=-5)
        result = _personas_module().check_persona_coherence(
            [_persona(), double_offender]
        )
        assert result["n_violations"] == 2
        assert len(result["examples"]) == 1
        assert result["examples"] == [double_offender]

    def test_boundary_values_are_not_violations(self):
        personas = [
            _persona(age=18),
            _persona(age=100),
            _persona(household_income=0),
            _persona(household_size=1, number_of_children=0),
            _persona(age=60, occupation="retired nurse"),
        ]
        result = _personas_module().check_persona_coherence(personas)
        assert result["n_violations"] == 0


# 9. compare_to_census() and load_census_marginals()


class TestCompareToCensus:
    def test_numeric_fields_report_mean_gap(self):
        personas = [
            _persona(age=20),
            _persona(age=30),
            _persona(age=40),
            _persona(age=50),
        ]
        result = _personas_module().compare_to_census(personas, {"age": {"mean": 60}})
        assert set(result) == {"age"}
        assert result["age"]["sample"] == pytest.approx(35.0)
        assert result["age"]["census"] == pytest.approx(60.0)
        assert result["age"]["gap"] == pytest.approx(-25.0)

    def test_categorical_fields_report_total_variation_distance(self):
        personas = [
            _persona(gender="female"),
            _persona(gender="female"),
            _persona(gender="female"),
            _persona(gender="male"),
        ]
        marginals = {"gender": {"shares": {"female": 0.52, "male": 0.48}}}
        result = _personas_module().compare_to_census(personas, marginals)
        assert set(result) == {"gender"}
        assert result["gender"]["sample"] == pytest.approx(
            {"female": 0.75, "male": 0.25}
        )
        assert result["gender"]["census"] == marginals["gender"]["shares"]
        tv = 0.5 * (abs(0.75 - 0.52) + abs(0.25 - 0.48))
        assert result["gender"]["gap"] == pytest.approx(tv)

    def test_result_has_exactly_the_fields_given_in_marginals(self):
        personas = [_persona(age=30), _persona(age=50)]
        marginals = {"age": {"mean": 40}, "state": {"shares": {"CA": 0.5, "TX": 0.5}}}
        result = _personas_module().compare_to_census(personas, marginals)
        assert set(result) == {"age", "state"}


class TestLoadCensusMarginals:
    def test_load_census_marginals_reads_the_bundled_file_when_it_exists(self):
        if not CENSUS_PATH.exists():
            pytest.skip(
                "census_marginals_us_approx.json is created by the implement task"
            )
        loaded = _personas_module().load_census_marginals()
        for field in (
            "age",
            "gender",
            "education",
            "household_income",
            "state",
            "home_ownership",
        ):
            assert field in loaded, f"bundled census file lacks {field!r}"
            entry = loaded[field]
            assert "mean" in entry or "shares" in entry, field

    def test_load_census_marginals_accepts_an_explicit_path(self, tmp_path):
        payload = {"age": {"mean": 42.0}, "gender": {"shares": {"female": 0.5}}}
        census_file = tmp_path / "census.json"
        census_file.write_text(
            '{"age": {"mean": 42.0}, "gender": {"shares": {"female": 0.5}}}'
        )
        loaded = _personas_module().load_census_marginals(census_file)
        assert loaded == payload


# 10. scripts/generate_personas.py


def _load_personas_script():
    """Import scripts/generate_personas.py by file path (no package import)."""
    spec = importlib.util.spec_from_file_location("generate_personas", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"no loader for {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module.__name__, None)
    return module


class TestGeneratePersonasScript:
    def test_script_defines_main_behind_a_main_guard(self):
        module = _load_personas_script()
        assert callable(module.main)
        assert "argv" in inspect.signature(module.main).parameters
        assert inspect.signature(module.main).parameters["argv"].default is None
        assert 'if __name__ == "__main__":' in SCRIPT_PATH.read_text()

    def test_importing_the_script_never_opens_a_socket(self):
        def _forbid_socket(*_args, **_kwargs):
            raise AssertionError("importing generate_personas must not open a socket")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(socket, "socket", _forbid_socket)
        try:
            module = _load_personas_script()
        finally:
            monkeypatch.undo()
        assert callable(module.main)

    def test_script_help_exits_zero_and_lists_every_option(self, capsys):
        module = _load_personas_script()
        with pytest.raises(SystemExit) as excinfo:
            module.main(["--help"])
        assert excinfo.value.code == 0
        help_text = capsys.readouterr().out
        for option in (
            "--category",
            "--product",
            "--n",
            "--out",
            "--model",
            "--base-url",
            "--temperature",
            "--seed",
        ):
            assert option in help_text, f"missing option {option} in --help"

    def test_parser_applies_the_documented_defaults(self):
        module = _load_personas_script()
        args = module._parse_args(["--category", "Snacks", "--product", "Chips"])
        assert args.category == "Snacks"
        assert args.product == "Chips"
        assert args.n == 500
        assert args.out == "results/personas"
        assert args.base_url == "http://127.0.0.1:8080"
        assert args.temperature == 1.0
        assert args.seed is None

    def test_parser_reads_every_explicit_option(self):
        module = _load_personas_script()
        args = module._parse_args(
            [
                "--category",
                "Soft Drinks - Carbonated",
                "--product",
                "Coca-Cola",
                "--n",
                "3",
                "--out",
                "results/pilot",
                "--model",
                "qwen3-8b",
                "--base-url",
                "http://localhost:1234/v1",
                "--temperature",
                "0.8",
                "--seed",
                "7",
            ]
        )
        assert args.category == "Soft Drinks - Carbonated"
        assert args.product == "Coca-Cola"
        assert args.n == 3
        assert args.out == "results/pilot"
        assert args.model == "qwen3-8b"
        assert args.base_url == "http://localhost:1234/v1"
        assert args.temperature == 0.8
        assert args.seed == 7
