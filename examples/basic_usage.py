"""
Example: Basic waitless usage with Selenium.

This demonstrates the one-line integration for automatic stabilization.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# One-line import
from waitless import stabilize, StabilizationConfig


def main():
    # Setup Chrome
    options = Options()
    options.add_argument("--headless")  # Optional: run headless
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Enable stabilization - ONE LINE
        driver = stabilize(driver)
        
        # Now all interactions auto-wait for stability
        driver.get("https://example.com")
        
        # This click will automatically wait for:
        # - All network requests to complete
        # - DOM to stop mutating
        # - Animations to finish
        heading = driver.find_element(By.TAG_NAME, "h1")
        print(f"Page title: {heading.text}")
        
        # More interactions...
        links = driver.find_elements(By.TAG_NAME, "a")
        print(f"Found {len(links)} links")
        
        if links:
            # This also auto-waits
            links[0].click()
        
        print("Success! All interactions stabilized automatically.")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
