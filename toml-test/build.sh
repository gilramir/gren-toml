#!/bin/bash
# Build the decoder into a runnable script.
#
# `gren make Main` (no --output) produces a self-running executable, which is
# what toml-test wants to exec. The wrapper exists so the thing toml-test is
# handed is a single path with no `node` in front of it.
set -e
cd "$(dirname "$0")"
gren make Main >/dev/null
cat > gren-toml-decoder <<'WRAPPER'
#!/bin/sh
exec node "$(dirname "$0")/app" "$@"
WRAPPER
chmod +x gren-toml-decoder
