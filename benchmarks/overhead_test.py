"""
Performance overhead test for Waitless instrumentation.

Measures the overhead of:
1. JavaScript instrumentation injection
2. Per-poll status check
3. Total stabilization time
"""

import time
import json
import statistics
from typing import Dict, List, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


def measure_injection_time(driver, script: str, iterations: int = 10) -> Dict[str, float]:
    """Measure time to inject instrumentation script."""
    times = []
    
    for _ in range(iterations):
        driver.get("about:blank")
        start = time.perf_counter()
        driver.execute_script(script)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    
    return {
        'mean_ms': statistics.mean(times),
        'median_ms': statistics.median(times),
        'stdev_ms': statistics.stdev(times) if len(times) > 1 else 0,
        'min_ms': min(times),
        'max_ms': max(times),
        'samples': len(times),
    }


def measure_poll_overhead(driver, iterations: int = 100) -> Dict[str, float]:
    """Measure time for each status poll."""
    # Inject instrumentation first
    from waitless.instrumentation import INSTRUMENTATION_SCRIPT, GET_STATUS_SCRIPT
    
    driver.get("about:blank")
    driver.execute_script(INSTRUMENTATION_SCRIPT)
    
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        driver.execute_script(GET_STATUS_SCRIPT)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    
    return {
        'mean_ms': statistics.mean(times),
        'median_ms': statistics.median(times),
        'stdev_ms': statistics.stdev(times) if len(times) > 1 else 0,
        'min_ms': min(times),
        'max_ms': max(times),
        'samples': len(times),
    }


def measure_stabilization_time(driver, url: str, iterations: int = 5) -> Dict[str, float]:
    """Measure total stabilization time on a real page."""
    from waitless import stabilize, StabilizationConfig
    
    config = StabilizationConfig(timeout=30, debug_mode=False)
    stabilized_driver = stabilize(driver, config=config)
    
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        stabilized_driver.get(url)
        # Stabilization happens automatically on navigation
        end = time.perf_counter()
        times.append((end - start) * 1000)
    
    return {
        'mean_ms': statistics.mean(times),
        'median_ms': statistics.median(times),
        'stdev_ms': statistics.stdev(times) if len(times) > 1 else 0,
        'min_ms': min(times),
        'max_ms': max(times),
        'samples': len(times),
    }


def run_all_benchmarks(output_file: str = None) -> Dict[str, Any]:
    """Run all benchmarks and optionally save results."""
    from waitless.instrumentation import INSTRUMENTATION_SCRIPT
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'benchmarks': {}
        }
        
        print("Measuring injection overhead...")
        results['benchmarks']['injection'] = measure_injection_time(
            driver, INSTRUMENTATION_SCRIPT
        )
        print(f"  Mean: {results['benchmarks']['injection']['mean_ms']:.2f}ms")
        
        print("Measuring poll overhead...")
        results['benchmarks']['poll'] = measure_poll_overhead(driver)
        print(f"  Mean: {results['benchmarks']['poll']['mean_ms']:.2f}ms")
        
        print("Measuring stabilization on blank page...")
        results['benchmarks']['stabilization_blank'] = measure_stabilization_time(
            driver, "about:blank", iterations=3
        )
        print(f"  Mean: {results['benchmarks']['stabilization_blank']['mean_ms']:.2f}ms")
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {output_file}")
        
        return results
        
    finally:
        driver.quit()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Waitless performance benchmarks')
    parser.add_argument('--output', '-o', help='Output file for JSON results')
    args = parser.parse_args()
    
    results = run_all_benchmarks(args.output)
    
    print("\n" + "="*50)
    print("BENCHMARK SUMMARY")
    print("="*50)
    print(f"Injection: {results['benchmarks']['injection']['mean_ms']:.2f}ms (median: {results['benchmarks']['injection']['median_ms']:.2f}ms)")
    print(f"Poll:      {results['benchmarks']['poll']['mean_ms']:.2f}ms (median: {results['benchmarks']['poll']['median_ms']:.2f}ms)")
    print(f"Stable:    {results['benchmarks']['stabilization_blank']['mean_ms']:.2f}ms (median: {results['benchmarks']['stabilization_blank']['median_ms']:.2f}ms)")
    print("="*50)
