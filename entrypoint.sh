#!/bin/sh
set -e

# Default to localhost if GEMINI_HOSTNAME is not set
HOSTNAME="${GEMINI_HOSTNAME:-localhost}"

echo "Starting Agate with hostname: ${HOSTNAME}"

exec agate --content content/ --certs certs/ --hostname "${HOSTNAME}" "$@"
