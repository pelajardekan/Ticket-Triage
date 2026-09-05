"""
Reachability checks against a DEPLOYED TicketTriage.

Everything in the rest of the suite runs offline against the in-memory
repository. These tests do the opposite: they prove the live app can actually
reach Cosmos DB and Azure AI Language, and that the frontend files were
deployed alongside the API.

They are skipped unless SMOKE_BASE_URL is set, so `pytest tests` stays offline,
credential-free and green on a laptop with no Azure account:

    # Bash
    SMOKE_BASE_URL=https://<your-app>.azurestaticapps.net python -m pytest tests/test_smoke_deployed.py -v

    # PowerShell
    $env:SMOKE_BASE_URL = "https://<your-app>.azurestaticapps.net"
    python -m pytest tests/test_smoke_deployed.py -v

A failure here means the deployment is wrong, not the code. Read the assertion
message: each one names the app setting or resource to check.
"""

import os

import pytest
import requests

BASE_URL = os.environ.get("SMOKE_BASE_URL", "").rstrip("/")
TIMEOUT = 20

pytestmark = pytest.mark.skipif(
    not BASE_URL,
    reason="set SMOKE_BASE_URL to the deployed site to run the smoke tests",
)


def get(path):
    return requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT)


@pytest.fixture(scope="module")
def health():
    """One call to /api/health, shared by every test that reads it."""
    response = get("/api/health")
    assert response.status_code == 200, (
        f"/api/health returned {response.status_code}. The managed API is not "
        f"responding, so nothing below can be trusted."
    )
    return response.json()


# ---------------------------------------------------------------------------
# Cosmos DB
# ---------------------------------------------------------------------------

def test_cosmos_is_the_live_storage_backend(health):
    """
    The repository falls back to in-memory when Cosmos is unreachable, and the
    app keeps serving, so a working site is not evidence Cosmos is connected.
    /api/health reports which backend actually loaded.
    """
    assert health["storage"] == "cosmos", (
        f"storage is '{health['storage']}', not 'cosmos'. Tickets are being "
        f"held in memory and will vanish when the function app recycles. "
        f"Check COSMOS_ENDPOINT and COSMOS_KEY in the Static Web App settings."
    )


# ---------------------------------------------------------------------------
# Azure AI Language
# ---------------------------------------------------------------------------

def test_azure_ai_language_is_configured(health):
    assert health["languageConfigured"] is True, (
        "languageConfigured is False. LANGUAGE_ENDPOINT and LANGUAGE_KEY are "
        "missing, so every ticket is being classified by the offline keyword "
        "rules instead of Azure AI."
    )


def test_azure_ai_language_leads_the_classifier_chain(health):
    """
    The cascade tries Azure first and silently drops to keyword rules when the
    call fails. The chain reports which stages are live, so this catches a
    resource that exists but is misconfigured or out of quota.
    """
    chain = health.get("classifierChain", [])
    assert chain, "health reported no classifierChain at all"
    assert chain[0].startswith("azure-ai-language"), (
        f"the chain starts with '{chain[0]}', so no Azure AI stage is active. "
        f"Full chain: {chain}"
    )


# ---------------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------------

def test_ticket_list_endpoint_is_reachable():
    response = get("/api/tickets")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload and "count" in payload


def test_ticket_detail_endpoint_is_reachable():
    listing = get("/api/tickets").json()
    if not listing.get("items"):
        pytest.skip("no tickets on the deployed app to open")

    ticket_id = listing["items"][0]["id"]
    response = get(f"/api/tickets/{ticket_id}")
    assert response.status_code == 200
    assert response.json()["id"] == ticket_id


# ---------------------------------------------------------------------------
# Frontend delivery
# ---------------------------------------------------------------------------

# Each page and the script it cannot render without.
PAGES = [
    ("/submit", "submit.js"),
    ("/lists", "lists.js"),
    ("/details", "details.js"),
    ("/admin/login", "admin-login.js"),
]


@pytest.mark.parametrize("path,script", PAGES)
def test_page_is_served_with_its_script(path, script):
    """
    A rewrite rule that stops matching, or a script left out of the build,
    both produce a page that loads and then does nothing. Checking the HTML
    references the script catches that without needing a browser.
    """
    response = get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"
    assert script in response.text, f"{path} does not reference {script}"


# Two files, not all of them: every script is served by the same static-content
# rule, so a third case would re-test the same mechanism. `api.js` is imported
# by every other module and `lists.js` drives the ticket table.
@pytest.mark.parametrize("script", ["api.js", "lists.js"])
def test_javascript_file_is_served(script):
    response = get(f"/js/{script}")
    assert response.status_code == 200, f"/js/{script} returned {response.status_code}"
    assert "javascript" in response.headers.get("content-type", ""), (
        f"/js/{script} was served as {response.headers.get('content-type')!r}. "
        f"The browser will refuse to execute it as a module."
    )
