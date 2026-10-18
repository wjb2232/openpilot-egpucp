#!/usr/bin/env bash

export API_HOST=https://api.konik.ai
export ATHENA_HOST=wss://athena.konik.ai
export HTTPS_PROXY=http://192.168.1.129:7897
export HTTP_PROXY=http://192.168.1.129:7897
exec ./launch_chffrplus.sh
