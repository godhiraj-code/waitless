"""Regression tests for the Selenium wrapper boundary."""

import weakref
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException, TimeoutException,
)

import waitless.selenium_integration as selenium_integration
from waitless.selenium_integration import (
    SeleniumIntegration,
    StabilizedWebDriver,
    StabilizedWebElement,
)


class FakeWebElement:
    def __init__(self):
        self.tag_name = "button"
        self.text = "Apple"
        self.attributes = {}
        self.get_attribute = Mock(side_effect=self.attributes.get)
        self.find_element = Mock()
        self.find_elements = Mock()
        self.click = Mock()
        self.is_enabled = Mock(return_value=True)


class FakeDriver:
    current_url = "https://example.test/"

    def __init__(self):
        self.execute_script = Mock()
        self.execute_async_script = Mock()
        self.find_element = Mock()


@pytest.fixture
def engine():
    return SimpleNamespace(
        wait_for_stability=Mock(),
        teardown=Mock(),
        config=SimpleNamespace(debug_mode=False, timeout=0.1, poll_interval=0.01),
    )


@pytest.fixture(autouse=True)
def recognize_fake_web_elements(monkeypatch):
    monkeypatch.setattr(
        selenium_integration,
        "SeleniumWebElement",
        FakeWebElement,
    )


@pytest.mark.parametrize("method_name", ["execute_script", "execute_async_script"])
def test_script_calls_unwrap_nested_arguments_and_wrap_nested_results(
    method_name,
    engine,
):
    raw_argument = FakeWebElement()
    raw_result = FakeWebElement()
    driver = FakeDriver()
    method = getattr(driver, method_name)
    method.return_value = {
        "items": [raw_result, ("unchanged", raw_result)],
    }
    wrapped_driver = StabilizedWebDriver(driver, engine)
    wrapped_argument = StabilizedWebElement(raw_argument, engine)

    result = getattr(wrapped_driver, method_name)(
        "return arguments[0]",
        {"items": [wrapped_argument, (wrapped_argument,)]},
    )

    method.assert_called_once_with(
        "return arguments[0]",
        {"items": [raw_argument, (raw_argument,)]},
    )
    assert isinstance(result["items"][0], StabilizedWebElement)
    assert result["items"][0].unwrap() is raw_result
    assert isinstance(result["items"][1][1], StabilizedWebElement)
    assert result["items"][1][1].unwrap() is raw_result


def test_descendant_element_lookups_stay_wrapped(engine):
    parent = FakeWebElement()
    child = FakeWebElement()
    children = [FakeWebElement(), FakeWebElement()]
    parent.find_element.return_value = child
    parent.find_elements.return_value = children
    wrapped_parent = StabilizedWebElement(parent, engine)

    wrapped_child = wrapped_parent.find_element("css selector", ".child")
    wrapped_children = wrapped_parent.find_elements("css selector", ".child")

    assert isinstance(wrapped_child, StabilizedWebElement)
    assert wrapped_child.unwrap() is child
    assert [item.unwrap() for item in wrapped_children] == children
    assert all(isinstance(item, StabilizedWebElement) for item in wrapped_children)
    assert engine.wait_for_stability.call_count == 3


def test_shadow_root_element_lookups_stay_wrapped(engine):
    parent = FakeWebElement()
    shadow_root = FakeWebElement()
    child = FakeWebElement()
    shadow_root.find_element.return_value = child
    parent.shadow_root = shadow_root

    wrapped_parent = StabilizedWebElement(parent, engine)
    wrapped_child = wrapped_parent.shadow_root.find_element("css selector", ".child")

    assert isinstance(wrapped_child, StabilizedWebElement)
    assert wrapped_child.unwrap() is child
    assert engine.wait_for_stability.call_count == 2


def test_shadow_root_is_unwrapped_in_script_arguments(engine):
    parent = FakeWebElement()
    shadow_root = FakeWebElement()
    parent.shadow_root = shadow_root
    driver = FakeDriver()
    driver.execute_script.return_value = True
    wrapped_driver = StabilizedWebDriver(driver, engine)
    wrapped_parent = StabilizedWebElement(parent, engine)

    result = wrapped_driver.execute_script(
        "return arguments[0] !== null;",
        {"root": wrapped_parent.shadow_root},
    )

    assert result is True
    driver.execute_script.assert_called_once_with(
        "return arguments[0] !== null;",
        {"root": shadow_root},
    )


def test_unstabilize_tears_down_engine_for_wrapped_driver(engine):
    driver = FakeDriver()
    wrapped = StabilizedWebDriver(driver, engine)
    integration = SeleniumIntegration()
    integration._wrapped_drivers[driver] = weakref.ref(wrapped)

    result = integration.unstabilize(wrapped)

    assert result is driver
    engine.teardown.assert_called_once_with()
    assert integration.is_stabilized(driver) is False


def test_unstabilize_tears_down_engine_for_original_driver(engine):
    driver = FakeDriver()
    wrapped = StabilizedWebDriver(driver, engine)
    integration = SeleniumIntegration()
    integration._wrapped_drivers[driver] = weakref.ref(wrapped)

    result = integration.unstabilize(driver)

    assert result is driver
    engine.teardown.assert_called_once_with()
    assert integration.is_stabilized(driver) is False


@pytest.mark.parametrize("context", ["driver", "element", "shadow_root"])
def test_find_element_refinds_after_settling_with_same_locator(engine, context):
    raw = FakeDriver() if context == "driver" else FakeWebElement()
    first, fresh = FakeWebElement(), FakeWebElement()
    events = []
    raw.find_element.side_effect = lambda *a, **kw: events.append("find") or (
        first if events.count("find") == 1 else fresh
    )
    engine.wait_for_stability.side_effect = lambda **kw: events.append("settle")
    if context == "driver":
        wrapped = StabilizedWebDriver(raw, engine)
    elif context == "element":
        wrapped = StabilizedWebElement(raw, engine)
    else:
        wrapped = selenium_integration._StabilizedSearchContext(raw, engine)

    result = wrapped.find_element(by="css selector", value="#button")

    assert result.unwrap() is fresh
    assert events == ["settle", "find", "settle", "find"]
    assert raw.find_element.call_count == 2
    for call in raw.find_element.call_args_list:
        assert call.kwargs == {"by": "css selector", "value": "#button"}


@pytest.mark.parametrize("stale_method", ["is_enabled", "click"])
def test_click_refinds_once_when_enabled_check_or_click_is_stale(engine, stale_method):
    first, fresh = FakeWebElement(), FakeWebElement()
    getattr(first, stale_method).side_effect = StaleElementReferenceException()
    refind = Mock(return_value=fresh)
    wrapped = StabilizedWebElement(first, engine, refind=refind)

    wrapped.click()

    refind.assert_called_once_with()
    fresh.click.assert_called_once_with()
    assert wrapped.unwrap() is fresh
    assert engine.wait_for_stability.call_count == 2


def test_click_does_not_retry_a_second_stale_failure(engine):
    first, fresh = FakeWebElement(), FakeWebElement()
    first.click.side_effect = StaleElementReferenceException()
    fresh.click.side_effect = StaleElementReferenceException()
    refind = Mock(return_value=fresh)

    with pytest.raises(StaleElementReferenceException):
        StabilizedWebElement(first, engine, refind=refind).click()

    refind.assert_called_once_with()
    first.click.assert_called_once_with()
    fresh.click.assert_called_once_with()


def test_click_without_locator_propagates_stale_failure(engine):
    element = FakeWebElement()
    element.click.side_effect = StaleElementReferenceException()

    with pytest.raises(StaleElementReferenceException):
        StabilizedWebElement(element, engine).click()

    element.click.assert_called_once_with()


def test_click_waits_until_enabled(engine):
    element = FakeWebElement()
    element.is_enabled.side_effect = [False, False, True]

    StabilizedWebElement(element, engine).click()

    assert element.is_enabled.call_count == 3
    element.click.assert_called_once_with()


def test_click_times_out_without_clicking_a_disabled_element(engine):
    element = FakeWebElement()
    element.is_enabled.return_value = False

    with pytest.raises(
        TimeoutException, match="Element <button> 'Apple' was not enabled after 0.1s",
    ):
        StabilizedWebElement(element, engine).click()

    element.click.assert_not_called()


@pytest.mark.parametrize("field", ["tag_name", "text", "id", "name", "data-testid", "aria-label"])
def test_stale_retry_refuses_changed_fingerprint(engine, field):
    first, replacement = FakeWebElement(), FakeWebElement()
    if field in ("tag_name", "text"):
        setattr(replacement, field, "different")
    else:
        first.attributes[field] = "apple"
        replacement.attributes[field] = "banana"
    first.is_enabled.side_effect = StaleElementReferenceException()
    wrapped = StabilizedWebElement(first, engine, refind=Mock(return_value=replacement))
    # The old element's attributes are no longer readable once it is stale.
    first.get_attribute.side_effect = StaleElementReferenceException()

    with pytest.raises(StaleElementReferenceException, match="Element changed; Waitless refused"):
        wrapped.click()

    first.click.assert_not_called()
    replacement.click.assert_not_called()


def test_stale_retry_settles_before_refinding(engine):
    first, replacement = FakeWebElement(), FakeWebElement()
    first.click.side_effect = StaleElementReferenceException()
    events = []
    engine.wait_for_stability.side_effect = lambda **kw: events.append("settle")
    refind = Mock(side_effect=lambda: events.append("refind") or replacement)

    StabilizedWebElement(first, engine, refind=refind).click()

    assert events == ["settle", "settle", "refind"]
    replacement.click.assert_called_once_with()


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(now=0.0)

    def advance(seconds):
        clock.now += seconds

    clock.advance = advance
    monkeypatch.setattr(selenium_integration, "time", SimpleNamespace(
        monotonic=lambda: clock.now, sleep=advance,
    ))
    return clock


def test_click_shares_deadline_across_stale_retry_and_enabled_wait(engine, clock):
    engine.config.timeout = 2.0
    engine.config.poll_interval = 0.3
    engine.wait_for_stability.side_effect = lambda **kw: clock.advance(0.6)
    first, replacement = FakeWebElement(), FakeWebElement()
    replacement.is_enabled.return_value = False

    def stale_click():
        clock.advance(0.5)
        raise StaleElementReferenceException()

    first.click.side_effect = stale_click
    wrapped = StabilizedWebElement(first, engine, refind=Mock(return_value=replacement))

    with pytest.raises(TimeoutException, match="was not enabled after 2.0s"):
        wrapped.click()

    assert clock.now == pytest.approx(2.0)
    assert [call.kwargs['timeout'] for call in engine.wait_for_stability.call_args_list] == pytest.approx([2.0, 0.9])
    replacement.click.assert_not_called()


@pytest.mark.parametrize("context", ["driver", "element", "shadow_root"])
def test_find_shares_deadline_across_both_settle_waits(engine, clock, context):
    engine.config.timeout = 2.0
    raw = FakeDriver() if context == "driver" else FakeWebElement()
    raw.find_element.return_value = FakeWebElement()
    if context == "driver":
        wrapped = StabilizedWebDriver(raw, engine)
    elif context == "element":
        wrapped = StabilizedWebElement(raw, engine)
    else:
        wrapped = selenium_integration._StabilizedSearchContext(raw, engine)

    def settle(timeout):
        clock.advance(min(1.2, timeout))

    engine.wait_for_stability.side_effect = settle
    with pytest.raises(NoSuchElementException, match="within 2.0s"):
        wrapped.find_element("id", "action")

    assert clock.now == pytest.approx(2.0)
    assert [call.kwargs['timeout'] for call in engine.wait_for_stability.call_args_list] == pytest.approx([2.0, 0.8])
    raw.find_element.assert_called_once_with("id", "action")


def test_find_missing_polling_uses_only_remaining_deadline(engine, clock):
    engine.config.timeout = 2.0
    engine.config.poll_interval = 0.3
    engine.wait_for_stability.side_effect = lambda **kw: clock.advance(1.5)
    raw = FakeDriver()
    raw.find_element.side_effect = NoSuchElementException()

    with pytest.raises(NoSuchElementException, match="within 2.0s"):
        StabilizedWebDriver(raw, engine).find_element("id", "absent")

    assert clock.now == pytest.approx(2.0)
    assert raw.find_element.call_count == 2
