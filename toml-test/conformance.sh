#!/bin/bash
# Run the official toml-test suite against the decoder.
#
# The runner embeds its own copy of the test files, so this checks gren-toml
# against the corpus as it was released rather than against ../vendor/toml-test,
# which is a newer checkout. gren-toml's own tests/ suite uses the vendored one.
# Between them the parser is scored against two snapshots by two independent
# comparators.
set -e
cd "$(dirname "$0")"

VERSION=v2.2.0
BIN=".bin/toml-test"

if [ ! -x "$BIN" ]; then
    echo "installing toml-test $VERSION ..."
    GOBIN="$PWD/.bin" go install "github.com/toml-lang/toml-test/v2/cmd/toml-test@$VERSION"
fi

exec "$BIN" test -toml=1.1.0 -decoder="$PWD/gren-toml-decoder" "$@"
