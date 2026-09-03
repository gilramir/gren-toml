# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## About this project

`gren-toml` is a TOML 1.1 parser that preserves comments and formatting well
enough to round-trip a file byte for byte. [README.md](README.md) says what it
is for and why the AST is shaped the way it is.

Modules, outermost first:

- `Toml` — the entry point. `parseBytes`, `parse`, `toString`.
- `Toml.Ast` — the syntactic layer. Types only, no functions.
- `Toml.Table` — the semantic layer, and where a document gets rejected.
- `Toml.Decode` — reading a file into your own types.
- `Toml.Edit` — changing a file in place, on the AST.
- `Toml.Encode` — building a file from nothing.
- `Toml.Literal` — spelling a value that has no source text yet. Shared by the
  two above so they cannot disagree about how to write a float.
- `Toml.Parse` — the grammar, hand-written against `String.Parser.Advanced`.
- `Toml.Write` — the AST back to text. Not exposed.
- `Toml.Number`, `Toml.Strings` — reading a literal into its value. Not exposed.

## Commands

Everything runs inside devbox; `gren` and node 22 are not on `PATH` otherwise.

```sh
devbox run build    # compile the package
devbox run docs     # check the doc comments parse
devbox run test     # tests/run.sh: 71 checks, 714 of them corpus files, ~0.8s
```

Format sources after editing them, especially after scripted edits:

```sh
gren-format src/ tests/src/
gren-format --diff src/ tests/src/
```

## The invariant everything else serves

**Nothing is thrown away between the bytes and the AST.** Whitespace and
comments are stored as text, not as positions. Every scalar carries its source
spelling next to its parsed value, because `BigDecimal` cannot tell `1.50` from
`1.5` and the file said `1.50`.

The round-trip suite is what enforces this, and it is not a formality: it caught
every writer bug during development, and a mutation of `Toml.Write` fails it
within a second with the byte offset and an excerpt from each side.

Adding a field to an AST node means adding it to `Toml.Write` too. If you forget,
the round trip fails; that is the design working.

## Toml.Edit's two invisible invariants

Both are about line endings and both are broken silently. `rebuild` is the one
place that restores them, and every edit goes through it:

1. Every expression but the last needs a newline. An edit that inserts after
   what used to be the final line breaks this.
2. Whether the *last* expression has one is what says if the file ends with a
   newline. An edit that removes the final line, or appends past it, changes
   that without meaning to.

Both were caught by the editing suite comparing whole files rather than the
value that changed. Keep it that way: "the edit was wrong" is not the failure
mode this package has, "everything else moved" is.

## Toml.Encode's two rules that look cosmetic and are not

**A table's own keys go before its sections.** A key written after a `[header]`
belongs to that header's table. Reordering the two lines does not just make the
output uglier, it moves the key. The suite checks this by reading the value back
out, not by comparing text.

**A float always gets a decimal point.** `1` without one is an *integer* in
TOML, so `Encode.float 1.0` writing `a = 1` would round-trip as the wrong type.
Also checked by reading it back.

## The two layers must not blur

`Toml.Parse` checks syntax and nothing else. Duplicate keys, redefined tables and
dotted keys reaching into a header's table are **not syntax** and belong in
`Toml.Table.fromDocument`. About a third of the suite's invalid files are
perfectly good syntax, so a rule put in the wrong layer will look like it works
and be wrong about which error it reports.

`Toml.Table` tracks how each table came to exist (`Implicit`, `Explicit`,
`Dotted`, `Inline`) and every rule follows from that. The subtle one: **passing
through a table is not defining it.** `[[fruit.apple.seeds]]` is legal after
`apple.color = "red"` because it defines `seeds` and merely visits `apple`.

## Two upstream bugs are worked around here

**gren-lang/compiler#384** — `\u{FFFF}` in a string literal compiles to
`U+D7FF U+DFFF`, which is not a surrogate pair. `tools/gen-strings.py` therefore
writes characters above ASCII into the fixture as themselves.

**gren-lang/core#138** — `chompIf`/`chompWhile` hand the predicate the leading
surrogate instead of the code point for a character outside the BMP. `Toml.Parse`
has an `orSurrogate` wrapper for this; without it a comment containing an emoji
ends at the emoji. Remove it when the fix lands, and the round-trip suite will
say whether it was safe to.

## Tests

`tests/src/Numbers.gren` and `tests/src/Literals.gren` are **generated** by
`tools/gen-numbers.py` and `tools/gen-strings.py`. Re-run the script from the
package root; both reproduce their file byte for byte and already emit the
escapes `gren-format` normalises to, so a diff afterwards means the script and
the file have drifted. Each writes its row counts into a guard test, so an
extractor that quietly found nothing cannot produce a passing suite.

`RoundTrip`, `Semantics` and `Values` read the corpus off the disk through
`tests/src/Corpus.gren`, so they follow the vendored `toml-test` rather than a
snapshot of it. They need `../../vendor/toml-test` to be checked out.

`Values` compares against the suite's own `.json` the way the official runner
does — numerically for numbers, semantically for date-times — rather than as
text.
