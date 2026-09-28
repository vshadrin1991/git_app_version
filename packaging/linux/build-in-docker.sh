#!/usr/bin/env bash
# Builds the amd64 .deb inside Ubuntu 22.04. build/ and dist/ end up owned by root; remove them with sudo.
set -euo pipefail
cd "$(dirname "$0")/../.."
docker run --rm --platform linux/amd64 -v "$PWD":/src -w /src ubuntu:22.04 bash -euxc '
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip git binutils \
    libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3 libfontconfig1
  python3 -m venv /tmp/venv && . /tmp/venv/bin/activate
  pip install -e ".[dev]"
  packaging/linux/build-deb.sh
'
