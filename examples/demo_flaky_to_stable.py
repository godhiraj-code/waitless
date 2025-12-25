"""
Demo: Flaky Test → Stable Test with Waitless

Simple demo showing waitless in action:
1. Load site
2. Click About menu
3. Click Latest Insights "Read Article"

Without waitless: May fail - popup not ready
With waitless: Automatically waits for element to appear

Run: python demo_flaky_to_stable.py [--flaky|--stable]
"""

import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    NoSuchElementException,
)

from waitless import stabilize, StabilizationConfig, get_diagnostics

URL = "https://www.dhirajdas.dev"


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)


# ═══════════════════════════════════════════════════════════════════════════
# WITHOUT WAITLESS - Flaky
# ═══════════════════════════════════════════════════════════════════════════

def test_without_waitless():
    """Flaky test - clicks immediately without waiting."""
    print("\n" + "=" * 60)
    print("TEST WITHOUT WAITLESS (Flaky)")
    print("=" * 60)
    
    driver = create_driver()
    
    try:
        # Step 1: Load site
        print("\n→ Loading site...")
        driver.get(URL)
        
        # Step 2: Click About immediately
        print("→ Clicking 'About' immediately...")
        try:
            about = driver.find_element(By.XPATH, "//a[contains(text(), 'About')]")
            about.click()
            print("  ✓ About clicked")
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            print(f"  ✗ FAILED: {type(e).__name__}")
            return False
        
        # Step 3: Go back to homepage
        driver.get(URL)
        
        # Step 4: Try to click Latest Insights immediately (will fail - popup not ready)
        print("→ Clicking 'Read Article' in Latest Insights immediately...")
        try:
            # The popup takes 2-3 seconds to appear - this will fail
            read_article = driver.find_element(By.CSS_SELECTOR, ".blog-nudge-button")
            read_article.click()
            print("  ✓ Read Article clicked")
        except NoSuchElementException as e:
            print(f"  ✗ FAILED: Element not found - popup not ready")
            return False
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            print(f"  ✗ FAILED: {type(e).__name__}")
            return False
        
        print("\n" + "-" * 40)
        print("PASSED (got lucky!)")
        return True
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        return False
        
    finally:
        time.sleep(1)
        driver.quit()


# ═══════════════════════════════════════════════════════════════════════════
# WITH WAITLESS - Stable
# ═══════════════════════════════════════════════════════════════════════════

def test_with_waitless():
    """Stable test - waitless auto-waits for elements to appear."""
    print("\n" + "=" * 60)
    print("TEST WITH WAITLESS (Stable)")
    print("=" * 60)
    
    driver = create_driver()
    
    try:
        # Enable waitless with relaxed mode for dynamic sites
        # The site has continuous animations/mutations - relaxed mode tolerates this
        config = StabilizationConfig(
            timeout=15,
            strictness='relaxed',        # Don't wait for animations to stop
            mutation_rate_threshold=200,  # Tolerate more DOM activity
            debug_mode=True
        )
        driver = stabilize(driver, config=config)
        print("\n✓ Waitless enabled (relaxed mode for dynamic site)")
        
        # Step 1: Load site
        print("\n→ Loading site...")
        driver.get(URL)
        print("  ✓ Site loaded")
        
        # Step 2: Click About - waitless auto-waits before click
        print("\n→ Clicking 'About' menu...")
        about = driver.find_element(By.XPATH, "//a[contains(text(), 'About')]")
        about.click()  # ← Waitless auto-waits for stability
        print("  ✓ About clicked")
        
        # Step 3: Go back to homepage
        print("\n→ Going back to homepage...")
        driver.get(URL)
        
        # Step 4: Click Latest Insights - waitless auto-waits for element to appear!
        # NO WebDriverWait needed - waitless handles it
        print("\n→ Clicking 'Read Article' in Latest Insights...")
        print("  (waitless auto-waits for popup to appear)")
        
        read_article = driver.find_element(By.CSS_SELECTOR, ".blog-nudge-button")
        
        # Debug: Check if element is displayed
        el = read_article.unwrap()
        print(f"  DEBUG: Element found, displayed={el.is_displayed()}, text='{el.text}'")
        
        # Scroll element into view to ensure it's clickable
        driver.unwrapped.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        time.sleep(0.3)  # Brief pause after scroll
        
        read_article.click()  # ← Waitless auto-waits for stability
        print("  ✓ Read Article clicked")
        
        # Show diagnostics
        print("\n" + "=" * 40)
        print("WAITLESS DIAGNOSTICS")
        print("=" * 40)
        diag = get_diagnostics(driver)
        if diag:
            status = diag.get('last_status', {})
            print(f"🔍 What Waitless Detected:")
            print(f"  • Mutation rate: {status.get('mutation_rate', 'N/A')}/sec")
            print(f"  • Pending requests: {status.get('pending_requests', 'N/A')}")
            print(f"  • Active animations: {status.get('active_animations', 'N/A')}")
        
        print("\n" + "-" * 40)
        print("STABLE: All clicks succeeded!")
        print("Waitless automatically waited for elements and stability.")
        return True
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        time.sleep(2)
        driver.quit()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--flaky":
            test_without_waitless()
        elif sys.argv[1] == "--stable":
            test_with_waitless()
        else:
            print("Usage: python demo_flaky_to_stable.py [--flaky|--stable]")
    else:
        # Run both
        print("\n╔" + "═" * 50 + "╗")
        print("║  WAITLESS DEMO: Flaky → Stable                    ║")
        print("╚" + "═" * 50 + "╝")
        
        input("\n[Press Enter to run FLAKY test...]")
        result1 = test_without_waitless()
        
        input("\n[Press Enter to run STABLE test...]")
        result2 = test_with_waitless()
        
        print("\n╔" + "═" * 50 + "╗")
        print("║  SUMMARY                                          ║")
        print("╠" + "═" * 50 + "╣")
        print(f"║  Without Waitless: {'FLAKY' if not result1 else 'Passed':<28}  ║")
        print(f"║  With Waitless:    {'STABLE' if result2 else 'Failed':<28}  ║")
        print("╚" + "═" * 50 + "╝")
