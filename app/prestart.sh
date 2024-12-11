#!/bin/bash
set -euo pipefail
echo Environment: "${ENV:-dev}"

if [ -f ./.streamlit/config."${ENV:-dev}".toml ]; then
  echo "Copy ./.streamlit/config."${ENV:-dev}".toml to ./.streamlit/config.toml"
  cp ./.streamlit/config."${ENV:-dev}".toml ./.streamlit/config.toml
fi
