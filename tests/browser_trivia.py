"""End-to-end Commonplace checks. Run: uv run --with playwright python tests/browser_trivia.py"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="commonplace-test-") as temp:
        env = dict(os.environ, LEARNGEO_DATA_DIR=temp)
        with open(Path(temp) / "server.log", "w") as log:
            server = subprocess.Popen([str(ROOT / ".venv/Scripts/python.exe"), "-c",
                "from app import app; app.run(host='127.0.0.1',port=5093,debug=False)"],
                cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                for _ in range(80):
                    if server.poll() is not None:
                        raise RuntimeError(Path(temp, "server.log").read_text())
                    try:
                        urllib.request.urlopen("http://127.0.0.1:5093/trivia/", timeout=1)
                        break
                    except OSError:
                        time.sleep(.2)
                with sync_playwright() as p:
                    browser = p.chromium.launch(channel="msedge", headless=True)
                    page = browser.new_page(viewport={"width":1440,"height":1080})
                    errors = []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.goto("http://127.0.0.1:5093/")
                    page.wait_for_selector(".topic-card")
                    assert page.locator(".topic-card").count() == 12
                    bank = page.request.get("http://127.0.0.1:5093/trivia/bank").json()["cards"]
                    card_index = {c["id"]: c for c in bank}
                    # Pure core checks: exact numeric answers, accents, repeat scheduling and input validation.
                    core = page.evaluate("""() => {
                      const C=TriviaCore, now=100000000;
                      const p=C.review(null,false,'again',now), good=C.review(p,true,'good',now);
                      const card={answer:'René Descartes',aliases:['Descartes']};
                      let rejected=false;try{C.validateBackup({version:1,progress:{x:{seen:1,correct:2}},custom:[],benchmarks:[]})}catch{rejected=true}
                      return {accent:C.judge('Rene Descartes',card),alias:C.judge('Descartes',card),wrong:!C.judge('Descart',card),
                        decimal:!C.judge('42195',{answer:'42.195',aliases:[]}),
                        sign:!C.judge('1',{answer:'-1',aliases:[]}),
                        balanced:new Set(C.queue(Array.from({length:120},(_,i)=>({id:String(i),topic:i<110?'large':'small',level:1})),{},{mode:'challenge'}).slice(0,2).map(id=>Number(id)<110?'large':'small')).size===2,
                        repeat:p.due===now+600000,good:good.due===now+86400000,rejected,
                        unsafe:C.safeURL('javascript:alert(1)')===''};
                    }""")
                    assert all(core.values()), core
                    ROOT.joinpath("docs").mkdir(exist_ok=True)
                    page.screenshot(path=str(ROOT / "docs/commonplace-desktop.png"), full_page=True)
                    page.locator('[data-start="study"]').click()
                    page.wait_for_selector("#answer")
                    first_id = page.evaluate("JSON.parse(sessionStorage.getItem('commonplace.session.v1')).queue[0]")
                    first_card = card_index[first_id]
                    page.locator("#answer").fill(first_card["aliases"][0] if first_card["aliases"] else first_card["answer"])
                    page.locator("#answer").press("Enter")
                    assert "You found it" in page.locator("#feedback").text_content(), page.locator("#feedback").text_content()
                    page.reload()
                    page.wait_for_selector("#feedback:not([hidden])")
                    page.locator('[data-rate="good"]').click()
                    record = page.evaluate(f"JSON.parse(localStorage.getItem('commonplace.v1')).progress[{json.dumps(first_id)}]")
                    assert record["seen"] == 1 and record["correct"] == 1
                    # A hint followed by a correct answer must not be counted as unaided recall.
                    second_id = page.evaluate("JSON.parse(sessionStorage.getItem('commonplace.session.v1')).queue[1]")
                    second = card_index[second_id]
                    page.locator('[data-action="hint"]').click()
                    page.locator("#answer").fill(second["aliases"][0] if second["aliases"] else second["answer"])
                    page.locator("#answer").press("Enter")
                    assert "with a hint" in page.locator("#feedback").text_content()
                    page.locator('[data-rate="again"]').click()
                    assert page.evaluate(f"JSON.parse(localStorage.getItem('commonplace.v1')).progress[{json.dumps(second_id)}].correct") == 0
                    page.locator('[data-action="finish"]').click()
                    page.get_by_role("button",name="Back to the desk").click()
                    page.locator('[data-start="challenge"]').click()
                    page.wait_for_selector("#session-clock")
                    page.evaluate("let s=JSON.parse(sessionStorage.getItem('commonplace.session.v1'));s.deadline=Date.now()-1;sessionStorage.setItem('commonplace.session.v1',JSON.stringify(s))")
                    page.reload()
                    page.wait_for_selector(".summary")
                    assert "TIME'S UP" in page.locator("#view").inner_text()
                    assert "0" in page.locator(".big-score").inner_text()
                    # Personal cards, safe rendering, persistence and actual practice.
                    page.locator('[data-view="notebook"]').click()
                    page.locator('[name="prompt"]').fill("Test: <script>alert(1)</script> is displayed as text?")
                    page.locator('[name="answer"]').fill("Yes")
                    page.locator('[name="explanation"]').fill("A personal test card.")
                    page.get_by_role("button",name="Add to my practice").click()
                    assert "Added to your notebook" in page.locator("#message").inner_text()
                    assert page.locator("#view script").count() == 0
                    page.locator('[data-view="library"]').click()
                    page.locator("#library-search").fill("displayed as text")
                    assert page.locator(".library-card").count() == 1
                    page.get_by_role("button",name="Open study card").click()
                    page.get_by_role("button",name="Save to notebook").click()
                    page.get_by_role("button",name="Close",exact=True).click()
                    page.locator('[data-view="benchmarks"]').click()
                    page.locator('[name="quiz"]').fill("1")
                    page.locator('[name="score"]').fill("7")
                    page.get_by_role("button",name="Save result").click()
                    assert "7/20" in page.locator(".attempt").inner_text()
                    # Export is a valid restorable backup, not just a download button.
                    page.locator('[data-view="progress"]').click()
                    with page.expect_download() as downloaded:
                        page.get_by_role("button",name="Download backup").click()
                    backup = Path(temp) / "backup.json"
                    downloaded.value.save_as(backup)
                    saved = json.loads(backup.read_text())
                    assert len(saved["custom"]) == 1 and saved["benchmarks"][0]["score"] == 7
                    page.on("dialog",lambda dialog: dialog.accept())
                    page.locator("#backup-file").set_input_files(backup)
                    page.wait_for_function("document.querySelector('#message').textContent.includes('Backup restored')")
                    # Actual graph, exploration links, trail and a study session from an entity.
                    page.locator('[data-view="explore"]').click()
                    page.wait_for_selector("#entity-search")
                    graph = page.request.get("http://127.0.0.1:5093/trivia/graph").json()["entities"]
                    if graph:
                        page.locator(".entity-tile").first.click()
                        page.wait_for_selector(".breadcrumbs")
                        page.locator(".connection-tile .entity-tile").first.click()
                        assert page.locator(".breadcrumbs [data-entity]").count() >= 2
                        page.reload()
                        page.wait_for_selector(".breadcrumbs")
                        assert page.locator(".breadcrumbs [data-entity]").count() >= 2
                        page.screenshot(path=str(ROOT / "docs/commonplace-rabbit-hole.png"), full_page=True)
                        page.get_by_role("button",name="Practise this trail").click()
                        page.wait_for_selector("#answer")
                    # Narrow-screen home, exploration and session must stay within the viewport.
                    page.set_viewport_size({"width":390,"height":844})
                    page.locator('[data-view="home"]').click()
                    page.wait_for_selector(".topic-card")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
                    page.screenshot(path=str(ROOT / "docs/commonplace-mobile.png"), full_page=True)
                    page.locator('[data-start="study"]').click()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Session mobile overflow"
                    assert not errors, errors
                    browser.close()
                    print(f"PASS: browser flows, learning rules, persistence, backups, mobile; {len(bank)} cards, {len(graph)} entities")
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
