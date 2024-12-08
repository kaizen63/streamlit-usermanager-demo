#!/bin/bash

docker compose -f docker-compose.yml \
    --progress=plain build  && echo "Image successfully created"
