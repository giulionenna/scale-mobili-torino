"""Collaudo landing e home aperte, statistiche riservate e accesso demo.

Richiede il server statico della demo su 127.0.0.1:5321.
Le sessioni Chromium contengono soltanto dati sintetici.
"""

import shutil

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"), headless=True, args=["--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, locale="it-IT")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:5321/", wait_until="networkidle")
        expect(page.locator(".landing-availability .availability-value")).to_have_text("67%")
        expect(page.get_by_role("dialog")).to_have_count(0)
        page.locator(".availability-toggle").click()
        expect(page.locator("#landing-availability-details")).to_be_visible()
        expect(page.locator(".availability-breakdown")).to_have_count(0)
        page.locator(".availability-toggle").click()
        page.screenshot(path="/tmp/torino-landing-public.png", full_page=True)
        page.get_by_role("button", name="Esplora la panoramica").click()
        assert page.url.endswith("/home/")

        def locked():
            expect(page.locator(".availability-value")).to_have_text("67%")
            expect(page.get_by_role("dialog")).to_have_count(0)
            expect(page.locator(".locked-statistic")).to_have_count(3)
            expect(page.locator(".alignment-number")).to_have_count(0)
            expect(page.locator(".incident-row")).to_have_count(0)
            expect(page.locator(".comparison-list")).to_have_count(0)
            expect(page.locator(".availability-mini")).to_have_count(0)
            expect(page.locator(".availability-breakdown")).to_have_count(0)
            expect(page.get_by_role("heading", name="Le stazioni", exact=True)).to_be_visible()
            expect(page.get_by_role("heading", name="Le ultime segnalazioni", exact=True)).to_be_visible()
            for preview in page.locator(".locked-preview").all():
                expect(preview).to_have_attribute("aria-hidden", "true")
                expect(preview).to_have_attribute("inert", "")
                assert preview.evaluate("el => getComputedStyle(el).filter") == "blur(7px)"

        locked()
        page.reload(wait_until="networkidle")
        locked()
        page.locator(".availability-toggle").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#availability-details")).to_be_visible()
        expect(page.locator(".availability-stations > div")).to_have_count(4)
        expect(page.locator(".availability-breakdown")).to_have_count(0)
        page.locator(".availability-toggle").click()
        page.locator(".search-box input").fill("Vinzaglio")
        expect(page.locator(".station-card")).to_have_count(1)
        page.locator(".search-box input").fill("")
        page.locator(".device-row").first.click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.keyboard.press("Escape")
        # Both contribution paths require login; cancelling leaves the public home.
        for name in ["Invia una segnalazione", "Proponi un impianto"]:
            page.get_by_role("button", name=name, exact=True).first.click()
            expect(page.get_by_role("dialog")).to_be_visible()
            expect(page.locator("#station")).to_have_count(0)
            page.keyboard.press("Escape")
            locked()
        for route in ["segnala", "proponi", "moderazione"]:
            page.goto(f"http://127.0.0.1:5321/{route}/", wait_until="networkidle")
            expect(page.get_by_role("dialog")).to_be_visible()
            expect(page.locator("#station")).to_have_count(0)
            expect(page.get_by_role("button", name="Approva impianto", exact=True)).to_have_count(0)
            page.keyboard.press("Escape")
            assert page.url.endswith("/home/")
            locked()
        page.screenshot(path="/tmp/torino-home-public.png", full_page=True)
        # Unlock in place, preserving scroll and current filters.
        page.locator(".search-box input").fill("Re Umberto")
        page.locator(".locked-incidents").get_by_role("button", name="Accedi e sblocca").click()
        before = page.evaluate("window.scrollY")
        page.get_by_role("button", name="Continua come cittadino").click()
        expect(page.locator(".locked-statistic")).to_have_count(0)
        expect(page.locator(".alignment-number > strong")).to_have_text("0%")
        expect(page.locator(".incident-row")).to_have_count(2)
        expect(page.locator(".comparison-list article")).to_have_count(3)
        expect(page.locator(".search-box input")).to_have_value("Re Umberto")
        assert abs(page.evaluate("window.scrollY") - before) < 2
        page.reload(wait_until="networkidle")
        expect(page.locator(".locked-statistic")).to_have_count(0)
        # An existing private proposal must remain hidden after sign-out.
        page.evaluate("""() => {
          const d=JSON.parse(sessionStorage.getItem('smt.platform-demo.v2'));
          const member=JSON.parse(sessionStorage.getItem('smt.platform-member.v2'));
          d.proposals.push({id:'qa-private-proposal',station_id:'demo-re-umberto',kind:'ascensore',name:'Proposta privata QA',location:'Esempio',description:'',actor_id:member.id,created_at:new Date().toISOString(),status:'pending'});
          sessionStorage.setItem('smt.platform-demo.v2',JSON.stringify(d));
        }""")
        page.reload(wait_until="networkidle")
        expect(page.locator(".my-proposals")).to_contain_text("Proposta privata QA")
        page.get_by_role("button", name="Esci", exact=True).click()
        locked()
        expect(page.locator(".my-proposals")).to_have_count(0)
        page.reload(wait_until="networkidle")
        locked()
        # All public routes remain readable without horizontal overflow.
        for route in ["", "home/"]:
            page.goto(f"http://127.0.0.1:5321/{route}", wait_until="networkidle")
            for width in [375, 768, 950, 1440]:
                page.set_viewport_size({"width": width, "height": 1100})
                page.locator(".availability-toggle").click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (route, width)
                page.locator(".availability-toggle").click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (route, width)
            page.set_viewport_size({"width": 375, "height": 1100})
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=f"/tmp/torino-{'landing' if not route else 'home'}-public-mobile.png", full_page=True)
        assert not errors, errors
        browser.close()
        print("PASS: landing, home anonima, blur con dati non renderizzati, accesso e sblocco nella stessa pagina, logout, proposte private e layout 375–1440 px.")


if __name__ == "__main__":
    main()
