# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2025-12-26

### Added
- **Shadow DOM support** - `MutationObserver` now recursively tracks changes inside shadow roots.
- **Improved stability detection** - Fixed a bug where quiet time was ignored when mutation rate was low.
- **Shadow DOM integration tests** - New test fixture and integration tests for shadow DOM scenarios.

---

## [0.3.0] - 2025-12-25

### Added
- **Input validation** - `stabilize()` now raises clear `TypeError` when invalid drivers are passed
- **Comprehensive test coverage** - New tests for `diagnostics.py` and `instrumentation.py` modules
- **Dynamic site support** - Demo updated with `relaxed` mode for highly animated websites

### Changed
- **Exception handling** - Replaced broad `except Exception` with specific Selenium exceptions (`WebDriverException`, `JavascriptException`, `NoSuchWindowException`)
- **Debug logging** - Exception handlers now log details when debug mode is enabled
- **Homepage URL** - Updated to `www.dhirajdas.dev`

### Fixed
- **Integration tests** - Removed all `time.sleep()` calls, now using proper waitless mechanisms
- **Config test** - Fixed `network_idle_threshold` assertion to match actual default of `2`

---

## [0.2.0] - 2025-12-24

### Added
- **Mutation rate detection** - Uses 50 mutations/sec threshold instead of absolute DOM silence
- **Auto-retry find_element** - Elements found automatically when they appear, no `WebDriverWait` needed
- **Non-blocking animations** - CSS animations don't block in `normal` mode
- **Enhanced diagnostics** - Shows `mutation_rate`, `pending_requests`, `active_animations`

### Changed
- Default `network_idle_threshold` set to `2` to allow background traffic

---

## [0.1.0] - 2025-12-23

### Added
- Initial release
- Core stabilization engine with JavaScript instrumentation
- `stabilize()` / `unstabilize()` / `wait_for_stability()` API
- `StabilizationConfig` with configurable thresholds
- Strictness levels: `strict`, `normal`, `relaxed`
- Factory methods: `StabilizationConfig.strict()`, `.relaxed()`, `.ci()`
- Diagnostic reporting with `waitless doctor` CLI
- `StabilizedWebDriver` and `StabilizedWebElement` wrappers
