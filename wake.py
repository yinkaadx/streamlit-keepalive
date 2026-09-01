"""Keep every Streamlit app awake, current and future. Hardened version.
Discovers all public repositories of the account (authenticated when a token is
present, so Actions runners never hit anonymous rate limits), unions them with a
bundled fallback list so discovery failure can never blank coverage, health
checks each candidate, and clicks sleeping apps awake with Playwright. The
script always exits 0: problems are reported in the log summary, never as a red
run that stops the schedule."""
import os
import sys
import time
import traceback

import requests
from playwright.sync_api import sync_playwright

USER = "yinkaadx"
WAKE_WAIT_SECONDS = 120
EXTRA_APPS = []        # full app URLs whose repo name does not match the convention
SKIP_REPOS = set()     # repo names to ignore

FALLBACK_APPS = [
    "https://6g-agri-food-safety-engine.streamlit.app/",
    "https://agri-digitalization-engine.streamlit.app/",
    "https://agri-environmental-mitigation-engine.streamlit.app/",
    "https://agri-systems-dynamics-engine.streamlit.app/",
    "https://ai-public-procurement-engine.streamlit.app/",
    "https://climate-equity-valuation-engine.streamlit.app/",
    "https://climate-finance-engine.streamlit.app/",
    "https://clinical-decision-engine.streamlit.app/",
    "https://commodity-finance-engine.streamlit.app/",
    "https://concept-drift-engine.streamlit.app/",
    "https://corporate-carbon-accounting-engine.streamlit.app/",
    "https://crypto-contagion-engine.streamlit.app/",
    "https://decision-reward-schemes-pilot.streamlit.app/",
    "https://digital-inclusion-engine.streamlit.app/",
    "https://disaster-economics-engine.streamlit.app/",
    "https://disaster-ehealth-twin-engine.streamlit.app/",
    "https://disaster-iot-engine.streamlit.app/",
    "https://econ-mirror-pro.streamlit.app/",
    "https://empirical-asset-pricing-engine.streamlit.app/",
    "https://esg-cognition-engine.streamlit.app/",
    "https://financial-engineering-pricing-engine.streamlit.app/",
    "https://fintech-fraud-detection-engine.streamlit.app/",
    "https://food-safety-culture-ai.streamlit.app/",
    "https://forestry-genetics-engine.streamlit.app/",
    "https://green-iot-supply-chain.streamlit.app/",
    "https://hybrid-eew-network-engine.streamlit.app/",
    "https://hydrological-forecasting-engine.streamlit.app/",
    "https://hyperspectral-uav-engine.streamlit.app/",
    "https://indicators-dashboard.streamlit.app/",
    "https://llm-security-engine.streamlit.app/",
    "https://precision-aquaculture-engine.streamlit.app/",
    "https://precision-aviation-engine.streamlit.app/",
    "https://rural-ecommerce-econometrics.streamlit.app/",
    "https://serverless-automl-stream.streamlit.app/",
    "https://shadow-banking-pricing-engine.streamlit.app/",
    "https://stablecoin-anomaly-engine.streamlit.app/",
    "https://supply-chain-resilience-engine.streamlit.app/",
    "https://telecom-blockchain-governance.streamlit.app/",
    "https://time-series-stream-engine.streamlit.app/",
    "https://uav-agricultural-iot-engine.streamlit.app/",
    "https://water-market-exchange-engine.streamlit.app/",
    "https://wsan-smart-farming-engine.streamlit.app/",
    "https://wsu-spatiotemporal-engine.streamlit.app/",
]

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def all_repo_names():
    try:
        names, page = [], 1
        while True:
            r = requests.get(
                f"https://api.github.com/users/{USER}/repos",
                params={"per_page": 100, "page": page, "type": "owner"},
                headers=HEADERS,
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
    except Exception:
        print("repo discovery failed, continuing with fallback list only")
        traceback.print_exc()
        return []


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


def main():
    discovered = all_repo_names()
    urls = sorted(
        {f"https://{n}.streamlit.app/" for n in discovered}
        | set(FALLBACK_APPS)
        | set(EXTRA_APPS)
    )
    print(f"discovered {len(discovered)} repos, probing {len(urls)} candidate apps")
    awake, woke, failed, not_app = [], [], [], []
    with sync_playwright() as p:
        browser, pw_page = None, None
        for url in urls:
            try:
                if is_healthy(url):
                    awake.append(url)
                    print(f"AWAKE   {url}")
                    continue
                if not looks_like_app(url):
                    not_app.append(url)
                    print(f"SKIP    {url}")
                    continue
                if pw_page is None:
                    browser = p.chromium.launch()
                    pw_page = browser.new_page()
                print(f"WAKING  {url}")
                if try_wake(pw_page, url):
                    woke.append(url)
                    print(f"WOKE    {url}")
                else:
                    failed.append(url)
                    print(f"FAILED  {url}")
            except Exception:
                print(f"ERROR   {url}, recreating browser and continuing")
                traceback.print_exc()
                failed.append(url)
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass
                browser, pw_page = None, None
        try:
            if browser:
                browser.close()
        except Exception:
            pass
    print("\nsummary")
    print(f"  already awake : {len(awake)}")
    print(f"  woken now     : {len(woke)}")
    print(f"  not an app    : {len(not_app)}")
    print(f"  failed        : {len(failed)}")
    for u in failed:
        print(f"  FAILED {u}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("SCRIPT ERROR, see traceback; exiting clean so the schedule keeps running")
        traceback.print_exc()
    sys.exit(0)
