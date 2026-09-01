"""Keep every Streamlit app awake, current and future.
Discovers all public repositories of the account, assumes the standard naming
convention repo-name -> https://repo-name.streamlit.app/, health checks each,
and clicks sleeping apps awake with Playwright. New apps are covered
automatically the moment they deploy under a matching name."""
import time
import requests
from playwright.sync_api import sync_playwright

USER = "yinkaadx"
EXTRA_APPS = []        # full app URLs whose repo name does not match the convention
SKIP_REPOS = set()     # repo names to ignore (never apps)
WAKE_WAIT_SECONDS = 150


def all_repo_names():
    names, page = [], 1
    while True:
        r = requests.get(
            f"https://api.github.com/users/{USER}/repos",
            params={"per_page": 100, "page": page, "type": "owner"},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        names += [x["name"] for x in batch]
        if len(batch) < 100:
            break
        page += 1
    return [n for n in names if n not in SKIP_REPOS]


def is_healthy(url):
    try:
        r = requests.get(url.rstrip("/") + "/_stcore/health", timeout=15)
        return r.ok and r.text.strip() == "ok"
    except requests.RequestException:
        return False


def looks_like_app(url):
    try:
        r = requests.get(url, timeout=20)
        return r.status_code < 400
    except requests.RequestException:
        return False


def try_wake(pw_page, url):
    try:
        pw_page.goto(url, wait_until="domcontentloaded", timeout=60000)
        pw_page.wait_for_timeout(5000)
        for selector in [
            "text=Yes, get this app back up",
            "text=get this app back up",
            "button:has-text('back up')",
        ]:
            try:
                pw_page.click(selector, timeout=4000)
                break
            except Exception:
                continue
        deadline = time.time() + WAKE_WAIT_SECONDS
        while time.time() < deadline:
            if is_healthy(url):
                return True
            time.sleep(10)
        return is_healthy(url)
    except Exception:
        return False


def main():
    names = all_repo_names()
    urls = sorted({f"https://{n}.streamlit.app/" for n in names} | set(EXTRA_APPS))
    print(f"discovered {len(names)} repos, probing {len(urls)} candidate apps")
    awake, woke, failed, not_app = [], [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pw_page = browser.new_page()
        for url in urls:
            if is_healthy(url):
                awake.append(url)
                print(f"AWAKE   {url}")
                continue
            if not looks_like_app(url):
                not_app.append(url)
                print(f"SKIP    {url} (no app deployed under this name)")
                continue
            print(f"WAKING  {url}")
            if try_wake(pw_page, url):
                woke.append(url)
                print(f"WOKE    {url}")
            else:
                failed.append(url)
                print(f"FAILED  {url}")
        browser.close()
    print("\nsummary")
    print(f"  already awake : {len(awake)}")
    print(f"  woken now     : {len(woke)}")
    print(f"  not an app    : {len(not_app)}")
    print(f"  failed        : {len(failed)}")
    for u in failed:
        print(f"  FAILED {u}")


if __name__ == "__main__":
    main()
