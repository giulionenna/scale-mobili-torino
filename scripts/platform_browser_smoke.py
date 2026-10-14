"""Collaudo della demo landing/home/segnalazione/proposta/moderazione.

Esegue solo azioni sintetiche nella sessione di Chromium, senza AWS.
Avviare prima il server statico della demo sulla porta 5321.
"""

import base64
import shutil

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}, locale="it-IT"
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:5321/segnala/", wait_until="networkidle")
        expect(page.get_by_role("dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).not_to_be_visible()
        page.get_by_role("button", name="Accedi", exact=True).click()
        page.get_by_role("button", name="Continua come cittadino").click()
        page.get_by_role("button", name="Invia una segnalazione", exact=True).click()
        expect(page.locator("#station")).to_be_visible()
        page.get_by_role("button", name="Invia segnalazione", exact=True).click()
        assert page.locator("#station").evaluate("el => !el.checkValidity()")
        page.locator("#station").select_option("demo-porta-nuova")
        page.locator("#device").select_option("demo-device-0-lift")
        page.get_by_label("Funzionante", exact=True).check()
        page.locator("#description").fill(
            "Segnalazione sintetica per il collaudo del nuovo modulo."
        )
        image = page.evaluate("""() => {
            const canvas=document.createElement('canvas');canvas.width=64;canvas.height=64;
            const context=canvas.getContext('2d');context.fillStyle='#E8C66B';
            context.fillRect(0,0,64,64);return canvas.toDataURL('image/png').split(',')[1];
        }""")
        file = {
            "name": "photo-test.png",
            "mimeType": "image/png",
            "buffer": base64.b64decode(image),
        }
        page.locator("#photo").set_input_files(
            {"name": "fake.png", "mimeType": "image/png", "buffer": b"not-an-image"}
        )
        expect(page.get_by_role("alert")).to_contain_text("fotografia valida")
        page.locator("#photo").set_input_files(file)
        expect(page.get_by_text("Foto aggiunta", exact=True)).to_be_visible()
        page.screenshot(path="/tmp/torino-report-v2.png", full_page=True)
        page.get_by_role("button", name="Invia segnalazione", exact=True).click()
        expect(
            page.get_by_role("heading", name="Le ultime segnalazioni")
        ).to_be_visible()
        expect(page.locator(".feed-panel")).to_contain_text(
            "Segnalazione sintetica per il collaudo"
        )
        expect(page.locator(".feed-photo")).to_have_count(0)
        assert page.evaluate(
            "JSON.parse(sessionStorage.getItem('smt.platform-demo.v2')).reports.at(-1).photo.data.startsWith('data:image/jpeg')"
        )
        page.get_by_role("button", name="Proponi un impianto", exact=True).first.click()
        page.locator("#station").select_option("demo-re-umberto")
        page.locator("#kind").select_option("ascensore")
        page.locator("#proposal-name").fill("Ascensore test lato est")
        page.locator("#location").fill(
            "Posizione sintetica: ingresso est, strada verso mezzanino."
        )
        page.locator("#photo").set_input_files(file)
        expect(page.get_by_text("Foto aggiunta", exact=True)).to_be_visible()
        page.get_by_role("button", name="Invia proposta", exact=True).click()
        expect(page.locator(".my-proposals")).to_contain_text(
            "In attesa di approvazione"
        )
        expect(page.locator(".station-grid")).not_to_contain_text(
            "Ascensore test lato est"
        )
        page.goto("http://127.0.0.1:5321/moderazione/", wait_until="networkidle")
        expect(page.get_by_role("alert")).to_contain_text("riservata al moderatore")
        expect(
            page.get_by_role("button", name="Approva impianto", exact=True)
        ).to_have_count(0)
        page.get_by_role("button", name="Esci", exact=True).click()
        page.get_by_role("button", name="Accedi", exact=True).click()
        page.get_by_role("button", name="Prova la modalità moderatore").click()
        page.locator(".app-nav").get_by_role("button", name="Moderazione").click()
        expect(
            page.get_by_role("heading", name="Ascensore test lato est")
        ).to_be_visible()
        page.get_by_role("button", name="Approva impianto", exact=True).click()
        expect(
            page.get_by_role("heading", name="Tutte le proposte sono state esaminate")
        ).to_be_visible()
        page.get_by_role("button", name="Foto in revisione").click()
        expect(
            page.get_by_role("button", name="Approva foto", exact=True)
        ).to_have_count(2)
        page.get_by_role("button", name="Approva foto", exact=True).first.click()
        page.get_by_role("button", name="Approva foto", exact=True).click()
        page.locator(".app-nav").get_by_role(
            "button", name="Panoramica", exact=True
        ).click()
        expect(page.locator(".station-grid")).to_contain_text("Ascensore test lato est")
        expect(page.locator(".feed-photo")).to_have_count(1)
        page.reload(wait_until="networkidle")
        expect(page.locator(".station-grid")).to_contain_text("Ascensore test lato est")
        page.get_by_role("button", name="Proponi un impianto", exact=True).first.click()
        page.locator("#station").select_option("demo-vinzaglio")
        page.locator("#kind").select_option("scala_mobile")
        page.locator("#proposal-name").fill("Scala test da respingere")
        page.locator("#location").fill("Posizione sintetica duplicata da verificare.")
        page.get_by_role("button", name="Invia proposta", exact=True).click()
        page.locator(".app-nav").get_by_role("button", name="Moderazione").click()
        page.get_by_role("button", name="Respingi proposta").click()
        page.get_by_role("button", name="Decisioni precedenti").click()
        expect(page.locator(".decision-history")).to_contain_text("Proposta respinta")
        page.screenshot(path="/tmp/torino-moderation-v2.png", full_page=True)
        page.locator(".app-nav").get_by_role(
            "button", name="Panoramica", exact=True
        ).click()
        expect(page.locator(".station-grid")).not_to_contain_text(
            "Scala test da respingere"
        )
        page.get_by_role("textbox", name="Cerca una stazione").fill("nome inesistente")
        expect(
            page.get_by_role("heading", name="Nessuna stazione trovata")
        ).to_be_visible()
        page.get_by_role("textbox", name="Cerca una stazione").fill("")
        page.screenshot(path="/tmp/torino-home-v2.png", full_page=True)
        for width in (375, 768, 950):
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), width
        page.set_viewport_size({"width": 375, "height": 812})
        page.screenshot(path="/tmp/torino-mobile-v2.png", full_page=True)
        page.get_by_role("button", name="Esci", exact=True).click()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        assert not errors, errors
        browser.close()
        print(
            "Demo verificata: accesso, campi obbligatori, foto, stream, proposta pendente, approvazione/rifiuto, moderazione foto, ruoli e mobile."
        )


if __name__ == "__main__":
    main()
