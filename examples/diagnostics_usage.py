"""
Example: Using diagnostics for debugging flaky tests.

Shows how to capture and analyze stability issues.
"""

import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from waitless import (
    stabilize,
    get_diagnostics,
    StabilizationConfig,
    StabilizationTimeout,
)
from waitless.diagnostics import print_report, generate_report


def example_capture_on_failure():
    """
    Capture diagnostics when a test fails due to timeout.
    """
    config = StabilizationConfig(
        timeout=5.0,
        debug_mode=True,
    )
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=config)
    
    try:
        driver.get("https://example.com")
        
        # Simulate interaction that might timeout
        try:
            driver.find_element(By.ID, "slow-button").click()
        except StabilizationTimeout as e:
            # Get detailed diagnostics
            print("Stabilization failed!")
            print(e.get_diagnostic_summary())
            
            # Also available as structured data
            diagnostics = get_diagnostics(driver)
            print("\nBlocking factors:", diagnostics.get('blocking_factors'))
            
            # Save for CI analysis
            with open('test_failure_diagnostics.json', 'w') as f:
                json.dump(diagnostics, f, indent=2)
            
            raise
            
    finally:
        driver.quit()


def example_generate_report():
    """
    Generate a full diagnostic report.
    """
    config = StabilizationConfig(timeout=5.0)
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=config)
    
    try:
        driver.get("https://example.com")
        driver.find_element(By.TAG_NAME, "h1")  # Trigger stabilization
        
        # Get diagnostics even on success
        diagnostics = get_diagnostics(driver)
        
        if diagnostics:
            from waitless.diagnostics import DiagnosticReport
            report = DiagnosticReport(diagnostics)
            
            # Print text report
            print(report.generate_text_report())
            
            # Export as JSON
            print("\nJSON export:")
            print(report.to_json())
            
    finally:
        driver.quit()


def example_pytest_integration():
    """
    Example pytest fixture for automatic diagnostics.
    
    Add this to conftest.py:
    
    ```python
    import pytest
    from waitless import stabilize, get_diagnostics
    from waitless.diagnostics import DiagnosticReport
    
    @pytest.fixture
    def stabilized_driver(request):
        driver = webdriver.Chrome()
        driver = stabilize(driver)
        
        yield driver
        
        # Capture diagnostics on failure
        if request.node.rep_call.failed:
            diagnostics = get_diagnostics(driver)
            if diagnostics:
                report = DiagnosticReport(diagnostics)
                # Attach to test report
                allure.attach(
                    report.generate_text_report(),
                    name="stabilization_report",
                    attachment_type=allure.attachment_type.TEXT
                )
        
        driver.quit()
    ```
    """
    pass


if __name__ == "__main__":
    print("Running diagnostic capture example...")
    try:
        example_generate_report()
    except Exception as e:
        print(f"Example failed (expected): {e}")
