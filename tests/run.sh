#!/bin/bash
# Unit tests.
#
# The package's own src/ is on the source path rather than being pulled in as a
# dependency, so that the suite can reach the modules gren.json does not expose.
set -e
cd "$(dirname "$0")"
geng make Main >/dev/null
exec node app "$@"
