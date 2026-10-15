"""Browser + frontend + API + DynamoDB/S3 emulati; nessuna risorsa AWS reale."""

import base64
import hashlib
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from emulated_http_check import free_port
from moto.server import ThreadedMotoServer
from PIL import Image
from playwright.sync_api import expect, sync_playwright


def check_oauth(browser, web, base):
    """Client OAuth con endpoint intercettati; non equivale a un login Cognito reale."""
    context = browser.new_context()
    page = context.new_page()
    authorization, grants, bearer_tokens = {}, [], []

    def api_route(route):
        if route.request.url.endswith("/api/config"):
            route.fulfill(
                json={
                    "mode": "aws",
                    "cognito_domain": "https://identity.example.invalid",
                    "cognito_client_id": "synthetic-browser-client",
                    "resource": base + "/mcp",
                }
            )
        else:
            headers = route.request.headers
            bearer = headers.get("authorization", "")
            if bearer.startswith("Bearer oauth-synthetic-"):
                bearer_tokens.append(bearer)
                route.continue_(
                    headers={**headers, "authorization": "Bearer demo-user-1"}
                )
            else:
                route.continue_()

    def identity_route(route):
        params = parse_qs(urlparse(route.request.url).query)
        if "/oauth2/authorize?" in route.request.url:
            authorization.update({key: values[0] for key, values in params.items()})
            assert authorization["code_challenge_method"] == "S256"
            assert authorization["resource"] == base + "/mcp"
            assert "scale-mobili/stats:read" in authorization["scope"]
            route.fulfill(
                status=302,
                headers={
                    "Location": web
                    + "/callback?code=synthetic-code&state="
                    + authorization["state"]
                },
            )
        else:
            payload = parse_qs(route.request.post_data)
            grants.append(payload["grant_type"][0])
            if payload["grant_type"] == ["authorization_code"]:
                actual = (
                    base64.urlsafe_b64encode(
                        hashlib.sha256(payload["code_verifier"][0].encode()).digest()
                    )
                    .decode()
                    .rstrip("=")
                )
                assert actual == authorization["code_challenge"]
            route.fulfill(
                json={
                    "access_token": "oauth-synthetic-" + str(len(grants)),
                    "expires_in": 3600,
                    "refresh_token": "synthetic-refresh-only",
                },
                headers={"Access-Control-Allow-Origin": "*"},
            )

    page.route("**/api/**", api_route)
    page.route("https://identity.example.invalid/**", identity_route)
    page.goto(web + "/segnala/", wait_until="networkidle")
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(
        page.get_by_role("button", name="Prova la modalità moderatore")
    ).to_have_count(0)
    page.get_by_role("button", name="Accedi al tuo account").click()
    expect(page.locator("#station")).to_be_visible()
    assert page.url == web + "/segnala/"
    assert grants == ["authorization_code"]
    assert page.evaluate("sessionStorage.getItem('smt.oauth')") is None
    page.evaluate("""() => {
        const tokens = JSON.parse(sessionStorage.getItem('smt.tokens'));
        tokens.expires_at = 0;
        sessionStorage.setItem('smt.tokens', JSON.stringify(tokens));
    }""")
    page.reload(wait_until="networkidle")
    expect(page.locator("#station")).to_be_visible()
    assert grants == ["authorization_code", "refresh_token"]
    assert "Bearer oauth-synthetic-2" in bearer_tokens
    # An unsolicited callback must not exchange a code.
    page.goto(web + "/callback?code=unsolicited&state=wrong", wait_until="networkidle")
    expect(page.get_by_role("status")).to_contain_text("Accesso non avviato")
    assert grants == ["authorization_code", "refresh_token"]
    assert "?" not in page.url
    context.close()


def main():
    root = Path(__file__).resolve().parents[1]
    data_port, api_port, web_port = free_port(), free_port(), free_port()
    base, web = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    emulator = ThreadedMotoServer(ip_address="127.0.0.1", port=data_port, verbose=False)
    emulator.start()
    env = {
        **os.environ,
        "AWS_ACCESS_KEY_ID": "local-only",
        "AWS_SECRET_ACCESS_KEY": "local-only",
        "AWS_SESSION_TOKEN": "",
        "AWS_EC2_METADATA_DISABLED": "true",
        "SMT_MODE": "local",
        "SMT_CORE_TABLE": "smt-browser-core",
        "SMT_EVENTS_TABLE": "smt-browser-events",
        "SMT_PHOTOS_BUCKET": "smt-browser-photos",
        "SMT_SOURCES_BUCKET": "smt-browser-sources",
        "SMT_DYNAMODB_ENDPOINT": f"http://127.0.0.1:{data_port}",
        "SMT_S3_ENDPOINT": f"http://127.0.0.1:{data_port}",
        "SMT_CURSOR_SECRET": "browser-local-only-at-least-32-characters",
        "SMT_PUBLIC_URL": base,
        "SMT_FRONTEND_URL": web,
        "SMT_API_PROXY": base,
        "PUBLIC_API_URL": "",
        "PUBLIC_COGNITO_DOMAIN": "",
        "PUBLIC_COGNITO_CLIENT_ID": "",
        "PUBLIC_BROWSER_DEMO": "false",
        "PUBLIC_DEV_LOGIN": "true",
    }
    processes = []
    try:
        for args in (["bootstrap-local"], ["seed", "--synthetic"]):
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from scale_mobili.cli import main; main()",
                    *args,
                ],
                cwd=root,
                env=env,
                check=True,
            )
        with tempfile.TemporaryFile() as logs:

            def start_api():
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "scale_mobili.app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--no-access-log",
                    ],
                    cwd=root,
                    env=env,
                    stdout=logs,
                    stderr=logs,
                )
                processes.append(process)
                return process

            def wait_ready(url):
                for _ in range(200):
                    if any(p.poll() is not None for p in processes):
                        logs.seek(0)
                        raise RuntimeError(logs.read().decode()[-4000:])
                    try:
                        if httpx.get(url, timeout=1).status_code == 200:
                            return
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                raise RuntimeError(f"Server non pronto: {url}")

            api = start_api()
            processes.append(
                subprocess.Popen(
                    [
                        "npm",
                        "run",
                        "dev",
                        "--",
                        "--port",
                        str(web_port),
                        "--strictPort",
                    ],
                    cwd=root / "frontend",
                    env=env,
                    stdout=logs,
                    stderr=logs,
                )
            )
            wait_ready(base + "/health")
            wait_ready(web)
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=shutil.which("chromium"),
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1100}, locale="it-IT"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                private_calls = []
                page.on(
                    "request",
                    lambda r: (
                        private_calls.append(r.url)
                        if "/api/stats/private" in r.url
                        else None
                    ),
                )
                page.goto(web, wait_until="networkidle")
                expect(page.locator(".availability-value")).to_have_text("0%")
                assert not private_calls
                page.get_by_role("button", name="Esplora la panoramica").click()
                expect(page.locator(".locked-statistic")).to_have_count(3)
                expect(page.locator(".station-card")).to_have_count(4)
                expect(page.locator(".device-row")).to_have_count(9)
                page.get_by_role(
                    "button", name="Invia una segnalazione", exact=True
                ).click()
                expect(page.get_by_role("dialog")).to_be_visible()
                page.get_by_role("button", name="Continua come cittadino").click()
                expect(page.locator("#station")).to_be_visible()
                page.locator("#station").select_option("demo-station")
                page.locator("#device").select_option("demo-esc-1")
                page.get_by_role("radio", name="Funzionante", exact=True).check()
                page.locator("#description").fill(
                    "Osservazione persistente dal browser QA"
                )
                image = io.BytesIO()
                Image.new("RGB", (40, 30), "#284b70").save(image, "PNG")
                page.locator("#photo").set_input_files(
                    {
                        "name": "qa.png",
                        "mimeType": "image/png",
                        "buffer": image.getvalue(),
                    }
                )
                expect(page.locator(".photo-preview")).to_be_visible()
                # Lost response after commit: retry must preserve the same intent and photo.
                saved = []

                def lose_once(route):
                    result = route.fetch()
                    assert result.status == 201
                    saved.append(result.json())
                    route.abort()
                    page.unroute("**/api/devices/demo-esc-1/reports", lose_once)

                page.route("**/api/devices/demo-esc-1/reports", lose_once)
                page.get_by_role(
                    "button", name="Invia segnalazione", exact=True
                ).click()
                expect(page.locator(".toast.error")).to_be_visible()
                page.get_by_role(
                    "button", name="Invia segnalazione", exact=True
                ).click()
                expect(page.locator(".toast.success")).to_contain_text(
                    "Segnalazione inviata"
                )
                expect(page.locator(".availability-value")).to_have_text("11%")
                expect(page.locator(".feed-item")).to_have_count(1)
                expect(page.locator(".feed-photo")).to_have_count(0)
                assert len(saved) == 1
                assert private_calls
                assert (
                    page.evaluate("sessionStorage.getItem('smt.platform-demo.v2')")
                    is None
                )
                page.get_by_role(
                    "button", name="Proponi un impianto", exact=True
                ).first.click()
                page.locator("#station").select_option("demo-station")
                page.locator("#kind").select_option("ascensore")
                page.locator("#proposal-name").fill("Ascensore proposto dal browser QA")
                page.locator("#location").fill("Posizione fittizia per il collaudo")
                page.locator("#photo").set_input_files(
                    {
                        "name": "qa.png",
                        "mimeType": "image/png",
                        "buffer": image.getvalue(),
                    }
                )
                expect(page.locator(".photo-preview")).to_be_visible()
                page.get_by_role("button", name="Invia proposta", exact=True).click()
                expect(page.locator(".my-proposals")).to_contain_text(
                    "Ascensore proposto dal browser QA"
                )
                expect(page.locator(".device-row")).to_have_count(9)
                page.reload(wait_until="networkidle")
                expect(page.locator(".my-proposals")).to_contain_text(
                    "In attesa di approvazione"
                )
                # Restart the API while keeping the emulator running.
                api.terminate()
                api.wait(timeout=10)
                processes.remove(api)
                api = start_api()
                wait_ready(base + "/health")
                page.reload(wait_until="networkidle")
                expect(page.locator(".feed-item")).to_have_count(1)
                expect(page.locator(".my-proposals")).to_contain_text(
                    "Ascensore proposto dal browser QA"
                )
                page.get_by_role("button", name="Esci", exact=True).click()
                expect(page.locator(".locked-statistic")).to_have_count(3)
                expect(page.locator(".my-proposals")).to_have_count(0)
                expect(page.locator(".alignment-number")).to_have_count(0)
                page.get_by_role("button", name="Accedi", exact=True).click()
                page.get_by_role("button", name="Prova la modalità moderatore").click()
                expect(page.get_by_role("dialog")).to_have_count(0)
                page.get_by_role("button", name="Moderazione").click()
                expect(page.locator(".moderation-card")).to_have_count(1)
                expect(page.locator(".moderation-photo")).to_be_visible()
                expect(
                    page.get_by_role("button", name="Approva impianto")
                ).to_be_disabled()
                page.get_by_label("Motivazione della decisione (privata)").fill(
                    "Censimento fittizio verificato nel collaudo"
                )
                page.get_by_role("button", name="Approva impianto").click()
                expect(page.locator(".toast.success")).to_contain_text(
                    "Impianto approvato"
                )
                expect(page.locator(".moderation-card")).to_have_count(0)
                page.get_by_role("button", name="Foto in revisione").click()
                expect(page.locator(".moderation-card")).to_have_count(2)
                expect(page.locator(".moderation-photo")).to_have_count(2)
                for card in page.locator(".moderation-card").all():
                    expect(card.locator("img")).to_be_visible()
                page.locator(".moderation-card").first.get_by_label(
                    "Motivazione della decisione (privata)"
                ).fill("Fotografia sintetica senza dati personali")
                page.get_by_role("button", name="Approva foto").first.click()
                expect(page.locator(".moderation-card")).to_have_count(1)
                page.locator(".moderation-card").first.get_by_label(
                    "Motivazione della decisione (privata)"
                ).fill("Fotografia sintetica senza dati personali")
                page.get_by_role("button", name="Approva foto").click()
                expect(page.locator(".moderation-card")).to_have_count(0)
                page.get_by_role("button", name="Panoramica", exact=True).click()
                expect(page.locator(".device-row")).to_have_count(10)
                expect(page.locator(".feed-photo")).to_have_count(1)
                expect(page.locator(".availability-value")).to_have_text("10%")
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                page.screenshot(
                    path="/tmp/torino-backend-connected.png", full_page=True
                )
                # Independent visitor can read the saved report and approved photo.
                visitor = browser.new_context()
                guest = visitor.new_page()
                guest.goto(web + "/home/", wait_until="networkidle")
                expect(guest.locator(".feed-item")).to_have_count(1)
                expect(guest.locator(".feed-photo")).to_have_count(1)
                expect(guest.locator(".locked-statistic")).to_have_count(3)
                assert not errors, errors
                check_oauth(browser, web, base)
                browser.close()
            print(
                "Browser + API: letture pubbliche, login, retry senza duplicati, foto private/pubbliche, proposte, moderazione, persistenza tra riavvii e sessioni, OAuth/PKCE/rinnovo simulati, viewport mobile: OK."
            )
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        emulator.stop()


if __name__ == "__main__":
    main()
