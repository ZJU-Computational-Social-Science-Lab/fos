# RED-phase regression tests for the reasoning-channel wrapper that
# google/gemma-4-26b-a4b (llama-server) puts around its answers, e.g.
# "<|channel>thought\n<channel|>purchase". The parsers must strip this
# wrapper before reading the actual answer. Every test FAILS against the
# current parsers — that is the RED phase of TDD.

import pytest

from fos.experiments.sweep_kit import parse_fillin_number, parse_purchase

# Real recorded outputs from the sweep runs (859x purchase, 241x not purchase).
_PURCHASE_WRAPPED = "<|channel>thought\n<channel|>purchase"
_NOT_PURCHASE_WRAPPED = "<|channel>thought\n<channel|>not purchase"


class TestParsePurchaseStripsChannelWrapper:
    def test_parse_purchase_reads_a_wrapped_purchase_answer(self):
        assert parse_purchase(_PURCHASE_WRAPPED) is True

    def test_parse_purchase_reads_a_wrapped_not_purchase_answer(self):
        assert parse_purchase(_NOT_PURCHASE_WRAPPED) is False

    def test_parse_purchase_strips_the_wrapper_around_case_and_punctuation(self):
        assert parse_purchase("<|channel>thought\n<channel|>Purchase.") is True
        assert parse_purchase("<|channel>thought\n<channel|>'not purchase.'") is False


class TestParseFillinNumberStripsChannelWrapper:
    def test_parse_fillin_number_reads_a_number_after_the_wrapper(self):
        wrapped = "<|channel>thought\n<channel|>$8.26"
        assert parse_fillin_number(wrapped) == pytest.approx(8.26)
