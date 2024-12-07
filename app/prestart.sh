#!/bin/bash
set -euo pipefail
echo Environment: "${ENV}"

if [ -f ./.streamlit/config.${ENV}.toml ]; then
  echo "Copy ./.streamlit/config.${ENV}.toml to ./.streamlit/config.toml"
  cp ./.streamlit/config.${ENV}.toml ./.streamlit/config.toml
fi
