"""
Demo: Flaky Test → Stable Test with Waitless

This demonstrates how waitless eliminates flaky test failures on
www.dhirajdas.dev by automatically waiting for UI stability.

Run with: python demo_flaky_to_stable.py
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
)

# Import waitless
from waitless import stabilize, StabilizationConfig


def create_driver():
    """Create Chrome driver with visible browser for demo."""
    options = Options()
    options.add_argument("--start-maximized")
    # Remove headless for demo visibility
    # options.add_argument("--headless")
    return webdriver.Chrome(options=options)


# ═══════════════════════════════════════════════════════════════════════════
# WITHOUT WAITLESS - Flaky Test (likely to fail intermittently)
# ═══════════════════════════════════════════════════════════════════════════

def test_without_waitless():
    """
    This test is FLAKY because:
    1. The page has animations that are still running
    2. Elements may not be fully interactive yet
    3. The "Latest Insights" popup may appear mid-interaction
    4. Navigation has transition effects
    
    Without waiting, clicks often fail or hit wrong elements.
    """
    print("\n" + "=" * 60)
    print("TEST WITHOUT WAITLESS (Flaky)")
    print("=" * 60)
    
    driver = create_driver()
    failures = []
    
    try:
        # Navigate to site
        print("\n→ Navigating to dhirajdas.dev...")
        driver.get("https://www.dhirajdas.dev")
        
        # PROBLEM 1: Page has entrance animations
        # Clicking immediately often fails or hits wrong element
        print("→ Attempting to click 'Projects' nav link immediately...")
        try:
            projects_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Projects')]")
            projects_link.click()
            print("  ✓ Click succeeded (lucky!)")
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            print(f"  ✗ FAILED: {type(e).__name__}")
            failures.append("Projects nav click")
        
        # PROBLEM 2: Scroll triggers lazy loading / animations
        print("→ Scrolling to projects section...")
        driver.execute_script("window.scrollTo(0, 800)")
        
        # PROBLEM 3: Immediately clicking after scroll = flaky
        print("→ Attempting to click element after scroll (no wait)...")
        try:
            # Try to find and click a project card or button
            buttons = driver.find_elements(By.CSS_SELECTOR, "button, a.btn, [role='button']")
            if buttons:
                buttons[0].click()
                print("  ✓ Click succeeded (lucky!)")
            else:
                print("  ✗ No buttons found yet (DOM still loading)")
                failures.append("Button find after scroll")
        except (StaleElementReferenceException, ElementClickInterceptedException) as e:
            print(f"  ✗ FAILED: {type(e).__name__}")
            failures.append("Button click after scroll")
        
        # PROBLEM 4: Typewriter effect / dynamic text causes mutations
        print("→ Checking for dynamic content stability...")
        try:
            # The hero section has typewriter effect
            hero = driver.find_element(By.CSS_SELECTOR, "h1, .hero, [class*='hero']")
            text1 = hero.text
            time.sleep(0.1)  # Brief pause
            text2 = hero.text
            if text1 != text2:
                print("  ⚠ Text changed between reads (typewriter animation)")
                failures.append("Dynamic text instability")
            else:
                print("  ✓ Text stable")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failures.append("Hero text check")
        
        # Results
        print("\n" + "-" * 40)
        if failures:
            print(f"FLAKY RESULT: {len(failures)} potential failure(s)")
            for f in failures:
                print(f"  - {f}")
            return False
        else:
            print("PASSED (got lucky this time!)")
            return True
            
    finally:
        time.sleep(1)  # Pause to see result
        driver.quit()


# ═══════════════════════════════════════════════════════════════════════════
# WITH WAITLESS - Stable Test
# ═══════════════════════════════════════════════════════════════════════════

def test_with_waitless():
    """
    This test is STABLE because waitless:
    1. Waits for all animations to complete
    2. Waits for network requests to finish
    3. Waits for DOM mutations to stop
    4. Ensures elements are truly ready before interaction
    """
    print("\n" + "=" * 60)
    print("TEST WITH WAITLESS (Stable)")
    print("=" * 60)
    
    driver = create_driver()
    
    try:
        # Enable waitless with debug mode to show what's happening
        config = StabilizationConfig(
            timeout=10,
            strictness='normal',
            debug_mode=True,  # Show stabilization logs
        )
        driver = stabilize(driver, config=config)
        
        # Navigate to site - waitless handles initial load stability
        print("\n→ Navigating to dhirajdas.dev...")
        driver.get("https://www.dhirajdas.dev")
        
        # SOLUTION 1: Waitless waits for animations before click
        print("\n→ Clicking 'Projects' nav link (waitless auto-waits)...")
        projects_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Projects')]")
        projects_link.click()  # ← This automatically waits for stability!
        print("  ✓ Click succeeded after UI stabilized")
        
        # SOLUTION 2: Scroll + automatic wait for lazy load
        print("\n→ Scrolling to projects section...")
        driver.unwrapped.execute_script("window.scrollTo(0, 800)")
        
        # Let waitless catch up after scroll
        from waitless import wait_for_stability
        wait_for_stability(driver)
        
        # SOLUTION 3: Elements are guaranteed stable before interaction
        print("\n→ Clicking element after scroll (waitless auto-waits)...")
        buttons = driver.find_elements(By.CSS_SELECTOR, "button, a.btn, [role='button']")
        if buttons:
            buttons[0].click()  # ← Automatically waits!
            print("  ✓ Click succeeded after stability detected")
        
        # SOLUTION 4: Check content only after DOM is stable
        print("\n→ Checking content (after stability)...")
        hero = driver.find_element(By.CSS_SELECTOR, "h1, .hero-title, [class*='hero']")
        print(f"  ✓ Hero text: {hero.unwrap().text[:50]}...")
        
        print("\n" + "-" * 40)
        print("STABLE RESULT: All interactions succeeded!")
        print("Waitless ensured UI was ready before each action.")
        return True
        
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False
        
    finally:
        time.sleep(2)  # Pause to see result
        driver.quit()


# ═══════════════════════════════════════════════════════════════════════════
# COMPARISON DEMO
# ═══════════════════════════════════════════════════════════════════════════

def run_comparison():
    """Run both tests to demonstrate the difference."""
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " WAITLESS DEMO: Flaky → Stable ".center(58) + "║")
    print("║" + " Testing: www.dhirajdas.dev ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    print("\nThis demo shows how the same test can be:")
    print("  1. FLAKY without waitless (racing against animations)")
    print("  2. STABLE with waitless (waiting for true UI stability)")
    
    input("\n[Press Enter to run the FLAKY test first...]")
    
    result1 = test_without_waitless()
    
    input("\n[Press Enter to run the STABLE test...]")
    
    result2 = test_with_waitless()
    
    # Summary
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " DEMO SUMMARY ".center(58) + "║")
    print("╠" + "═" * 58 + "╣")
    print("║" + f" Without Waitless: {'FLAKY (race conditions)' if not result1 else 'Lucky pass':<36}" + "║")
    print("║" + f" With Waitless:    {'STABLE (deterministic)' if result2 else 'Failed':<36}" + "║")
    print("╠" + "═" * 58 + "╣")
    print("║" + " Key Difference: ".ljust(58) + "║")
    print("║" + " Waitless monitors DOM, Network, and Animations ".ljust(58) + "║")
    print("║" + " to ensure TRUE stability before each interaction ".ljust(58) + "║")
    print("╚" + "═" * 58 + "╝")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--flaky":
            test_without_waitless()
        elif sys.argv[1] == "--stable":
            test_with_waitless()
        else:
            print("Usage: python demo_flaky_to_stable.py [--flaky|--stable]")
    else:
        run_comparison()
