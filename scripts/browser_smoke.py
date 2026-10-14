"""Collaudo browser della demo, con backend e Vite già avviati nel cloud.

uv run --project backend python scripts/browser_smoke.py
Richiede Chromium disponibile nel runtime oppure `playwright install chromium`.
Usare esclusivamente la demo sintetica; scrive segnalazioni di prova.
"""

import json
import shutil
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
        assert json.load(response)["mode"] == "demo", (
            "Collaudo riservato alla demo sintetica"
        )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(
            viewport={"width": 1400, "height": 1100},
            locale="it-IT",
            timezone_id="Europe/Rome",
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        expect(
            page.get_by_role("heading", name="Scala mobile fittizia 1")
        ).to_be_visible()
        page.get_by_label("Simula accesso di prova").select_option("demo-user-1")
        page.get_by_label("Stato osservato").select_option("guasta")
        page.get_by_role("button", name="Invia segnalazione").click()
        expect(
            page.get_by_role("status").filter(has_text="Segnalazione registrata")
        ).to_be_visible()
        expect(page.get_by_role("heading", name="Guasta", exact=True)).to_be_visible()
        page.get_by_label("Simula accesso di prova").select_option("demo-user-2")
        page.get_by_role("button", name="Rettifica", exact=True).last.click()
        page.get_by_label("Motivazione privata").fill(
            "Correzione sintetica per il collaudo"
        )
        page.get_by_role("button", name="Salva rettifica").click()
        expect(page.get_by_role("alert")).to_contain_text("solo le tue segnalazioni")
        page.get_by_label("Simula accesso di prova").select_option("demo-user-1")
        page.get_by_role("button", name="Salva rettifica").click()
        expect(
            page.get_by_role("status").filter(has_text="Rettifica registrata")
        ).to_be_visible()
        expect(
            page.get_by_role("heading", name="Funzionante", exact=True)
        ).to_be_visible()
        expect(
            page.get_by_text("Segnalazione · Guasta", exact=True).last
        ).to_be_visible()
        page.get_by_label("Simula accesso di prova").select_option("demo-user-2")
        page.get_by_role("button", name="Conferma", exact=True).last.click()
        expect(
            page.get_by_role("status").filter(has_text="Conferma registrata")
        ).to_be_visible()
        screenshot = Path("/tmp/scale-mobili-prototipo.png")
        page.screenshot(path=str(screenshot), full_page=True)
        page.set_viewport_size({"width": 375, "height": 812})
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        assert not errors, errors
        browser.close()
        print(
            "Browser: invio, rettifica autorizzata/negata, conferma e viewport mobile verificati."
        )
        print(f"Schermata: {screenshot}")


if __name__ == "__main__":
    main()
