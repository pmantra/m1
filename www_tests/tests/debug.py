import os

from selenium import webdriver

BROWSERSTACK_USERNAME = os.environ.get("BROWSERSTACK_USERNAME", "zach197")
BROWSERSTACK_PASSWORD = os.environ["BROWSERSTACK_PASSWORD"]


def debug_driver(caps=None):
    caps = caps or {"os": "OS X", "browser": "Chrome"}
    driver_url = f"http://{BROWSERSTACK_USERNAME}:{BROWSERSTACK_PASSWORD}@hub.browserstack.com:80/wd/hub"
    driver = webdriver.Remote(command_executor=driver_url, desired_capabilities=caps)
    driver.implicitly_wait(10)

    return driver
