"""
Demo: Waitless on TodoMVC (React)

Tests waitless on TodoMVC React app - a site with:
- Dynamic DOM updates
- CSS animations
- No page reloads (SPA)

Run: python demo_todomvc.py [--flaky|--stable]
"""

import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
)

from waitless import stabilize, StabilizationConfig, get_diagnostics

URL = "https://todomvc.com/examples/react/dist/"


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)


# ═══════════════════════════════════════════════════════════════════════════
# WITHOUT WAITLESS
# ═══════════════════════════════════════════════════════════════════════════

def test_without_waitless():
    """Flaky test - clicks immediately without waiting."""
    print("\n" + "=" * 60)
    print("TEST WITHOUT WAITLESS (Flaky)")
    print("=" * 60)
    
    driver = create_driver()
    
    try:
        # Step 1: Go to TodoMVC
        print("\n→ Loading TodoMVC...")
        driver.get(URL)
        
        # Step 2: Type a new todo immediately
        print("→ Adding todo item immediately...")
        try:
            input_box = driver.find_element(By.CSS_SELECTOR, ".new-todo")
            input_box.send_keys("Test item 1" + Keys.ENTER)
            print("  ✓ Todo added")
        except NoSuchElementException as e:
            print(f"  ✗ FAILED: Input not found yet")
            return False
        
        # Step 3: Toggle the todo immediately 
        print("→ Toggling todo immediately...")
        try:
            toggle = driver.find_element(By.CSS_SELECTOR, ".toggle")
            toggle.click()
            print("  ✓ Todo toggled")
        except NoSuchElementException as e:
            print(f"  ✗ FAILED: Toggle not found")
            return False
        
        # Step 4: Click Clear Completed
        print("→ Clicking 'Clear completed' immediately...")
        try:
            clear_btn = driver.find_element(By.CSS_SELECTOR, ".clear-completed")
            clear_btn.click()
            print("  ✓ Cleared completed")
        except NoSuchElementException as e:
            print(f"  ✗ FAILED: Clear button not found")
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
# WITH WAITLESS
# ═══════════════════════════════════════════════════════════════════════════

def test_with_waitless():
    """Stable test - waitless auto-waits."""
    print("\n" + "=" * 60)
    print("TEST WITH WAITLESS (Stable)")
    print("=" * 60)
    
    driver = create_driver()
    
    try:
        # Enable waitless
        config = StabilizationConfig(debug_mode=True)
        driver = stabilize(driver, config=config)
        print("\n✓ Waitless enabled")
        
        # Step 1: Go to TodoMVC
        print("\n→ Loading TodoMVC...")
        driver.get(URL)
        print("  ✓ Site loaded")
        
        # Step 2: Type a new todo - waitless auto-waits for input
        print("\n→ Adding todo item...")
        input_box = driver.find_element(By.CSS_SELECTOR, ".new-todo")
        input_box.send_keys("Test item 1" + Keys.ENTER)
        print("  ✓ Todo added")
        
        # Step 3: Toggle the todo - waitless auto-waits for toggle
        print("\n→ Toggling todo...")
        toggle = driver.find_element(By.CSS_SELECTOR, ".toggle")
        toggle.click()
        print("  ✓ Todo toggled")
        
        # Step 4: Click Clear Completed - waitless auto-waits
        print("\n→ Clicking 'Clear completed'...")
        clear_btn = driver.find_element(By.CSS_SELECTOR, ".clear-completed")
        clear_btn.click()
        print("  ✓ Cleared completed")
        
        # Show diagnostics
        print("\n" + "=" * 40)
        print("WAITLESS DIAGNOSTICS")
        print("=" * 40)
        diag = get_diagnostics(driver)
        if diag:
            status = diag.get('last_status', {}) or {}
            print(f"🔍 What Waitless Detected:")
            print(f"  • Mutation rate: {status.get('mutation_rate', 'N/A')}/sec")
            print(f"  • Pending requests: {status.get('pending_requests', 'N/A')}")
            print(f"  • Active animations: {status.get('active_animations', 'N/A')}")
        
        print("\n" + "-" * 40)
        print("STABLE: All actions succeeded!")
        print("Waitless handled React's dynamic DOM.")
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
            print("Usage: python demo_todomvc.py [--flaky|--stable]")
    else:
        print("\n╔" + "═" * 50 + "╗")
        print("║  WAITLESS DEMO: TodoMVC React                     ║")
        print("╚" + "═" * 50 + "╝")
        
        input("\n[Press Enter to run FLAKY test...]")
        result1 = test_without_waitless()
        
        input("\n[Press Enter to run STABLE test...]")
        result2 = test_with_waitless()
        
        print("\n╔" + "═" * 50 + "╗")
        print("║  SUMMARY                                          ║")
        print("╠" + "═" * 50 + "╣")
        print(f"║  Without: {'FLAKY' if not result1 else 'Passed':<36}  ║")
        print(f"║  With:    {'STABLE' if result2 else 'Failed':<36}  ║")
        print("╚" + "═" * 50 + "╝")
