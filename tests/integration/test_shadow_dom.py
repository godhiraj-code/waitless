"""
Integration tests for Shadow DOM support.
"""

import time
import pytest
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from waitless import stabilize, StabilizationConfig, wait_for_stability

# Path to test fixture
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "shadow_dom_page.html"
FIXTURE_URL = f"file:///{FIXTURE_PATH.absolute().as_posix()}"

@pytest.fixture
def driver():
    """Create a Chrome driver for testing."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()

class TestShadowDOM:
    """Tests for Shadow DOM stability detection."""
    
    def test_waits_for_shadow_mutations(self, driver):
        """Test that waitless correctly detects mutations inside Shadow DOM."""
        config = StabilizationConfig(timeout=5, dom_settle_time=0.3)
        stable_driver = stabilize(driver, config=config)
        
        stable_driver.get(FIXTURE_URL)
        
        # Trigger shadow DOM mutations
        btn = stable_driver.find_element("id", "trigger-btn")
        btn.click()
        
        # Use wait_for_stability and then verify the 'shadow-complete' element exists in shadow root
        start_time = time.time()
        
        # We poll until shadow-complete is found, using wait_for_stability in each loop
        found = False
        while (time.time() - start_time) < 5:
            wait_for_stability(driver)
            
            # Check if complete via JS
            is_complete = driver.execute_script("""
                const host = document.getElementById('shadow-host');
                if (!host || !host.shadowRoot) return false;
                return host.shadowRoot.getElementById('shadow-complete') !== null;
            """)
            if is_complete:
                found = True
                break
            time.sleep(0.1)
            
        duration = time.time() - start_time
        assert found, "Shadow DOM mutations did not complete within timeout"
        assert duration > 0.4, f"Should have waited for mutations, but only waited {duration:.2f}s"
