"""Run with a Python environment containing Playwright and installed Chromium."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='learngeo-browser-') as tmp:
        env = dict(os.environ, LEARNGEO_DATA_DIR=tmp)
        with open(Path(tmp) / 'server.log', 'w') as log:
            server = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe'), '-c',
                "from app import app; from werkzeug.serving import make_server; "
                "from threading import Thread; "
                "s=make_server('127.0.0.1',5087,app,threaded=True); "
                "Thread(target=s.serve_forever,daemon=True).start(); "
                "input(); s.shutdown(); s.server_close()"], cwd=ROOT,
                env=env, stdout=log, stderr=log, stdin=subprocess.PIPE, text=True)
            try:
                for _ in range(60):
                    if server.poll() is not None:
                        raise RuntimeError('Browser test server failed to start')
                    try:
                        urllib.request.urlopen('http://127.0.0.1:5087/games', timeout=1)
                        break
                    except OSError:
                        time.sleep(.2)
                with sync_playwright() as p:
                    browser = p.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 390, 'height': 844})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto('http://127.0.0.1:5087/games')
                    assert page.locator('form[action="/play/map"] [name="challenge"]').count() == 0
                    form = page.locator('form[action="/play/capitals"]')
                    form.locator('[name="endless"]').select_option('1')
                    assert not form.locator('.question-limit').is_visible()
                    form.locator('[name="endless"]').select_option('0')
                    form.locator('[name="length"]').select_option('5')
                    form.locator('button').click()
                    page.wait_for_selector('.choice')
                    assert page.evaluate('window.LEARNGEO.length') == 5
                    page.goto('http://127.0.0.1:5087/country/NL')
                    page.locator('#people-name .section-practice').click()
                    page.wait_for_selector('.choice')
                    assert 'demonyms' in page.url
                    assert 'Netherlands' in page.locator('#prompt').inner_text()
                    page.goto('http://127.0.0.1:5087/play/demonyms?country=GB&challenge=1&endless=1')
                    page.wait_for_selector('input[type="text"]')
                    entry = page.locator('input[type="text"]').last
                    entry.fill('Britons')
                    entry.press('Enter')
                    page.wait_for_selector('.answerbar')
                    assert 'Correct' in page.locator('.answerbar').inner_text()
                    assert page.locator('.answerbar a.lesson-source').count() == 2
                    explanation = page.locator('.answerbar .note').inner_text()
                    page.reload()
                    page.wait_for_selector('.answerbar')
                    assert page.locator('.answerbar .note').inner_text() == explanation
                    page.goto('http://127.0.0.1:5087/play/beliefs?country=IN&endless=1')
                    page.wait_for_selector('.choice')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.locator('.choice').first.click()
                    page.wait_for_selector('.answerbar a.lesson-source')
                    page.goto('http://127.0.0.1:5087/play/historical_flags?country=IR&endless=1')
                    page.wait_for_selector('#media img')
                    page.locator('#media img').evaluate('(img) => img.decode()')
                    assert 'reconstruction' in page.locator('#prompt').inner_text()
                    page.goto('http://127.0.0.1:5087/play/capitals?length=5')
                    page.wait_for_selector('.choice')
                    old_url = page.url
                    page.reload()
                    page.wait_for_selector('.choice')
                    assert page.url == old_url
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.locator('[data-act="restart"]').click()
                    page.wait_for_url(lambda url: str(url) != old_url)
                    page.wait_for_selector('.choice')
                    assert page.evaluate('window.LEARNGEO.length') == 5
                    for iso in ['IR', 'CN', 'IN', 'TV']:
                        page.goto('http://127.0.0.1:5087/country/' + iso)
                        page.locator('#civilizations').scroll_into_view_if_needed()
                        for image in page.locator('.historical-flag').all():
                            image.scroll_into_view_if_needed()
                            image.evaluate('(img) => img.decode()')
                            assert image.evaluate('(img) => img.naturalWidth > 0')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), iso
                        card = page.locator('details.study-card').first
                        card.locator('summary').click()
                        assert card.get_attribute('open') is not None
                    page.goto('http://127.0.0.1:5087/country/IR')
                    page.locator('#civilizations').evaluate('(el) => el.scrollIntoView({block: "start"})')
                    page.screenshot(path=str(ROOT / 'docs/explore-mobile.png'))
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.locator('#civilizations').evaluate('(el) => el.scrollIntoView({block: "start"})')
                    page.screenshot(path=str(ROOT / 'docs/explore-desktop.png'))
                    assert not errors, errors
                    browser.close()
                    print('PASS: mode controls, section practice, typed demonyms, sourced/restored feedback, historical flag games, length, refresh, restart and mobile layout')
            finally:
                # Exit through stdin so Windows' venv launcher also waits for
                # the actual Python child to release its log and database.
                server.communicate(input='\n', timeout=15)


if __name__ == '__main__':
    main()
