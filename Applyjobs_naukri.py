import os
import time
import sys
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException,
    WebDriverException
)
import traceback

# ------------------ Configuration ------------------
# recommended: set these as environment variables instead of hardcoding
GEMINI_API_KEY = os.environ.get("AIzaSyC60GiDVrsxpEYPu-Pq3486r3MPbxKfgc8", "")  # optional, not used in this debug run
NAUKRI_EMAIL = os.environ.get("NAUKRI_EMAIL", "nalinelliot.dsouza@gmail.com")
NAUKRI_PASSWORD = os.environ.get("NAUKRI_PASSWORD", "calsiner@3185")

GECKODRIVER_PATH = os.environ.get("GECKODRIVER_PATH", None)  # optional
FIREFOX_BINARY = r"C:\Program Files\Mozilla Firefox\firefox.exe"  # change if needed

LOGIN_URL = "https://www.naukri.com/nlogin/login"
JOB_SEARCH_URL = "https://www.naukri.com/program-management-team-lead-project-management-pmo-it-project-management-delivery-management-service-delivery-manager-it-service-delivery-management-it-operations-management-jobs-in-delhi-ncr?k=program%20management%2C%20team%20lead%2C%20project%20management%2C%20pmo%2C%20it%20project%20management%2C%20delivery%20management%2C%20service%20delivery%20manager%2C%20it%20service%20delivery%20management%2C%20it%20operations%20management&l=delhi%20%2F%20ncr"
MAX_APPLIES = 10
WAIT_SECONDS = 15
SCREENSHOT_DIR = "debug_screens"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
# ----------------------------------------------------

def debug_print(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

# --- WebDriver init (verbose) ---
def init_driver():
    opts = Options()
    # opts.headless = False   # leave visible while debugging
    if FIREFOX_BINARY:
        opts.binary = FIREFOX_BINARY

    if GECKODRIVER_PATH:
        from selenium.webdriver.firefox.service import Service
        service = Service(executable_path=GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=opts)
    else:
        driver = webdriver.Firefox(options=opts)

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(2)  # short implicit wait; rely on explicit waits
    return driver

driver = None
try:
    debug_print("Initializing WebDriver...")
    driver = init_driver()
    debug_print("WebDriver initialized successfully.")
except Exception as e:
    debug_print(f"Failed to initialize WebDriver: {e}")
    traceback.print_exc()
    sys.exit(1)

wait = WebDriverWait(driver, WAIT_SECONDS)

# --- utility: take screenshot + save page source ---
def save_debug_snapshot(name_prefix):
    ts = time.strftime("%Y%m%d-%H%M%S")
    png = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{ts}.png")
    html = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{ts}.html")
    try:
        driver.save_screenshot(png)
        debug_print(f"Saved screenshot: {png}")
    except Exception as e:
        debug_print(f"Could not save screenshot: {e}")
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        debug_print(f"Saved page source: {html}")
    except Exception as e:
        debug_print(f"Could not save page source: {e}")

# --- utility: try many selectors, return the first present element ---
def find_element_fallback(selector_list, timeout=4):
    """
    selector_list: list of tuples (By.SOMETHING, "selector string")
    tries each selector for up to `timeout` seconds and returns first match
    """
    for by, sel in selector_list:
        try:
            el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
            debug_print(f"Found element using: {by} '{sel}'")
            return el
        except TimeoutException:
            continue
        except StaleElementReferenceException:
            continue
    return None

# --- Close extra windows that some sites open automatically ---
def close_extra_windows():
    handles = driver.window_handles
    if len(handles) > 1:
        main = driver.current_window_handle
        debug_print(f"Multiple windows detected: {len(handles)} - closing extras.")
        for h in handles:
            if h != main:
                try:
                    driver.switch_to.window(h)
                    driver.close()
                except Exception:
                    pass
        driver.switch_to.window(main)
        time.sleep(1)

# --- Robust login with multiple selector fallbacks and retries ---
def login_to_naukri(max_retries=3):
    debug_print("Starting login attempts...")
    for attempt in range(1, max_retries + 1):
        debug_print(f"Login attempt {attempt}/{max_retries}")
        try:
            driver.get(LOGIN_URL)
            time.sleep(1.5)
            debug_print(f"Page title after navigate: '{driver.title}' Current URL: {driver.current_url}")

            close_extra_windows()

            # If site displays a 'Login' modal only after clicking something, try that first:
            # Try to click any "Login" link/button that may open a modal:
            try_login_triggers = [
                (By.XPATH, "//a[contains(translate(text(), 'LOGIN', 'login'), 'login')]"),
                (By.XPATH, "//button[contains(translate(text(), 'LOGIN', 'login'), 'login')]"),
                (By.CSS_SELECTOR, "a[href*='nlogin']"),
            ]
            for by, sel in try_login_triggers:
                try:
                    btn = driver.find_element(by, sel)
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    debug_print(f"Clicking potential login trigger: {sel}")
                    try:
                        btn.click()
                        time.sleep(0.5)
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                            time.sleep(0.5)
                        except Exception:
                            pass
                except Exception:
                    pass  # not fatal; continue

            # Prepare fallback selectors for email and password
            email_selectors = [
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[placeholder*='Email']"),
                (By.CSS_SELECTOR, "input[id*='email']"),
                (By.CSS_SELECTOR, "input[id*='user']"),
                (By.CSS_SELECTOR, "input[name='email']"),
                (By.CSS_SELECTOR, "input[name='username']"),
                (By.CSS_SELECTOR, "input#eMail"),
            ]
            password_selectors = [
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[id*='password']"),
                (By.CSS_SELECTOR, "input[name='password']"),
            ]
            login_button_selectors = [
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.XPATH, "//button[contains(translate(text(), 'LOGIN', 'login'), 'login')]"),
                (By.CSS_SELECTOR, "button.loginBtn"),
                (By.CSS_SELECTOR, "button.btn-primary"),
            ]

            email_el = find_element_fallback(email_selectors, timeout=4)
            if not email_el:
                debug_print("Email input NOT found with initial selectors. Will take snapshot and retry after small wait.")
                save_debug_snapshot("login_no_email")
                raise Exception("Email input not found")

            # always re-find elements immediately before interacting to avoid stale references
            email_el = find_element_fallback(email_selectors, timeout=3)
            email_el.clear()
            email_el.send_keys(NAUKRI_EMAIL)
            debug_print("Entered email.")

            password_el = find_element_fallback(password_selectors, timeout=4)
            if not password_el:
                debug_print("Password input not found. Snapshotting.")
                save_debug_snapshot("login_no_password")
                raise Exception("Password input not found")
            password_el = find_element_fallback(password_selectors, timeout=3)
            password_el.clear()
            password_el.send_keys(NAUKRI_PASSWORD)
            debug_print("Entered password.")

            login_btn = find_element_fallback(login_button_selectors, timeout=4)
            if not login_btn:
                debug_print("Login button NOT found; snapshotting and failing this attempt.")
                save_debug_snapshot("login_no_button")
                raise Exception("Login button not found")
            try:
                driver.execute_script("arguments[0].click();", login_btn)
            except Exception:
                try:
                    login_btn.click()
                except Exception as e:
                    debug_print(f"Could not click login button: {e}")

            debug_print("Clicked login. Waiting for profile or sign of successful login...")

            # Wait for signs of a successful login — try multiple indications
            try:
                # indicator: profile area or logout link or My Naukri link
                success_indicators = [
                    (By.XPATH, "//a[contains(text(), 'My Naukri')]"),
                    (By.XPATH, "//a[contains(translate(text(), 'Logout', 'logout'), 'logout')]"),
                    (By.CSS_SELECTOR, "div.nI-gNb-drawer__profile"),
                    (By.CSS_SELECTOR, "div.nI-gNb-nav-header__profile"),
                    (By.CSS_SELECTOR, "a[href*='logout']"),
                ]
                logged_in = False
                for by, sel in success_indicators:
                    try:
                        wait_short = WebDriverWait(driver, 6)
                        wait_short.until(EC.presence_of_element_located((by, sel)))
                        logged_in = True
                        break
                    except Exception:
                        continue

                # As fallback, check that current URL changed away from login URL
                if not logged_in:
                    time.sleep(2)
                    if driver.current_url and "nlogin" not in driver.current_url:
                        debug_print(f"URL changed after login click to: {driver.current_url}")
                        logged_in = True

                if logged_in:
                    debug_print("Login appears successful.")
                    # close extra windows that may have opened automatically
                    close_extra_windows()
                    return True
                else:
                    debug_print("Login attempt did not show success indicators.")
                    save_debug_snapshot("login_no_success_indicator")
                    raise Exception("Login attempt did not complete (no success indicators).")

            except Exception as e:
                debug_print(f"Waiting for success indicators threw: {e}")
                save_debug_snapshot("login_wait_exception")
                raise

        except Exception as e:
            debug_print(f"[Login attempt {attempt}] Exception: {e}")
            traceback.print_exc()
            # small backoff before retry
            time.sleep(2)

    debug_print("All login attempts exhausted — login failed.")
    return False

# --- Job scraping attempt with robust link-finding ---
def scrape_job_links(max_links=MAX_APPLIES):
    debug_print(f"Navigating to search page: {JOB_SEARCH_URL}")
    driver.get(JOB_SEARCH_URL)
    time.sleep(2)
    close_extra_windows()

    # try multiple selectors for job anchor links
    link_selectors = [
        (By.CSS_SELECTOR, "a.title"),                         # common enhanced
        (By.CSS_SELECTOR, "a[href*='/view/']"),
        (By.CSS_SELECTOR, "a[href*='/jobs/']"),
        (By.CSS_SELECTOR, "a.jobTuple a"),                    # some site structures
        (By.CSS_SELECTOR, "article a"),                       # broad fallback
        (By.CSS_SELECTOR, "a[data-job-id]"),
    ]

    job_links = []
    for by, sel in link_selectors:
        try:
            els = driver.find_elements(by, sel)
            for e in els:
                try:
                    href = e.get_attribute("href")
                    if href and href.startswith("http"):
                        if href not in job_links:
                            job_links.append(href)
                except Exception:
                    pass
            if job_links:
                debug_print(f"Found {len(job_links)} job links using selector {by} '{sel}'")
                break
        except Exception as e:
            debug_print(f"Selector {sel} threw: {e}")
            continue

    debug_print(f"Total collected job links: {len(job_links)}")
    return job_links[:max_links]

# --- attempt to apply on a job page (simplified) ---
def apply_to_job(job_url):
    debug_print(f"Processing: {job_url}")
    try:
        driver.get(job_url)
        time.sleep(2)
        close_extra_windows()
    except Exception as e:
        debug_print(f"Could not navigate to job page: {e}")
        save_debug_snapshot("job_nav_error")
        return False

    # quick guard: if already applied message is present
    try:
        if driver.find_elements(By.XPATH, "//*[contains(text(), 'You have already applied')]"):
            debug_print("Already applied - skipping.")
            return True
    except Exception:
        pass

    apply_selectors = [
        (By.ID, "apply-button"),
        (By.CSS_SELECTOR, ".btn-apply-now"),
        (By.XPATH, "//button[contains(translate(text(), 'APPLY', 'apply'), 'apply')]"),
        (By.CSS_SELECTOR, "button.apply"),
        (By.XPATH, "//a[contains(translate(text(), 'APPLY', 'apply'), 'apply')]"),
        (By.CSS_SELECTOR, "div.apply-btn a"),
    ]

    clicked_apply = False
    for by, sel in apply_selectors:
        try:
            btn = driver.find_element(by, sel)
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            try:
                driver.execute_script("arguments[0].click();", btn)
            except Exception:
                try:
                    btn.click()
                except Exception as e:
                    debug_print(f"Click fallback failed for {sel}: {e}")
                    continue
            clicked_apply = True
            debug_print(f"Clicked apply using {by} '{sel}'")
            time.sleep(1.5)
            break
        except NoSuchElementException:
            continue
        except StaleElementReferenceException:
            continue
        except Exception as e:
            debug_print(f"Error trying apply selector {sel}: {e}")
            continue

    if not clicked_apply:
        debug_print("No apply button found on this job.")
        save_debug_snapshot("no_apply_button")
        return False

    # wait briefly for confirmation (simplified)
    try:
        # common confirmation text
        conf_xpaths = [
            "//*[contains(text(), 'Your application has been sent successfully')]",
            "//*[contains(text(), 'Application submitted')]",
            "//*[contains(text(), 'You have applied')]",
            "//*[contains(text(), 'Application Received')]",
        ]
        confirmed = False
        for xp in conf_xpaths:
            try:
                el = WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.XPATH, xp)))
                if el:
                    debug_print("Application confirmed by page text.")
                    confirmed = True
                    break
            except Exception:
                continue

        if not confirmed:
            debug_print("No clear confirmation found — saving snapshot.")
            save_debug_snapshot("no_apply_confirm")
            # sometimes the application will open a new window/modal to fill; give the script the benefit of the doubt
            # if an "Apply" flow opens a modal with questions, more logic is needed (Gemini auto-answering etc.)
            return True  # return True to indicate we clicked apply; change if you want stricter check
        return True
    except Exception as e:
        debug_print(f"Error while waiting for confirmation: {e}")
        save_debug_snapshot("apply_confirm_exception")
        return False

# ------------------ Main flow ------------------
try:
    if not login_to_naukri(max_retries=3):
        debug_print("Login failed. Exiting script.")
        save_debug_snapshot("final_login_failed")
        driver.quit()
        sys.exit(1)

    debug_print("Logged in. Now scraping job links...")
    links = scrape_job_links(max_links=MAX_APPLIES)
    if not links:
        debug_print("No job links found on search page. Snapshotting and exiting.")
        save_debug_snapshot("no_links_found")
        driver.quit()
        sys.exit(1)

    debug_print(f"Beginning to apply to up to {len(links)} jobs...")
    applied = 0
    failed = 0
    for idx, link in enumerate(links, start=1):
        debug_print(f"({idx}/{len(links)}) Attempting apply...")
        ok = apply_to_job(link)
        if ok:
            applied += 1
            debug_print(f"Applied (or clicked apply) for {link}")
        else:
            failed += 1
            debug_print(f"Failed to apply for {link}")
        # small gap between applies to avoid hitting rate limits
        time.sleep(2)

    debug_print(f"Finished. Applied: {applied}, Failed: {failed}")
    save_debug_snapshot("final_state")

except Exception as e:
    debug_print(f"Unhandled exception in main flow: {e}")
    traceback.print_exc()
    save_debug_snapshot("unhandled_exception")

finally:
    debug_print("Quitting driver...")
    try:
        driver.quit()
    except Exception:
        pass
