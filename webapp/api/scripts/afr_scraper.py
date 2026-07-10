import os
import re
import sys
import time
import json
import sqlite3
import urllib.parse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    from playwright_stealth import Stealth
except ImportError as e:
    print(f"ImportError: {e}")
    print("Please install playwright and stealth: pip install playwright playwright-stealth && playwright install chromium")
    sys.exit(1)

try:
    from anthropic import Anthropic
except ImportError:
    print("Please install anthropic: pip install anthropic")
    sys.exit(1)

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", HERE.parent)))

# Resolve the canonical DB — always prefer unified_companies.db which has the full ERD
# (infringements, metrics, contacts, company_news). Fall back to railway_db.sqlite only
# if unified_companies.db is genuinely absent.
_candidates = [
    DATA_DIR / "unified_companies.db",
    HERE.parent / "unified_companies.db",
    HERE.parent.parent.parent / "railway_db.sqlite",
]
DB_PATH = next((p for p in _candidates if p.exists()), _candidates[0])

SESSION_FILE = DATA_DIR / "afr_session.json"

# Try to load .env from the project webapp directory
ENV_PATH = HERE.parent.parent / ".env"
if ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)

AFR_EMAIL = os.environ.get("AFR_EMAIL")
AFR_PASSWORD = os.environ.get("AFR_PASSWORD")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not AFR_EMAIL or not AFR_PASSWORD:
    print("Error: AFR_EMAIL and AFR_PASSWORD must be set in the environment.")
    sys.exit(1)

def summarize_article(text: str) -> str:
    """Use Anthropic to summarize the article."""
    if not ANTHROPIC_API_KEY:
        return text[:500] + "..."
    
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            temperature=0.3,
            system="You are a financial analyst. Provide a concise, 2-3 sentence summary of the following news article, focusing on any regulatory, legal, or financial issues.",
            messages=[
                {"role": "user", "content": f"Article text:\n\n{text[:10000]}"}
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Summarization error: {e}")
        return text[:500] + "..."

def login_afr(page):
    """Log into AFR and save session."""
    print("Navigating to AFR homepage...")
    page.goto("https://www.afr.com")
    
    try:
        # Click the "Log in" button on the homepage
        print("Clicking Log in button...")
        page.locator('button:has-text("Log in")').filter(visible=True).first.click()
        
        # Wait for the email field (part of Nine SSO)
        page.wait_for_selector('#loginEmail', timeout=10000)
        page.fill('#loginEmail', AFR_EMAIL)
        
        if page.is_visible('#loginPassword'):
            page.fill('#loginPassword', AFR_PASSWORD)
            page.locator('button[type="submit"]').filter(has_text="Log in").first.click()
        else:
            # Click continue and wait for password field
            page.locator('button[type="submit"]').filter(has_text="Log in").first.click()
            page.wait_for_selector('#loginPassword', timeout=10000)
            page.fill('#loginPassword', AFR_PASSWORD)
            page.locator('button[type="submit"]').filter(has_text="Log in").first.click()
        
        # Wait for successful login (logout button or avatar)
        try:
            page.wait_for_selector('a[href="/logout"]', timeout=15000)
        except PlaywrightTimeoutError:
            print("Could not find standard logout button, checking if login succeeded anyway...")
            
        print("Login completed.")
        
        # Save session
        context = page.context
        context.storage_state(path=str(SESSION_FILE))
        print("Session saved.")
    except PlaywrightTimeoutError:
        print("Timeout during login. The page structure might have changed or a CAPTCHA appeared.")
        page.screenshot(path=str(DATA_DIR / "login_error.png"))
        with open(DATA_DIR / "login_error.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        sys.exit(1)

# Legal suffixes to strip before searching AFR so we search the brand name,
# not the corporate registry name. e.g. "Canva Pty Ltd" -> "Canva"
_LEGAL_SUFFIXES = re.compile(
    r"\s+(pty\.?\s*ltd\.?|pty\.?\s*limited|proprietary\s+limited|limited|ltd\.?|"  
    r"corporation|corp\.?|incorporated|inc\.?|hold\s*co|holdings?)\s*$",
    re.IGNORECASE
)

def _search_name(company_name: str) -> str:
    """Strip legal suffixes and return a clean search term."""
    name = _LEGAL_SUFFIXES.sub("", company_name).strip()
    return name or company_name

def _is_relevant(url: str, title: str, keywords: list[str]) -> bool:
    """Return True only if the article URL slug or headline contains at least
    one meaningful keyword from the company name. Prevents saving generic
    AFR lifestyle/travel articles that have nothing to do with the company."""
    haystack = (url + " " + title).lower()
    return any(kw in haystack for kw in keywords)

def scrape_company_news(page, acn: str, company_name: str, conn: sqlite3.Connection):
    search_term = _search_name(company_name)
    # Build relevance keywords from the cleaned name (words >= 4 chars to avoid noise)
    keywords = [w.lower() for w in re.split(r"\W+", search_term) if len(w) >= 4]

    print(f"\nSearching AFR for: {company_name} (query: '{search_term}')")
    search_url = f"https://www.afr.com/search?text={urllib.parse.quote(search_term)}"
    page.goto(search_url)

    try:
        page.wait_for_selector('a[data-testid="headlineLink"]', timeout=8000)
    except PlaywrightTimeoutError:
        print("No articles found or timeout.")
        return

    # Collect candidate links
    links = page.locator('a[data-testid="headlineLink"]').all()
    unique_urls = []
    for link in links:
        url = link.get_attribute("href") or ""
        title_text = link.inner_text() or ""
        if url and not url.startswith("http"):
            url = "https://www.afr.com" + url
        # Relevance gate — skip if neither URL nor headline mentions the company
        if not keywords or _is_relevant(url, title_text, keywords):
            if url and url not in unique_urls:
                unique_urls.append(url)

    if not unique_urls:
        print(f"No relevant articles found for '{search_term}'.")
        return

    for url in unique_urls[:3]:
        # Skip if already saved to company_news
        if conn.execute("SELECT id FROM company_news WHERE url=?", (url,)).fetchone():
            print(f"Already in database: {url}")
            continue

        print(f"Scraping article: {url}")
        page.goto(url)

        try:
            page.wait_for_selector('article', timeout=12000)

            title_loc = page.locator('h1').first
            title = title_loc.inner_text() if title_loc.is_visible() else "Unknown Title"

            paragraphs = page.locator('article p').all()
            text_content = "\n".join([p.inner_text() for p in paragraphs])

            if len(text_content) < 100:
                print("Article too short (paywall or empty).")
                continue

            print("Summarizing...")
            summary = summarize_article(text_content)

            conn.execute("""
                INSERT INTO company_news (acn, source, url, title, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (acn, 'AFR', url, title, summary, time.time()))
            conn.commit()
            print("Saved successfully.")

        except PlaywrightTimeoutError:
            print(f"Timeout loading article: {url}")
            continue

        time.sleep(2)

def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)
        
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS company_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                acn TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                summary TEXT,
                fetched_at REAL
            )
        """)
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        sys.exit(1)
    
    # Query company names directly from the infringements table ERD column — no JSON parsing
    rows = conn.execute("""
        SELECT DISTINCT acn, name
        FROM infringements
        WHERE name IS NOT NULL AND name != ''
        ORDER BY name
    """).fetchall()
    companies = [{"acn": r["acn"], "name": r["name"]} for r in rows]

    print(f"Found {len(companies)} unique infringement companies to scrape.")

    if not companies:
        print("No infringement companies found in the infringements table. Run migrate_to_erd.py first.")
        sys.exit(0)

    with sync_playwright() as p:
        # Launch browser in visible mode if we need to log in (to handle CAPTCHAs), else headless
        needs_login = not SESSION_FILE.exists()
        browser = p.chromium.launch(headless=not needs_login)
        
        # Add standard user agent to avoid basic blocks
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        
        context = None
        if not needs_login:
            print("Loading existing session...")
            context = browser.new_context(storage_state=str(SESSION_FILE), user_agent=user_agent)
        else:
            context = browser.new_context(user_agent=user_agent)
            
        Stealth().apply_stealth_sync(context)
        page = context.new_page()
        
        if not SESSION_FILE.exists():
            login_afr(page)
            
        for comp in companies:
            acn = comp['acn']
            name = comp['name']
            try:
                scrape_company_news(page, acn, name, conn)
            except Exception as e:
                print(f"Error scraping {name}: {e} — skipping")
            time.sleep(3)
            
        browser.close()
        
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
