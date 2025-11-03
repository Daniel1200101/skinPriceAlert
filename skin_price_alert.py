import os, re, time, subprocess
import requests
from playwright.sync_api import sync_playwright, TimeoutError
from email_alert import send_email_alert
from voice_alert import VoiceAlert

# --- choose ONE of these imports ---

# ✅ Preferred (folder name: watchlist)
from watchlist.items_list import ITEMS

# ❗ If your folder is literally named "list", use this instead and DELETE the line above:
# from list.items_list import ITEMS   # works, but avoid "import list" anywhere else

# ========= BROWSER CONFIG =========
CDP_ENDPOINT   = "http://127.0.0.1:9222"
CHROME_PATH    = os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")
USER_DATA_DIR  = r"C:\Temp\ChromeRemote"

CHECK_EVERY_SEC        = 15        # wait between full cycles over all items
SLEEP_BETWEEN_ITEMS_MS = 400       # small pause between items (keeps UI responsive)

PRICE_SELECTORS = [
    "div.min-price-value",
    "div.skin-min-price .min-price-value",
    "div.skin-min-price",
]
# ==================================

def parse_price_text(raw: str) -> float | None:
    if not raw:
        return None
    m = re.search(r"(?P<cur>[$€₪£])?\s*(?P<num>\d[\d,]*\.?\d*)\s*(?P<cur2>[$€₪£])?", raw.strip())
    if not m:
        return None
    num = (m.group("num") or "").replace(",", "")
    try:
        return float(num)
    except ValueError:
        return None

def condition_met(price: float, target: float, cmp_op: str) -> bool:
    return (cmp_op == "<=" and price <= target) or (cmp_op == ">=" and price >= target)

def cdp_up(endpoint: str) -> bool:
    try:
        r = requests.get(endpoint + "/json/version", timeout=1.0)
        return r.ok
    except Exception:
        return False

def ensure_chrome_with_cdp():
    if cdp_up(CDP_ENDPOINT):
        return
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(CHROME_PATH):
        raise FileNotFoundError(f"Chrome not found at: {CHROME_PATH}")
    port = CDP_ENDPOINT.split(":")[-1]
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--start-maximized",
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if cdp_up(CDP_ENDPOINT):
            return
        time.sleep(0.25)
    raise RuntimeError(f"DevTools endpoint not reachable at {CDP_ENDPOINT}")

def get_or_open_page(ctx, url: str):
    base = url.split("?")[0]
    for pg in ctx.pages:
        if base in (pg.url or ""):
            return pg
    pg = ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    return pg

def read_min_price(page) -> tuple[float | None, str | None]:
    raw = None
    for sel in PRICE_SELECTORS:
        try:
            el = page.wait_for_selector(sel, timeout=8000)
            txt = el.inner_text().strip()
            if txt:
                raw = txt
                break
        except TimeoutError:
            continue
    if raw is None:
        return None, None
    return parse_price_text(raw), raw

def main():
    if not ITEMS:
        raise RuntimeError("No ITEMS loaded. Put your knives in watchlist/items_list.py (ITEMS = [...]).")

    ensure_chrome_with_cdp()
    voice = VoiceAlert()

    with sync_playwright() as p:
        print("🔗 Connecting to Chrome on", CDP_ENDPOINT)
        browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        # Keep one tab per URL and reuse
        pages = { it["url"]: get_or_open_page(ctx, it["url"]) for it in ITEMS }

        print("🗡️ Tracking items:")
        for it in ITEMS:
            print(f"   • {it['name']}  |  target {it['compare']} {it['target']:.2f}")
        print(f"\n🔁 Full cycle every {CHECK_EVERY_SEC}s.\n")

        while True:
            try:
                hits = []  # collect all items under/over target this cycle

                for it in ITEMS:
                    page = pages[it["url"]]
                    page.reload(wait_until="domcontentloaded", timeout=60000)

                    price_val, raw = read_min_price(page)
                    now = time.strftime("%H:%M:%S")

                    if price_val is None:
                        print(f"[{now}] ⚠️  {it['name']}: couldn't read price (verify/selector). URL: {page.url}")
                    else:
                        print(f"[{now}] {it['name']}: {price_val:.2f}  (target {it['compare']} {it['target']:.2f})")
                        if condition_met(price_val, it["target"], it["compare"]):
                            dir_word = "under" if it["compare"] == "<=" else "above"
                            msg = f"{it['name']}: {price_val:.2f} "
                            # Optional: keep voice per-item
                            voice.alert(msg)
                            # Add to batch for one combined email
                            hits.append({
                                "name": it["name"],
                                "price": price_val,
                                "target": it["target"],
                                "compare": it["compare"],
                                "url": it["url"],
                            })

                    time.sleep(SLEEP_BETWEEN_ITEMS_MS / 1000)

                # === Send ONE email if we had 2+ hits (or >=1 if you prefer) ===
                if len(hits) >= 2:  # change to >=1 if you want email even for a single hit
                    subject_count = len(hits)
                    body_lines = [
                        f"{h['name']} — {h['price']:.2f} (target {h['compare']} {h['target']:.2f})\n{h['url']}"
                        for h in hits
                    ]
                    body = (
                            f"{subject_count} items hit your target:\n\n" +
                            "\n\n".join(body_lines) +
                            f"\n\nTime: {time.ctime()}"
                    )
                    # Use a batch key so cooldown is for the whole batch email
                    send_email_alert(body, key="batch")

                time.sleep(CHECK_EVERY_SEC)

            except KeyboardInterrupt:
                print("\n👋 Stopped by user.")
                break
            except Exception as e:
                print("⚠️ Loop error:", e)
                time.sleep(2)


if __name__ == "__main__":
    main()
