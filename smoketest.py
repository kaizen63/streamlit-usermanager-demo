import time
import os
import sys
from subprocess import check_call
from urllib.request import urlopen

print("This smoketest should end without raising an exception within 3s")
env = os.environ.copy()
env["DB_ENGINE"] = "sqlite"
env["DB_DATABASE"] = ":memory:"
env["ENV"] = "dev"
env["STREAMLIT_LOGGER_LEVEL"] = "INFO"
env["STREAMLIT_LOGGER_MESSAGE_FORMAT"] = (
    "%(asctime)s %(levelname)s [%(name)s] [%(process)d] - %(message)s"
)
env["STREAMLIT_SERVER_FOLDER_WATCH_BLACKLIST"] = '["/app/logs", "./logs"]'
env["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
env["LOGGING_LOG_LEVEL"] = "INFO"
env["LOGGING_CONFIG"] = "log-config/logging-conf.yaml"
env["POLICY_TTL"] = "0"

CONTAINER_NAME = "smoketest"
CONTAINER_PORT = 18501
IMAGE_NAME = "stusermanagerdemo:0.1.0-final1"
try:
    exit_code = check_call(
        f"docker run --rm --name={CONTAINER_NAME} -p {CONTAINER_PORT}:8501 -d {IMAGE_NAME}".split(),
        env=env,
    )
except Exception as e:
    raise e
else:
    if exit_code != 0:
        print("Error starting container: {exit_code=")
        sys.exit(exit_code)
    # Wait for the server to start. A better implementation would
    # poll in a loop:
    print("Waiting for container to come up")
    time.sleep(3)
    # Check if the server started (it'll throw an exception if not):
    try:
        urlopen(f"http://localhost:{CONTAINER_PORT}").read()
    except Exception as e:
        print(f"Cannot connect to container: {e=}")
        sys.exit(0)
    else:
        health = (
            urlopen(f"http://localhost:{CONTAINER_PORT}/_stcore/health")
            .read()
            .decode("utf-8")
        )
        if health != "ok":
            raise ValueError(f"Unexpected health: {health}")
        else:
            print("Health OK. Smoketest successful")
    finally:
        try:
            exit_code = check_call(f"docker kill {CONTAINER_NAME}".split())
            if exit_code != 0:
                print(f"Cannot kill container {CONTAINER_NAME}")
                sys.exit(exit_code)
        except Exception as e:
            print(f"Failed to kill container {CONTAINER_NAME}")
