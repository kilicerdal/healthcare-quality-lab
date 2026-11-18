#!/bin/sh
set -eu
umask 077
: "${HQL_RUNNER_TOKEN:?Missing ephemeral registration token}"
: "${HQL_RUNNER_LABEL:?Missing unique job label}"
: "${HQL_RUNNER_NAME:?Missing unique runner name}"
: "${HQL_OLLAMA_HOST:?Missing verified VM-to-host bridge}"
socat TCP-LISTEN:11434,bind=127.0.0.1,reuseaddr,fork "TCP:${HQL_OLLAMA_HOST}:11434" &
relay=$!
trap 'kill "$relay" 2>/dev/null || true' EXIT INT TERM
./config.sh --unattended --ephemeral --disableupdate --url https://github.com/kilicerdal/healthcare-quality-lab --token "$HQL_RUNNER_TOKEN" --name "$HQL_RUNNER_NAME" --labels "$HQL_RUNNER_LABEL" --work _work
unset HQL_RUNNER_TOKEN
./run.sh
