# Waitless

[![PyPI version](https://img.shields.io/pypi/v/waitless.svg)](https://pypi.org/project/waitless/)
[![Python versions](https://img.shields.io/pypi/pyversions/waitless.svg)](https://pypi.org/project/waitless/)
[![License: MIT](https://img.shields.io/pypi/l/waitless.svg)](https://github.com/godhiraj-code/waitless/blob/main/LICENSE)
[![CI](https://github.com/godhiraj-code/waitless/actions/workflows/ci.yml/badge.svg)](https://github.com/godhiraj-code/waitless/actions/workflows/ci.yml)

**Stop flaky Selenium tests caused by clicking before the page is ready.** Waitless wraps your WebDriver so `get`, `find_element` and `click` wait for the DOM and network to settle (and, in strict mode, for animations and layout too): no `time.sleep()`, less `WebDriverWait` boilerplate, and fewer `StaleElementReferenceException`, `ElementClickInterceptedException` and `NoSuchElementException` failures caused by timing races.

**Automatic UI stabilization for Selenium.** Reduce explicit waits and sleeps by automatically evaluating multiple UI stability signals.

**Learn more:** [Waitless v1: the end of flaky tests](https://www.dhirajdas.dev/blog/waitless-v1-end-of-flaky-tests) · [Eliminating flaky tests with Waitless](https://www.dhirajdas.dev/blog/waitless-eliminate-flaky-tests) · [Project page](https://www.dhirajdas.dev/project/waitless) · [Follow @dkkkkd on X](https://x.com/dkkkkd)

## Installation

```bash
pip install waitless
```

## Quick Start

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from waitless import stabilize

driver = webdriver.Chrome()
driver = stabilize(driver)

# Navigation, lookups, and common element actions now wait for stability.
driver.get(
    "data:text/html,<input id='username'><button id='login-button'>Log in</button>"
)
driver.find_element(By.ID, "username").send_keys("user")
driver.find_element(By.ID, "login-button").click()
driver.quit()
```

## Why Waitless?

### The Problem

Automation tests fail because interactions happen while the UI is still changing:

- DOM mutations from React/Vue/Angular updates
- In-flight AJAX requests
- CSS animations and transitions
- Layout shifts from lazy-loaded content

### Traditional Solutions (and why they fail)

| Approach | Problem |
|----------|---------|
| `time.sleep(2)` | Too slow, still fails sometimes |
| `driver.implicitly_wait(10)` | Only retries element lookup until the element exists; it does not wait for pending requests, animations or DOM churn |
| `WebDriverWait` | Requires an explicit condition at each synchronization point |
| Retries | Masks the real problem, adds flakiness |

### The Waitless Solution

Waitless evaluates page-level stability signals:

- DOM mutation activity (MutationObserver, including **Shadow DOM**)
- Pending network requests (XHR/fetch interception after instrumentation is installed)
- CSS animations and transitions
- Layout stability for interactive elements
- WebSocket/SSE activity (opt-in)
- Framework hooks (React/Angular/Vue, opt-in)
- Same-origin iframe load readiness (opt-in; not full child-frame signal injection)

Before supported interactions, Waitless polls until the enabled mandatory signals
meet their configured thresholds.

## When to use Waitless (and when not to)

**Good fit:**

- Selenium 4 test suites in Python, on single-page apps (React, Angular, Vue) where clicks land while the page is still re-rendering
- Pages with AJAX/fetch calls, lazy-loaded content or long-polling that make tests pass locally and fail in CI
- Suites full of `time.sleep()` calls or copy-pasted `WebDriverWait` boilerplate that you want to remove

**Not a good fit:**

- **Playwright.** Playwright already auto-waits for elements to be actionable, and Waitless only supports Selenium.
- **Specific business conditions.** If a test must wait for "the order status says Shipped", keep a `WebDriverWait` with an explicit condition for that. Waitless waits for the page to be *stable*, not for your app to reach a particular state. The two work well together.
- **Async Selenium clients or Service Worker traffic.** See [Current Limitations](#current-limitations).

| | `time.sleep` | `implicitly_wait` | `WebDriverWait` | Waitless |
|---|---|---|---|---|
| Waits for element presence | No (fixed delay) | Yes | Yes (per condition) | Yes (`find_element` retries until timeout) |
| Waits for pending XHR/fetch | No | No | Only if you write the condition | Yes |
| Waits for DOM mutations to settle | No | No | Only if you write the condition | Yes |
| Waits for animations/layout | No | No | Only if you write the condition | Strict mode |
| Code needed per interaction | One sleep | None | One condition | None after `stabilize(driver)` |

## Configuration

```python
from waitless import stabilize, StabilizationConfig

config = StabilizationConfig(
    timeout=10,                    # Max wait time (seconds)
    mutation_rate_threshold=50,    # mutations/sec considered stable (allows animations)
    network_idle_threshold=0,      # Wait for all tracked XHR/fetch requests
    animation_detection=True,      # Track CSS animations (non-blocking in normal mode)
    strictness='normal',           # 'strict' | 'normal' | 'relaxed'
    debug_mode=True                # Enable logging
)

driver = stabilize(driver, config=config)
```

### Strictness Levels

| Level | What It Waits For |
|-------|-------------------|
| `strict` | DOM + Network + Animations + Layout |
| `normal` | DOM + Network (default) |
| `relaxed` | DOM only |

### Factory Methods

```python
# For strict testing
config = StabilizationConfig.strict()

# For apps with background traffic
config = StabilizationConfig.relaxed()

# For CI environments
config = StabilizationConfig.ci()
```

## Manual Stabilization

If you don't want to wrap the driver:

```python
from waitless import wait_for_stability

wait_for_stability(driver)
driver.find_element(By.ID, "button").click()
```

## Disabling Stabilization

```python
from waitless import unstabilize

driver = unstabilize(driver)  # Back to original behavior
```

## Diagnostics

When tests fail, get detailed analysis:

```python
from waitless import get_diagnostics, StabilizationTimeout
from waitless.diagnostics import print_report

try:
    driver.find_element(By.ID, "slow-button").click()
except StabilizationTimeout as e:
    diagnostics = get_diagnostics(driver)
    print_report(diagnostics)  # Print detailed report
```

### CLI Doctor Command

```bash
python -m waitless doctor --file diagnostics.json
```

Sample output:
```
+--------------------------------------------------------------------+
|                     WAITLESS STABILITY REPORT                      |
+--------------------------------------------------------------------+
| BLOCKING FACTORS:                                                  |
|   [!] NETWORK: 2 request(s) still pending                          |
|   -> GET /api/users                                                |
|   [!] ANIMATIONS: 1 active animation(s)                            |
+--------------------------------------------------------------------+
| SUGGESTIONS:                                                       |
|   1. Set network_idle_threshold=2 for background traffic           |
|   2. Use animation_detection=False for infinite spinners           |
+--------------------------------------------------------------------+
```

## Important Notes

### Network Threshold Warning

The default and `StabilizationConfig.strict()` use `network_idle_threshold=0`,
so all tracked XHR/fetch requests must finish before the network is considered
idle. This prevents a delayed response from leaving a loading overlay in place
when an interaction starts. Set `network_idle_threshold=2` to allow up to two
requests to remain pending for background analytics or polling.

Many apps have background traffic that never stops:
- Analytics calls
- Long polling
- Feature flags
- WebSocket heartbeats

If known background traffic exceeds the default, raise the threshold carefully:
```python
config = StabilizationConfig(network_idle_threshold=3)
```

### Wrapped Elements

The stabilized driver returns wrapped elements that auto-wait before `click()`,
`send_keys()`, `submit()`, and `clear()`. They behave like WebElements but:

- `isinstance(element, WebElement)` returns `False`
- Use `.unwrap()` to get the original element if needed

```python
element = driver.find_element(By.ID, "button")
original = element.unwrap()  # Gets the real WebElement
```

## Optional Signals

- **WebSocket/SSE Awareness** - Track WebSocket and Server-Sent Events activity
- **Framework Adapters** - React, Angular, Vue hooks for framework-specific settling
- **iframe Support** - Monitor same-origin iframes
- **Performance benchmarks** - Run the repository benchmark against your environment

```python
config = StabilizationConfig(
    track_websocket=True,         # WebSocket monitoring
    track_sse=True,               # SSE monitoring
    framework_hooks=['react'],    # React adapter
    track_iframes=True,           # iframe monitoring
)
```

## Performance

| Metric | Typical Value |
|--------|---------------|
| Instrumentation injection | Environment-dependent; from a repository checkout, run `python benchmarks/overhead_test.py` |
| Per-poll overhead | Environment-dependent; run the repository benchmark |
| Poll interval (default) | 50ms |
| Stabilization time | Depends on page activity, thresholds, and environment |

### Navigation Handling

Wrapped `get()`, `refresh()`, `back()`, and `forward()` wait after Selenium's
synchronous navigation call returns. For SPA route changes initiated by page
JavaScript, Waitless validates/re-injects instrumentation on the next wait:

1. Checks `__waitless__.isAlive()` before each wait
2. Detects URL changes via `driver.current_url`
3. Re-injects if instrumentation is missing

This does not observe routes continuously, and cross-origin iframe internals remain
outside the browser same-origin boundary.

Because instrumentation is installed after Selenium's synchronous navigation call
returns, requests that start and finish during navigation are not observed. Requests
started after instrumentation is installed are tracked.

`find_elements()` keeps Selenium's immediate-empty lookup semantics: after the
page-stability wait, it performs one lookup and returns `[]` when there are no matches.
By contrast, `find_element()` retries `NoSuchElementException` until the configured
timeout after the page-stability wait.

## Current Limitations

- **Selenium only** - No Playwright integration
- **Sync only** - No async/await support yet
- **No Service Workers** - SW network requests not intercepted

See [CHANGELOG.md](https://github.com/godhiraj-code/waitless/blob/main/CHANGELOG.md) for version history.

## FAQ and Troubleshooting

**Does it work with pytest?**
Yes. Waitless has no runner dependency; wrap the driver in your fixture:

```python
import pytest
from selenium import webdriver
from waitless import stabilize

@pytest.fixture
def driver():
    d = stabilize(webdriver.Chrome())
    yield d
    d.quit()
```

**Does it work with Shadow DOM?**
Yes, for open shadow roots. The MutationObserver also watches open shadow roots, and elements and shadow roots returned from searches are wrapped so they auto-wait too. Closed shadow roots are not visible to page JavaScript, so they are not observed.

**Does it work with SeleniumBase or other wrappers?**
It isn't tested against SeleniumBase in this repository. `stabilize()` accepts any WebDriver-like object that has `execute_script`, `find_element` and `current_url`, so you can wrap the underlying Selenium driver. If a framework needs a real `WebDriver` instance, pass it `driver.unwrapped`.

**My app has WebSockets, analytics beacons or long polling and never goes idle. I get `StabilizationTimeout`.**
Run the diagnostics (see [Diagnostics](#diagnostics)) to see which signal is blocking. WebSocket/SSE tracking is off by default, so it doesn't block unless you enable it. For background XHR/fetch traffic, raise `network_idle_threshold` or use `StabilizationConfig.relaxed()` (DOM only). For infinite spinners, set `animation_detection=False`.

**How much slower does it make my tests?**
Waitless polls every 50 ms (`poll_interval`) and returns as soon as the enabled signals are stable, after a 0.1 s DOM quiet period (`dom_settle_time`). On a settled page that's a short pause per interaction; on a busy page it waits as long as the page is busy, up to `timeout` (10 s by default). Measure it in your environment with `python benchmarks/overhead_test.py` from a repository checkout.

**`isinstance(element, WebElement)` is `False`.**
That's expected: the stabilized driver returns wrapped elements. Call `.unwrap()` on an element, or use `driver.unwrapped` for the original driver. See [Wrapped Elements](#wrapped-elements).

## API Reference

### Functions

| Function | Description |
|----------|-------------|
| `stabilize(driver, config=None)` | Enable auto-stabilization |
| `unstabilize(driver)` | Disable and return original driver |
| `wait_for_stability(driver, timeout=None)` | Manual one-time wait |
| `get_diagnostics(driver)` | Get diagnostic data |

### Classes

| Class | Description |
|-------|-------------|
| `StabilizationConfig` | Configuration options |
| `StabilizedWebDriver` | Wrapped driver with auto-wait |
| `StabilizedWebElement` | Wrapped element with auto-wait |
| `StabilizationTimeout` | Exception when UI doesn't stabilize |

## License

MIT. See [LICENSE](https://github.com/godhiraj-code/waitless/blob/main/LICENSE).
