import pytest

from capstone.memory.long_term import EntityMemoryStore
from capstone.memory.session import SessionMemory
from capstone.observability.logging import redact_fields
from capstone.observability.tracing import trace_span
from capstone.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError
from capstone.reliability.fallbacks import safe_fallback
from capstone.reliability.retries import call_with_retries


def test_retry_helper_retries_only_transient_errors():
    calls = {"n": 0}
    def operation():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("temporary")
        return "ok"
    assert call_with_retries(operation, max_attempts=3) == "ok"
    assert calls["n"] == 3


def test_retry_helper_does_not_retry_unconfigured_errors():
    calls = {"n": 0}
    def operation():
        calls["n"] += 1
        raise ValueError("not transient")
    with pytest.raises(ValueError):
        call_with_retries(operation, max_attempts=3)
    assert calls["n"] == 1


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_seconds=60)
    for _ in range(2):
        with pytest.raises(TimeoutError):
            breaker.call(lambda: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "should not run")


def test_safe_fallback_does_not_claim_action_success():
    result = safe_fallback()
    assert result["requires_human"] is True
    assert result["actions_executed"] is False


def test_session_memory_is_isolated_and_bounded():
    memory = SessionMemory(max_messages=2)
    memory.append("session-a", "user", "first")
    memory.append("session-a", "assistant", "second")
    memory.append("session-a", "user", "third")
    assert [m["content"] for m in memory.get("session-a")] == ["second", "third"]
    assert memory.get("session-b") == []


def test_entity_memory_persists_and_isolates_entities(tmp_path):
    store = EntityMemoryStore(tmp_path / "entities.json")
    store.add("customer-a", "Prefers email updates")
    store.add("customer-b", "Prefers SMS updates")
    assert store.get("customer-a")[0]["note"] == "Prefers email updates"
    assert len(store.get("customer-a")) == 1
    assert store.get("customer-b")[0]["note"] == "Prefers SMS updates"


def test_redaction_hides_secrets():
    assert redact_fields({"api_key": "secret", "nested": {"access_token": "abc"}}) == {
        "api_key": "[REDACTED]", "nested": {"access_token": "[REDACTED]"}
    }


def test_trace_span_reports_success_and_error():
    events = []
    with trace_span("demo", trace_id="trace-1", callback=events.append):
        pass
    assert events[-1]["status"] == "ok"
    with pytest.raises(ValueError):
        with trace_span("failure", callback=events.append):
            raise ValueError("oops")
    assert events[-1]["status"] == "error"
