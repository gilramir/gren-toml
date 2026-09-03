# gren-toml-test

The [toml-test](https://github.com/toml-lang/toml-test) decoder *and* encoder
interfaces for [`gren-toml`](..). Not a library, not published: a way to score
the library against the official suite using the official runner.

It lives in the same repository as the library on purpose. A library and the
evidence that it works should not be able to drift apart across two checkouts,
and anyone who clones `gren-toml` should be able to run the official suite
against it without going looking for anything.

It is also the only thing here that depends on `gren-toml` the way an outside
consumer does -- `local:../`, not `../src` on the source path the way `tests/`
deliberately does. So it doubles as a check that the public API is enough to
build something real out of: importing an unexposed module from here is a
compile error, and should stay one.

```
% devbox run test

toml-test v2.2.0 [.../gren-toml-decode] [.../gren-toml-encode]
  valid tests: 214 passed,  0 failed
encoder tests: 214 passed,  0 failed
invalid tests: 467 passed,  0 failed
```

## The two directions

```sh
gren-toml-test decode   # TOML on stdin, tagged JSON on stdout
gren-toml-test encode   # tagged JSON on stdin, TOML on stdout
```

Either way: read all of stdin, write the converted form to stdout and exit 0, or
write a message to stderr and exit non-zero. `build.sh` wraps each subcommand in
a script of its own, because what `toml-test` wants handed to `-decoder` and
`-encoder` is a path it can execute rather than a command line.

The two are not the same test. The decoder checks that `Toml.Parse` and
`Toml.Table` read a file correctly; the encoder checks that `Toml.Encode` writes
one that *means* the right thing, since the runner parses the output with its
own blessed TOML implementation and compares that against the JSON it started
from. An encoder that writes plausible-looking TOML saying something slightly
different fails there and nowhere else.

## What the programs are actually for

They are plumbing. Everything they could get wrong about TOML lives in
`gren-toml`, and everything they could get wrong about the JSON lives in
`TaggedJson` and `FromTaggedJson`.

The one thing that is genuinely their own business is reading stdin as **bytes**
and reading all of it before decoding any. Nine of the suite's invalid files are
invalid precisely because they are not UTF-8, so a decoder that reads a string
has already lost them; and a character whose bytes straddle a chunk boundary
would look like an encoding error to an incremental decode.

## Two things the JSON format forces

**A scalar is an object of exactly two string fields named `type` and `value`.**
So is a table with two string-valued keys called `type` and `value`, and nothing
in the format tells them apart. `toml-test`'s own reader uses the
size-and-names test and so does `FromTaggedJson`; a document ambiguous under it
is ambiguous for the official runner too.

**Every value is a string**, which is what keeps `9223372036854775807` intact
through a JSON reader. So the `type` tag is the only thing that says how to read
one back, and the reading is done by `gren-toml`'s own parsers — the same code
that reads `1979-05-27T07:32:00Z` out of a TOML file reads it out of here.

## Why two conformance runs

This one and the library's own `../tests` suite check the same library against
different things, on purpose:

|  | corpus | comparator |
| --- | --- | --- |
| here | embedded in the released v2.2.0 runner | the official Go one |
| `../tests` | `../../vendor/toml-test`, a newer checkout | written independently in Gren |

So a bug would have to fool two comparators about two snapshots to get through.
The vendored corpus is the larger of the two — 220 valid and 494 invalid files
against the released 214 and 467 — and it is the one that also checks the
byte-for-byte round trip, which `toml-test` has no notion of.

## Building

```sh
devbox run build   # produces ./gren-toml-decode and ./gren-toml-encode
devbox run test    # builds, then runs the official suite over both
```

Or `devbox run conformance` from the package root, which is this directory's
`test` under another name.

This directory has a devbox.json of its own because it needs Go, and the
package's toolchain should not: someone who only wants to build the library
should not be made to fetch a Go distribution to do it.

`conformance.sh` installs the runner into `.bin/` on first use, which needs Go
and a network. `build.sh` needs neither.
