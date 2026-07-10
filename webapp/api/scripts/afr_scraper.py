import os
import sys
import time
import json
import sqlite3
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("Please install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from anthropic import Anthropic
except ImportError:
    print("Please install anthropic: pip install anthropic")
    sys.exit(1)

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", HERE.parent.parent.parent / "data")))
DB_PATH = DATA_DIR / "unified_companies.db"
if not DB_PATH.exists() and (HERE.parent.parent.parent / "railway_db.sqlite").exists():
    DB_PATH = HERE.parent.parent.parent / "railway_db.sqlite"
    
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
            model="claude-3-haiku-20240307",
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
    print("Logging into AFR...")
    page.goto("https://www.afr.com/login")
    
    try:
        # Wait for the email field
        page.wait_for_selector('input[type="email"]', timeout=10000)
        page.fill('input[type="email"]', AFR_EMAIL)
        
        # Check if password is on the same page
        if page.is_visible('input[type="password"]'):
            page.fill('input[type="password"]', AFR_PASSWORD)
            page.click('button[type="submit"]')
        else:
            # Click continue and wait for password field
            page.click('button[type="submit"]')
            page.wait_for_selector('input[type="password"]', timeout=10000)
            page.fill('input[type="password"]', AFR_PASSWORD)
            page.click('button[type="submit"]')
        
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
        sys.exit(1)

def scrape_company_news(page, acn: str, company_name: str, conn: sqlite3.Connection):
    print(f"\nSearching AFR for: {company_name}")
    search_url = f"https://www.afr.com/search?text={company_name}"
    page.goto(search_url)
    
    try:
        page.wait_for_selector('a[data-testid="StoryTileBasic-Title"]', timeout=5000)
    except PlaywrightTimeoutError:
        print("No articles found or timeout.")
        return

    # Extract top 3 article links
    links = page.locator('a[data-testid="StoryTileBasic-Title"]').all()
    top_links = []
    for link in links[:3]:
        url = link.get_attribute("href")
        if url and url.startswith("/"):
            url = "https://www.afr.com" + url
        if url:
            top_links.append(url)
            
    print(f"Found {len(top_links)} articles.")
    
    for url in top_links:
        # Check if already processed
        cur = conn.execute("SELECT 1 FROM company_news WHERE url = ?", (url,))
        if cur.fetchone():
            print(f"Already processed: {url}")
            continue
            
        print(f"Scraping article: {url}")
        page.goto(url)
        
        try:
            page.wait_for_selector('article', timeout=10000)
            
            title_loc = page.locator('h1').first
            title = title_loc.inner_text() if title_loc.is_visible() else "Unknown Title"
            
            paragraphs = page.locator('article p').all()
            text_content = "\n".join([p.inner_text() for p in paragraphs])
            
            if len(text_content) < 100:
                print("Article too short (might be blocked by paywall).")
                continue
                
            print("Summarizing...")
            summary = summarize_article(text_content)
            
            conn.execute("""
                INSERT INTO company_news (acn, url, title, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (acn, url, title, summary, time.time()))
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
    
    # Get companies from infringements
    # Hardcoded test list since DB isn't fully built locally
    companies = [
        {"acn": "000000001", "name": "BHP Group"},
        {"acn": "000000002", "name": "Commonwealth Bank"}
    ]
    
    if not companies:
        print("No infringement companies found in DB.")
        sys.exit(0)

    with sync_playwright() as p:
        # Launch browser in visible mode if we need to log in (to handle CAPTCHAs), else headless
        needs_login = not SESSION_FILE.exists()
        browser = p.chromium.launch(headless=not needs_login)
        
        context = None
        if not needs_login:
            print("Loading existing session...")
            context = browser.new_context(storage_state=str(SESSION_FILE))
        else:
            context = browser.new_context()
            
        page = context.new_page()
        
        if not SESSION_FILE.exists():
            login_afr(page)
            
        for comp in companies:
            acn = comp['acn']
            name = comp['name']
            scrape_company_news(page, acn, name, conn)
            time.sleep(3)
            
        browser.close()
        
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
