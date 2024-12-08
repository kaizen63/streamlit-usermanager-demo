#!/bin/bash

docker compose -f docker-compose.yml up --build -d
sleep 1
open http://localhost:18501?debug=1


