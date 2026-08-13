import time
from pathlib import Path
from playwright.sync_api import sync_playwright

WAKE_TEXT = "get this app back up"


def find_wake_button(page):
    for frame in page.frames:
        try:
            btn = frame.get_by_role("button").filter(has_text=WAKE_TEXT)
            if btn.count() > 0:
                return btn.first
            btn = frame.get_by_text(WAKE_TEXT, exact=False)
            if btn.count() > 0:
                return btn.first
        except Exception:
            continue
    return None


def visit(page, url):
    page.goto(url, timeout=90000, wait_until="domcontentloaded")
    time.sleep(10)  # let the websocket connect so it counts as real traffic
    btn = find_wake_button(page)
    if btn:
        btn.click()
        print(f"[WOKE UP] {url} was asleep, clicked the wake button")
        time.sleep(45)  # give it time to boot
    else:
        print(f"[OK] {url} is awake, timer reset")


def main():
    urls = [u.strip() for u in Path("apps.txt").read_text().splitlines()
            if u.strip() and not u.strip().startswith("#")]
    print(f"Checking {len(urls)} apps...")
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for url in urls:
            try:
                visit(page, url)
            except Exception as e:
                failures.append(url)
                print(f"[ERROR] {url}: {e}")
        browser.close()
    print(f"Done. {len(urls) - len(failures)} ok, {len(failures)} failed.")
    if failures:
        print("Failed apps:")
        for u in failures:
            print(f"  - {u}")


if __name__ == "__main__":
    main()
