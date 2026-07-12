from fragarach_ii.operational_decision import (
    OperationalDecision,
    OperationalStatus,
    aggregate,
    degraded,
    hard_block,
)


def test_amber_and_missing_maximum_proof_keep_safe_actions():
    decision = degraded(
        "AUDUSD:D1:MAXIMUM_HISTORY",
        "Terminal-boundary proof is unavailable.",
        safe_fallbacks=("CUSTOM_RANGE", "IMPORT_FILE"),
        unaffected_operations=("RETIRE", "TRUTH"),
    )
    assert not decision.hard_block
    assert decision.status is OperationalStatus.DEGRADED_OPERATION_AVAILABLE
    assert "CUSTOM_RANGE" in decision.safe_fallbacks


def test_missing_overlap_keeps_custom_range_and_provider_failure_keeps_import():
    update = degraded("AUDUSD:D1:UPDATE", "Automatic overlap is unavailable.", safe_fallbacks=("CUSTOM_RANGE", "IMPORT_FILE"))
    provider = degraded("AUDUSD:D1:PROVIDER", "Provider rejected the call.", safe_fallbacks=("IMPORT_FILE",))
    assert update.safe_fallbacks == ("CUSTOM_RANGE", "IMPORT_FILE")
    assert provider.safe_fallbacks == ("IMPORT_FILE",)


def test_unsupported_m5_does_not_block_d1_and_d1_only_is_implementation_owned():
    decision = degraded(
        "AUDUSD:M5",
        "The D1-only implementation has not caught up with ratified M5 authority.",
        safe_fallbacks=("RUN_D1", "IMPORT_D1"),
        unaffected_operations=("AUDUSD:D1",),
    )
    assert decision.repair_owner == "IMPLEMENTATION"
    assert "AUDUSD:D1" in decision.unaffected_operations


def test_retired_scope_is_hard_block_but_import_for_other_instruments_continues():
    decision = hard_block("JPYCHF:D1:ACQUISITION", "Retired authority cannot receive new evidence.", unaffected_operations=("AUDUSD:D1:IMPORT",))
    assert decision.hard_block
    assert decision.status is OperationalStatus.HARD_BLOCK_AFFECTED_PATH
    assert decision.unaffected_operations == ("AUDUSD:D1:IMPORT",)


def test_partial_success_is_completed_with_warnings():
    success = OperationalDecision(OperationalStatus.SUCCESS, False, "AUDUSD:D1", "Completed")
    m5 = degraded("AUDUSD:M5", "Implementation unavailable", safe_fallbacks=("RUN_D1",))
    result = aggregate((success, m5))
    assert result.status is OperationalStatus.COMPLETED_WITH_WARNINGS
    assert not result.hard_block


def test_degraded_results_require_fallbacks():
    try:
        degraded("D1", "missing", safe_fallbacks=())
    except ValueError:
        pass
    else:
        raise AssertionError("degraded result accepted without a safe fallback")
