"""Real-browser regressions for delayed list redraws and loading overlays."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from waitless import StabilizationConfig, stabilize


PAGE = rb"""<!doctype html>
<html><body><div id="list"></div><output id="result"></output>
<script>
function render(generation) {
    document.querySelector('#list').outerHTML =
        '<div id="list"><button id="action" data-generation="' + generation +
        '" onclick="document.querySelector(\'#result\').textContent=\'clicked\'">' +
        'Click</button></div>';
}
function redraw() {
    return fetch('/delay').then(response => response.text()).then(() => render('fresh'));
}
function startList() {
    setTimeout(() => { render('initial'); redraw(); }, 150);
}
function startOverlay() {
    render('initial');
    document.querySelector('#action').disabled = true;
    const overlay = document.createElement('div');
    overlay.id = 'overlay';
    overlay.style = 'position:fixed;inset:0;z-index:10;background:#ddd';
    document.body.appendChild(overlay);
    fetch('/slow').then(response => response.text()).then(() => {
        overlay.remove();
        document.querySelector('#action').disabled = false;
    });
}
</script></body></html>"""


@pytest.fixture(scope="module")
def local_page():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/delay', '/slow'):
                time.sleep(0.5 if self.path == '/delay' else 1.5)
                body = b'ready'
            else:
                body = PAGE
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    browser = webdriver.Chrome(options=options)
    try:
        yield browser
    finally:
        browser.quit()


@pytest.mark.parametrize('strict', [False, True])
def test_find_returns_fresh_element_after_delayed_list_redraw(driver, local_page, strict):
    config = StabilizationConfig.strict() if strict else StabilizationConfig()
    wrapped = stabilize(driver, config=config)
    wrapped.get(local_page)
    driver.execute_script('startList()')

    button = wrapped.find_element(By.ID, 'action')

    assert button.get_attribute('data-generation') == 'fresh'
    button.click()
    assert driver.find_element(By.ID, 'result').text == 'clicked'


def test_click_recovers_when_list_is_replaced_after_find(driver, local_page):
    wrapped = stabilize(driver, config=StabilizationConfig.strict())
    wrapped.get(local_page)
    driver.execute_script("render('initial')")
    button = wrapped.find_element(By.ID, 'action')
    original_id = button.unwrap().id
    driver.execute_script('redraw()')

    button.click()

    assert button.unwrap().id != original_id
    assert button.get_attribute('data-generation') == 'fresh'
    assert driver.find_element(By.ID, 'result').text == 'clicked'


@pytest.mark.parametrize('mode', ['default', 'strict', 'background'])
def test_click_waits_for_disabled_button_and_delayed_fetch_overlay(driver, local_page, mode):
    config = StabilizationConfig.strict() if mode == 'strict' else StabilizationConfig()
    if mode == 'background':
        # Even when a caller permits pending requests, click must wait for enabled.
        config = config.with_overrides(network_idle_threshold=2)
    wrapped = stabilize(driver, config=config)
    wrapped.get(local_page)
    driver.execute_script('startOverlay()')

    wrapped.find_element(By.ID, 'action').click()

    assert driver.find_element(By.ID, 'result').text == 'clicked'
    assert driver.find_elements(By.ID, 'overlay') == []
    assert driver.execute_script('return window.__waitless__.pendingRequests') == 0
