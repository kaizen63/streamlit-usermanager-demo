#!/bin/bash

docker compose -f docker-compose.yml --progress=plain up --build -d \
&& sleep 1 \
&& open http://localhost:18501?debug=1


