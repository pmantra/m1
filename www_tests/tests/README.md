# Adding new tests

The main decision is whether or not to add a new method to an existing class or to add a new class altogether. The main difference is that a new class will start a new session with all configured browsers, so will be slower & more expensive to run. Only do that when it makes sense.

For a list of all the supported options on browserstack use: `curl -u "username:api_key" https://www.browserstack.com/automate/browsers.json`

The most important docs for testing so far seem to be: https://selenium-python.readthedocs.io/locating-elements.html. selenium-python (https://github.com/SeleniumHQ/Selenium) is the library that powers our selenium tests.

# Running locally (not on gitlab)

1. build the docker container e.g. `docker build -t www_tests .` from the `www_tests` directory
2. `docker run --rm -e DEBUG=True -v YOUR_REPO_PATH:/maven -e BROWSERSTACK_PASSWORD=API_KEY_HERE www_tests python /maven/main.py`. Optional test names can be put at the end of the command, but see the note at the bottom of main.py for more info on that.

# Debugging

- There is `ipython` in the container for a python shell. The `debug.py` file is a place to put debug helpers, right now there's a function that'll give you a chrome browser on browserstack to test things.
- If you exit running tests using `ctrl-c`, then make sure to stop the session in the browserstack UI, or we will pay $$$ until it times out.
