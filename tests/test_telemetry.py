"""
Application Insights wiring in `shared/telemetry.py`.

The module makes one promise in its own docstring: monitoring must never break
ticket submission. These tests hold it to that. They do not assert that spans
are exported -- that would be testing the OpenTelemetry SDK rather than our
code -- they check the two states this project actually runs in:

  * no connection string (local development, CI, every other test file)
  * a connection string that is present but unusable

Neither must raise, and neither must stop a ticket being created.
"""

import json

import azure.functions as func
import pytest

from shared import telemetry
from shared.repository import get_repository

CONNECTION_STRING = "APPLICATIONINSIGHTS_CONNECTION_STRING"


@pytest.fixture(autouse=True)
def reset_telemetry(clean_env):
    """
    `_configured` is module state that survives between tests, so a test that
    configures telemetry would otherwise make the next one a no-op.
    """
    get_repository(clean_env, refresh=True)
    telemetry._configured = False
    yield
    telemetry._configured = False


def explode(*args, **kwargs):
    raise RuntimeError("Application Insights is unreachable")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_no_connection_string_means_no_configuration():
    """
    This is what keeps the rest of the suite offline. If the guard were ever
    removed, every test that imports `tickets` would try to reach Azure.
    """
    telemetry.configure_telemetry()
    assert telemetry._configured is False


def test_configuration_runs_once_per_worker(monkeypatch):
    calls = []
    monkeypatch.setenv(CONNECTION_STRING, "InstrumentationKey=00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(
        "azure.monitor.opentelemetry.configure_azure_monitor",
        lambda **kwargs: calls.append(kwargs),
    )

    telemetry.configure_telemetry()
    telemetry.configure_telemetry()
    telemetry.configure_telemetry()

    assert len(calls) == 1, "configure_azure_monitor should be called once, not per request"
    assert telemetry._configured is True


def test_a_broken_connection_string_is_swallowed(monkeypatch):
    monkeypatch.setenv(CONNECTION_STRING, "this-is-not-a-connection-string")
    monkeypatch.setattr("azure.monitor.opentelemetry.configure_azure_monitor", explode)

    telemetry.configure_telemetry()  # must not raise

    assert telemetry._configured is False, (
        "a failed setup must stay unconfigured so the next worker can retry"
    )


# ---------------------------------------------------------------------------
# The tracer
# ---------------------------------------------------------------------------

def test_spans_work_without_any_configuration():
    """
    `get_tracer()` returns a no-op tracer when Azure Monitor was never set up.
    The handlers open spans unconditionally, so this has to be safe.
    """
    tracer = telemetry.get_tracer()
    with tracer.start_as_current_span("classify-ticket") as span:
        span.set_attribute("ticket.category", "IT Support")


# ---------------------------------------------------------------------------
# The promise: monitoring never breaks ticket submission
# ---------------------------------------------------------------------------

def test_a_ticket_is_still_created_when_telemetry_fails(monkeypatch):
    """
    A bad APPLICATIONINSIGHTS_CONNECTION_STRING in the Static Web App settings
    must not turn every POST /api/tickets into a 500.
    """
    import tickets

    monkeypatch.setenv(CONNECTION_STRING, "InstrumentationKey=broken")
    monkeypatch.setattr("azure.monitor.opentelemetry.configure_azure_monitor", explode)

    response = tickets.main(func.HttpRequest(
        method="POST",
        url="/api/tickets",
        body=json.dumps({
            "name": "Aiman Rahman",
            "email": "aiman@example.com",
            "title": "Cannot access campus Wi-Fi",
            "description": "I cannot connect to the campus Wi-Fi from my laptop.",
            "priority": "Medium",
        }).encode("utf-8"),
        params={},
        headers={},
    ))

    assert response.status_code == 201
    assert json.loads(response.get_body())["category"] == "IT Support"
