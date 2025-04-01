import os
import sys
import unittest

from selenium import webdriver

BROWSERSTACK_USERNAME = os.environ.get("BROWSERSTACK_USERNAME", "zach197")
BROWSERSTACK_PASSWORD = os.environ["BROWSERSTACK_PASSWORD"]

if os.environ.get("DEBUG") is not None:
    # when writing new tests just testing once is quicker/cheaper
    # if you run locally and mount the files like in the README, you can change
    # this on the fly locally and test on whatever you want
    CAPABILITIES_TO_TEST = [{"os": "OS X", "browser": "Chrome"}]
else:
    CAPABILITIES_TO_TEST = [
        {
            "os": "Windows",
            "os_version": "7",
            "browser": "IE",
            "browser_version": "11.0",
        },
        {
            "os": "Windows",
            "os_version": "7",
            "browser": "Chrome",
            "browser_version": "30",
        },
        {"os": "Windows", "browser": "Edge"},
        {"os": "Windows", "browser": "Chrome"},
        {"os": "OS X", "browser": "Chrome"},
        {"os": "Windows", "browser": "Firefox"},
        {"os": "OS X", "browser": "Firefox"},
        {"os": "OS X", "browser": "Safari"},
        {"os": "android", "device": "Google Nexus 5"},
        {"os": "ios", "device": "iPad Mini 4"},
    ]


def on_platforms(platforms):
    def decorator(base_class):
        module = sys.modules[base_class.__module__].__dict__
        for i, platform in enumerate(platforms):
            d = dict(base_class.__dict__)
            d["desired_capabilities"] = platform
            name = "%s_%s" % (base_class.__name__, i + 1)
            module[name] = type(name, (base_class,), d)

    return decorator


class WebFrontendTestCase(unittest.TestCase):
    desired_capabilities = None

    @classmethod
    def setUpClass(cls):
        if cls.desired_capabilities is None:
            raise Exception("Need capabilities to test!")

        cls.driver_url = "http://%s:%s@hub.browserstack.com:80/wd/hub" % (
            BROWSERSTACK_USERNAME,
            BROWSERSTACK_PASSWORD,
        )

        print("Adding driver for: %s" % cls.desired_capabilities)
        driver = webdriver.Remote(
            command_executor=cls.driver_url,
            desired_capabilities=cls.desired_capabilities,
        )
        driver.implicitly_wait(10)
        cls.driver = driver

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()


@on_platforms(CAPABILITIES_TO_TEST)
class SmokeTestCase(WebFrontendTestCase):
    def test_basic_dom_rendering(self):
        self.driver.get("https://www.qa.mvnctl.net")

        # will raise selenium.common.exceptions.NoSuchElementException
        # if failing
        self.driver.find_element_by_class_name("btn-cta")

    def test_login(self):
        self.driver.get("https://www.qa.mvnctl.net/login")

        # these are brittle - we should access by name or something
        _inputs = self.driver.find_elements_by_tag_name("input")
        _inputs[0].send_keys("test+authtests@mavenclinic.com")
        _inputs[1].send_keys("pass")

        # logs us in
        self.driver.find_element_by_class_name("btn-next").click()

        # will error if not present (e.g. on failed login)
        self.driver.find_element_by_class_name("dash-card")


if __name__ == "__main__":
    """
    to target a specific test, use DEBUG and classname_1, e.g.
    SmokeTestCase_1.test_name as the arg to this script
    needed due to on_platforms magic above.

    if this got too confusing, we could adjust the class naming scheme that
    uses enumerate above to be something else, and then the class names would
    be easier to reference. for now there's only 1 browser needed to be
    debugged at a time.
    """

    unittest.main()
