"""Application Insights/OpenTelemetry setup shared by the API functions.

Telemetry is optional: local development and tests keep working when no
Application Insights connection string is configured.
"""

from __future__ import annotations

import logging
import os
import threading

from opentelemetry import trace

log = logging.getLogger("tickettriage.telemetry")

_configure_lock = threading.Lock()
_configured = False


def configure_telemetry() -> None:
    """Configure Azure Monitor once for the current Functions worker."""
    global _configured

    if _configured or not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip():
        return

    with _configure_lock:
        if _configured:
            return

        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(logger_name="tickettriage")
            _configured = True
        except Exception:  # noqa: BLE001 - monitoring must never break ticket submission
            log.exception("Application Insights telemetry could not be configured")


def get_tracer():
    """Return the Ticket Triage tracer (a harmless no-op when not configured)."""
    return trace.get_tracer("tickettriage")
