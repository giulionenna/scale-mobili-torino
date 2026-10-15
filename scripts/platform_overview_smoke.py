"""Collaudo statistiche, copertura e sequenze della demo browser.

Richiede il server statico della demo su 127.0.0.1:5321.
Usa soltanto dati sintetici in una sessione Chromium isolata.
"""

import shutil
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 1100}, locale="it-IT"
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:5321/home/", wait_until="networkidle")
        page.get_by_role("button", name="Accedi", exact=True).click()
        page.get_by_role("button", name="Continua come cittadino").click()
        seed = page.evaluate(
            "JSON.parse(sessionStorage.getItem('smt.platform-demo.v2'))"
        )
        now = datetime.now(UTC)

        def report(status, minutes, recorded_minutes=None):
            item = deepcopy(seed["reports"][0])
            item.update(
                id=f"qa-{status}-{minutes}",
                status=status,
                observed_at=(now - timedelta(minutes=minutes)).isoformat(),
                recorded_at=(
                    now
                    - timedelta(
                        minutes=recorded_minutes
                        if recorded_minutes is not None
                        else minutes
                    )
                ).isoformat(),
            )
            return item

        def dataset(reports, official="funzionante"):
            data = deepcopy(seed)
            data["devices"] = data["devices"][:1]
            data["reports"] = reports
            data["officialExamples"] = (
                {} if official is None else {data["devices"][0]["id"]: official}
            )
            return data

        def restore(data):
            page.evaluate(
                "data => sessionStorage.setItem('smt.platform-demo.v2', JSON.stringify(data))",
                data,
            )
            page.reload(wait_until="networkidle")

        def check(working, alignment, new, streak):
            expect(page.locator(".availability-value")).to_have_text(working)
            expect(page.locator(".alignment-number > strong")).to_have_text(alignment)
            expect(
                page.get_by_role("button", name=f"Nuovi fermi {new}", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name=f"Streak {streak}", exact=True)
            ).to_be_visible()

        check("67%", "0%", 2, 0)
        expect(page.locator(".alignment-counts")).to_contain_text("6 senza confronto")
        toggle = page.locator(".availability-toggle")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(page.locator("#availability-details")).not_to_be_visible()
        toggle.focus()
        page.keyboard.press("Enter")
        expect(toggle).to_have_attribute("aria-expanded", "true")
        expect(page.locator(".availability-stations > div")).to_have_count(4)
        expect(page.locator("#availability-details")).to_contain_text("senza dati")
        page.keyboard.press("Enter")
        expect(page.locator("#availability-details")).not_to_be_visible()
        page.locator(".incident-row").first.click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.keyboard.press("Escape")
        page.get_by_role("link", name="Vedi il confronto").click()
        assert page.url.endswith("#comparison-detail")

        for reports, official in [
            ([], "funzionante"),
            ([report("non_verificabile", 10)], "funzionante"),
            ([report("funzionante", 10)], None),
            ([report("funzionante", 10)], "non_verificabile"),
        ]:
            restore(dataset(reports, official))
            expect(page.locator(".alignment-number > strong")).to_have_text("—")
            expect(page.locator(".alignment-number")).to_contain_text("0 su 0")
        restore(dataset([report("funzionante", 20)]))
        check("100%", "100%", 0, 0)
        restore(
            dataset(
                [
                    report("funzionante", 40),
                    report("guasta", 30),
                    report("manutenzione", 20),
                ]
            )
        )
        check("0%", "0%", 1, 1)
        page.get_by_role("button", name="Streak 1", exact=True).click()
        expect(page.locator(".incident-row")).to_contain_text(
            "2 segnalazioni consecutive"
        )
        restore(
            dataset(
                [
                    report("guasta", 30),
                    report("guasta", 20),
                    report("non_verificabile", 10),
                    report("guasta", 5),
                ]
            )
        )
        check("0%", "0%", 1, 0)
        restore(
            dataset(
                [report("guasta", 30), report("guasta", 20), report("funzionante", 5)]
            )
        )
        check("100%", "100%", 0, 0)
        restore(dataset([report("guasta", 49 * 60), report("guasta", 25 * 60)]))
        check("0%", "0%", 0, 1)
        restore(dataset([report("funzionante", 5, 4), report("guasta", 30, 0)]))
        check("100%", "100%", 0, 0)

        # Actual submissions update all three blocks immediately.
        def submit(status):
            page.get_by_role(
                "button", name="Invia una segnalazione", exact=True
            ).click()
            page.locator("#station").select_option(seed["devices"][0]["station_id"])
            page.locator("#device").select_option(seed["devices"][0]["id"])
            page.get_by_label(status, exact=True).check()
            page.get_by_role("button", name="Invia segnalazione", exact=True).click()

        submit("Fuori servizio")
        check("0%", "0%", 1, 0)
        submit("Fuori servizio")
        check("0%", "0%", 1, 1)
        submit("Funzionante")
        check("100%", "100%", 0, 0)
        empty = dataset([])
        empty["devices"] = []
        restore(empty)
        check("—", "—", 0, 0)
        restore(seed)
        for width in [375, 768, 950, 1100, 1440]:
            page.set_viewport_size({"width": width, "height": 1100})
            for expanded in [False, True]:
                if (
                    page.locator(".availability-toggle").get_attribute("aria-expanded")
                    != str(expanded).lower()
                ):
                    page.locator(".availability-toggle").click()
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                ), (width, expanded)
                card = page.locator(".availability-card").bounding_box()
                stack = page.locator(".overview-stack").bounding_box()
                assert abs(card["width"] - stack["width"]) < 1
            page.locator(".availability-toggle").click()
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path="/tmp/torino-home-overview.png", full_page=True)
        page.set_viewport_size({"width": 375, "height": 1100})
        page.screenshot(path="/tmp/torino-home-overview-mobile.png", full_page=True)
        assert not errors, errors
        browser.close()
        print(
            "PASS: statistiche, confronto incompleto, ordine osservazioni, nuovi fermi, streak, ripristino, invii reali demo, accordion tastiera e layout 375–1440 px."
        )


if __name__ == "__main__":
    main()
