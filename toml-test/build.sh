#!/bin/bash
# Build the two toml-test interfaces into runnable scripts.
#
# `geng make Main` (no --output) produces a self-running executable. The two
# wrappers exist because what toml-test wants handed to -decoder and -encoder is
# a path it can execute, not a command line with a subcommand in it.
set -e
cd "$(dirname "$0")"
geng make Main >/dev/null

for word in decode encode; do
    cat > "gren-toml-$word" <<WRAPPER
#!/bin/sh
exec node "\$(dirname "\$0")/app" $word "\$@"
WRAPPER
    chmod +x "gren-toml-$word"
done
