"""Regression tests for the Selenium wrapper boundary."""

import weakref
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import waitless.selenium_integration as selenium_integration
from waitless.selenium_integration import (
    SeleniumIntegration,
    StabilizedWebDriver,
    StabilizedWebElement,
)


class FakeWebElement:
    def __init__(self):
        self.find_element = Mock()
        self.find_elements = Mock()


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
        config=SimpleNamespace(debug_mode=False),
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
    assert engine.wait_for_stability.call_count == 2


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
    engine.wait_for_stability.assert_called_once_with()


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
