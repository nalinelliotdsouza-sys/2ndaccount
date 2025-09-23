import os
import time
import sys
import traceback
import requests
import json
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException

# ------------------ Configuration ------------------
# IMPORTANT: DO NOT hardcode your credentials. Use environment variables.
# You can set these in your terminal:
# For Windows: set NAUKRI_EMAIL=your_email@example.com
# For Mac/Linux: export NAUKRI_EMAIL=your_email@example.com
NAUKRI_EMAIL = os.environ.get("NAUKRI_EMAIL", "yourexactemail used to sign in")
NAUKRI_PASSWORD = os.environ.get("NAUKRI_PASSWORD", "enter Naukri password")
GECKODRIVER_PATH = os.environ.get("GECKODRIVER_PATH", None)
FIREFOX_BINARY = r"C:\Program Files\Mozilla Firefox\firefox.exe"  # change if needed

# Gemini API configuration
# Replace this with your actual Gemini API key.
GEMINI_API_KEY = "the gemini studio key you've generated"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

LOGIN_URL = "https://www.naukri.com/nlogin/login"
JOB_SEARCH_URL = "https://www.naukri.com/program-management-team-lead-project-management-pmo-it-project-management-delivery-management-service-delivery-manager-it-service-delivery-management-it-operations-management-jobs-in-delhi-ncr?k=program%20management&l=delhi%20%2F%20ncr"
MAX_APPLIES = 10
WAIT_SECONDS = 20
SCREENSHOT_DIR = "debug_screens"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ------------------ Utilities ------------------
def debug_print(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def save_debug_snapshot(name_prefix):
    ts = time.strftime("%Y%m%d-%H%M%S")
    png = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{ts}.png")
    html = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{ts}.html")
    try:
        driver.save_screenshot(png)
    except: pass
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except: pass

def init_driver():
    opts = Options()
    opts.headless = False  # We need to see the browser for this task
    if FIREFOX_BINARY:
        opts.binary = FIREFOX_BINARY
    if GECKODRIVER_PATH:
        from selenium.webdriver.firefox.service import Service
        service = Service(executable_path=GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=opts)
    else:
        driver = webdriver.Firefox(options=opts)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(5)
    return driver

def close_extra_windows():
    handles = driver.window_handles
    if len(handles) > 1:
        main = driver.current_window_handle
        for h in handles:
            if h != main:
                try:
                    driver.switch_to.window(h)
                    driver.close()
                except: pass
        driver.switch_to.window(main)
        time.sleep(1)

# ------------------ Gemini API ------------------
def call_gemini_api(question_text: str) -> str:
    """
    Calls the Gemini API to get an answer to a question.
    """
    if not GEMINI_API_KEY:
        debug_print("Gemini API key is not set. Cannot answer questions.")
        return "I cannot answer this question without an API key."

    payload = {
        "contents": [{"parts": [{"text": question_text}]}],
        "systemInstruction": {
            "parts": [{"text": "You are an expert at answering job application questions. Provide a concise, professional answer based on the provided question."}]
        }
    }
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        debug_print(f"Sending question to Gemini: '{question_text}'")
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers, timeout=30)
        response.raise_for_status() # Raise an exception for bad status codes
        
        result = response.json()
        answer = result['candidates'][0]['content']['parts'][0]['text']
        debug_print(f"Received answer from Gemini.")
        return answer
    except requests.exceptions.RequestException as e:
        debug_print(f"Error calling Gemini API: {e}")
        return "An error occurred while getting the answer."
    except (KeyError, IndexError) as e:
        debug_print(f"Failed to parse Gemini API response: {e}")
        return "Could not get a valid answer from the API."

# ------------------ Login ------------------
def login_to_naukri(max_retries=3):
    """
    Automates the login process for Naukri.com.
    """
    debug_print("Starting login process...")
    if not NAUKRI_EMAIL or not NAUKRI_PASSWORD:
        debug_print("Credentials not set. Cannot log in.")
        return False

    for attempt in range(1, max_retries + 1):
        try:
            debug_print(f"Attempt {attempt}: Navigating to login page.")
            driver.get(LOGIN_URL)
            wait = WebDriverWait(driver, WAIT_SECONDS)
            time.sleep(3)
            save_debug_snapshot("login_page_loaded")
            
            # Correctly locate the email field by its ID, as per your observation.
            email_el = wait.until(EC.presence_of_element_located((By.ID, "usernameField")))
            password_el = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
            
            # Enter credentials first to trigger the login button to appear
            email_el.clear()
            email_el.send_keys(NAUKRI_EMAIL)
            password_el.clear()
            password_el.send_keys(NAUKRI_PASSWORD)
            debug_print("Entered email and password.")
            
            # Now, wait for the login button to appear and be clickable
            login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'].blue-btn")))
            
            # Click login button
            driver.execute_script("arguments[0].scrollIntoView(true);", login_btn)
            login_btn.click()
            debug_print("Clicked Login button.")

            # Wait for a URL change to confirm login was successful
            wait.until(EC.url_changes(LOGIN_URL))
            debug_print("Login successful. URL changed.")

            # Handle common pop-ups after login
            try:
                close_icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".close-icon, .close-popup")))
                close_icon.click()
                debug_print("Closed a pop-up.")
            except (TimeoutException, NoSuchElementException):
                pass

            # Navigate to the job search URL after a successful login.
            debug_print(f"Navigating to job search results: {JOB_SEARCH_URL}")
            driver.get(JOB_SEARCH_URL)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            return True

        except Exception as e:
            debug_print(f"Login attempt {attempt} failed: {e}")
            save_debug_snapshot(f"login_exception_{attempt}")
            if driver:
                driver.switch_to.default_content()
            time.sleep(5)
    
    debug_print("Login failed after all retries.")
    return False

# ------------------ Job scraping ------------------
def scrape_job_links(max_links=MAX_APPLIES):
    debug_print("Scraping job links from search page...")
    time.sleep(5) # Give page time to render
    close_extra_windows()
    link_selectors = [
        (By.CSS_SELECTOR, "a.title"),
        (By.CSS_SELECTOR, "a[href*='/view/']"),
        (By.CSS_SELECTOR, "a[href*='/jobs/']"),
        (By.CSS_SELECTOR, "a.jobTuple a"),
    ]
    job_links = []
    for by, sel in link_selectors:
        try:
            els = driver.find_elements(by, sel)
            for e in els:
                href = e.get_attribute("href")
                if href and href.startswith("http") and href not in job_links:
                    job_links.append(href)
            if job_links:
                break
        except Exception as e:
            debug_print(f"Selector '{sel}' failed: {e}")
            continue
    debug_print(f"Total job links collected: {len(job_links)}")
    return job_links[:max_links]

# ------------------ Gemini question answering ------------------
def answer_questions_with_gemini():
    try:
        debug_print("Checking for application questions...")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'formBody') and descendant::textarea] | //div[contains(@class, 'formBody') and descendant::input]"))
        )
        questions = driver.find_elements(By.XPATH, "//div[contains(@class, 'formGroup')] | //div[contains(@class, 'form-group')]")
        debug_print(f"Found {len(questions)} potential question containers.")

        for q_el in questions:
            question_text = ""
            try:
                question_text = q_el.find_element(By.TAG_NAME, "label").text.strip()
            except NoSuchElementException:
                try:
                    question_text = q_el.find_element(By.TAG_NAME, "p").text.strip()
                except NoSuchElementException:
                    debug_print("Could not find question label, skipping this container.")
                    continue
            
            if not question_text:
                continue

            debug_print(f"Found question: '{question_text}'")
            
            # Call Gemini to get the answer
            answer = call_gemini_api(question_text)
            
            if "error" in answer.lower(): # Basic check for API errors
                debug_print(f"Skipping question due to API error: '{question_text}'")
                continue

            try:
                input_field = q_el.find_element(By.TAG_NAME, "input")
            except NoSuchElementException:
                try:
                    input_field = q_el.find_element(By.TAG_NAME, "textarea")
                except NoSuchElementException:
                    debug_print("Could not find input field for question.")
                    continue
            
            input_field.clear()
            input_field.send_keys(answer)
            debug_print(f"Filled in answer for question: '{question_text}'")
            time.sleep(1)

        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Submit Application')]")
        driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
        submit_btn.click()
        time.sleep(2)
        debug_print("Submitted answers via Gemini.")
        return True
    except TimeoutException:
        debug_print("No questions found, skipping this step.")
        return True
    except Exception as e:
        debug_print(f"Failed to answer questions with Gemini: {e}")
        save_debug_snapshot("gemini_error")
        return False

# ------------------ Apply to job ------------------
def apply_to_job(job_url):
    debug_print(f"Processing: {job_url}")
    try:
        driver.get(job_url)
        wait = WebDriverWait(driver, WAIT_SECONDS)
        time.sleep(2)
        close_extra_windows()
        
        apply_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Apply')]"))
        )
        driver.execute_script("arguments[0].click();", apply_btn)
        debug_print("Clicked Apply button.")
        
        # Check if the application requires answering questions
        answer_questions_with_gemini()
        
        # Check for successful submission message
        conf = wait.until(
            EC.presence_of_element_located((By.XPATH,
                "//*[contains(text(), 'Your application has been sent successfully') or contains(text(), 'Application submitted')]"
            ))
        )
        if conf:
            debug_print("Application submitted successfully.")
            return True
            
    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        debug_print(f"Error applying to job: {e}")
        save_debug_snapshot("apply_error")
        return False

# ------------------ Main Flow ------------------
driver = None
try:
    debug_print("Initializing WebDriver...")
    driver = init_driver()
    debug_print("WebDriver initialized successfully.")

    if not login_to_naukri(max_retries=3):
        debug_print("Login failed. Exiting.")
        save_debug_snapshot("final_login_failed")
        sys.exit(1)

    debug_print("Scraping job links...")
    links = scrape_job_links(max_links=MAX_APPLIES)
    if not links:
        debug_print("No job links found. Exiting.")
        save_debug_snapshot("no_links_found")
        sys.exit(1)

    debug_print(f"Beginning to apply to {len(links)} jobs...")
    applied, failed = 0, 0
    for idx, link in enumerate(links, start=1):
        debug_print(f"({idx}/{len(links)}) Applying...")
        ok = apply_to_job(link)
        if ok:
            applied += 1
        else:
            failed += 1
        time.sleep(2)
    debug_print(f"Finished. Applied: {applied}, Failed: {failed}")
    save_debug_snapshot("final_state")

except Exception as e:
    debug_print(f"Unhandled exception: {e}")
    save_debug_snapshot("unhandled_exception")
    traceback.print_exc()
finally:
    debug_print("Quitting driver...")
    if driver:
        driver.quit()
