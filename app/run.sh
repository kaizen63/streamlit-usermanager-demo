#!/bin/bash
set -euo pipefail

# If there's a prestart.sh script in the /app directory or other path specified, run it before starting
PRE_START_PATH=${PRE_START_PATH:-/app/prestart.sh}
echo "Checking for script in $PRE_START_PATH"
if [ -f "$PRE_START_PATH" ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else
    echo "There is no script $PRE_START_PATH"
fi

# Streamlit Settings
export STREAMLIT_LOGGER_LEVEL=${STREAMLIT_LOGGER_LEVEL:-INFO}
export STREAMLIT_LOGGER_MESSAGE_FORMAT=${STREAMLIT_LOGGER_MESSAGE_FORMAT:-"%(asctime)s %(levelname)s [%(name)s] [%(process)d] - %(message)s"}
export STREAMLIT_SERVER_FOLDER_WATCH_BLACKLIST='["/app/logs", "./logs"]'
export STREAMLIT_SERVER_FILE_WATCHER_TYPE=${STREAMLIT_SERVER_FILE_WATCHER_TYPE:-"none"}
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Metadata UI settings
export LOGGING_CONFIG=${LOGGING_CONFIG:-"log-config/logging-conf.prod.yaml"}
export LOGGING_LOG_LEVEL=${LOGGING_LOG_LEVEL:-INFO}

# run streamlit
exec streamlit run --server.headless true  --client.toolbarMode minimal ./app.py
