# gren-toml-test

The [toml-test](https://github.com/toml-lang/toml-test) decoder interface for
[`gren-toml`](../gren-toml). Not a library, not published: a way to score the
parser against the official suite using the official runner.

```
% devbox run test

toml-test v2.2.0 [.../gren-toml-decoder] [no encoder]
  valid tests: 214 passed,  0 failed
invalid tests: 467 passed,  0 failed
```

## What it does

Reads TOML on stdin. If it is valid, writes the tagged JSON description of it to
stdout and exits 0; if not, writes a message to stderr and exits 1. That is the
whole contract, and the program is correspondingly thin — everything it could
get wrong about TOML lives in `gren-toml`.

The one thing that is genuinely this program's business is reading stdin as
**bytes** rather than as text, and reading all of it before decoding any. Nine
of the suite's invalid files are invalid precisely because they are not UTF-8,
so a decoder that reads a string has already lost them; and a character whose
bytes straddle a chunk boundary would look like an encoding error to an
incremental decode.

## Why two conformance runs

This one and `gren-toml`'s own `tests/` suite check the same parser against
different things, on purpose:

|  | corpus | comparator |
| --- | --- | --- |
| here | embedded in the released v2.2.0 runner | the official Go one |
| `gren-toml/tests` | `../vendor/toml-test`, a newer checkout | written independently in Gren |

So a bug would have to fool two comparators about two snapshots to get through.
The vendored corpus is the larger of the two — 220 valid and 494 invalid files
against the released 214 and 467 — and it is the one that also checks the
byte-for-byte round trip, which `toml-test` has no notion of.

## Building

```sh
devbox run build   # produces ./gren-toml-decoder
devbox run test    # builds, then runs the official suite
```

`conformance.sh` installs the runner into `.bin/` on first use, which needs Go
and a network. `build.sh` needs neither.
