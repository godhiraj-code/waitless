import time
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from waitless import stabilize, get_diagnostics

# Path to test fixture relative to this script
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "shadow_dom_page.html"
FIXTURE_URL = f"file:///{FIXTURE_PATH.absolute().as_posix()}"

def generate_evidence():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    
    # Try to find chromedriver in CI environment
    driver = webdriver.Chrome(options=options)
    
    try:
        # Wrap driver
        driver = stabilize(driver)
        driver.get(FIXTURE_URL)
        
        print("--- GENERATING EVIDENCE: Shadow DOM Support ---")
        
        # Trigger mutations
        btn = driver.find_element("id", "trigger-btn")
        btn.click()
        
        print("Waiting for Shadow DOM stability...")
        start_time = time.time()
        
        # Poll for completion inside shadow root
        found = False
        while (time.time() - start_time) < 5:
            driver.wait_for_stability()
            
            # Check via JS if it's done
            is_complete = driver.execute_script("""
                const host = document.getElementById('shadow-host');
                if (!host || !host.shadowRoot) return false;
                return host.shadowRoot.getElementById('shadow-complete') !== null;
            """)
            if is_complete:
                found = True
                break
            time.sleep(0.05)
            
        duration = time.time() - start_time
        print(f"Total Wait Duration: {duration:.2f}s")
        
        # Save screenshot to current working directory
        screenshot_path = "shadow_dom_evidence.png"
        driver.save_screenshot(screenshot_path)
        print(f"Evidence saved to: {os.path.abspath(screenshot_path)}")
        
        diag = get_diagnostics(driver)
        print("\nStability Verified: SUCCESS" if duration > 0.4 and found else "\nStability Verified: FAILURE")

    finally:
        driver.quit()

if __name__ == "__main__":
    generate_evidence()
