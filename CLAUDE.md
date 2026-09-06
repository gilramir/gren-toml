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
  two above so they cannot disagree about how to write a float, an array or an
  inline table. `Toml.Encode`'s `brackets` and `braces` are thin wrappers over
  it; put a new spelling here, never in one of the callers.
- `Toml.Parse` — the grammar, hand-written against `String.Parser.Advanced`.
- `Toml.Write` — the AST back to text. Not exposed.
- `Toml.Number`, `Toml.Strings` — reading a literal into its value. Not exposed.

## The one thing that has to be beside this repo

**`vendor/toml-test`** is a submodule. `git submodule update --init` if it is
empty, or the three corpus suites have nothing to read.

## Commands

Everything runs inside devbox; `gren` and node 22 are not on `PATH` otherwise.

```sh
devbox run build    # compile the package
devbox run docs     # check the doc comments parse
devbox run test     # tests/run.sh: 241 checks, 714 of them corpus files, ~1.1s
devbox run gen      # regenerate the two generated test fixtures

devbox run conformance   # toml-test/: the official runner. Needs Go and,
                         # on first use, a network.
```

`toml-test/` has its own devbox.json because it needs Go, and the package's own
toolchain should not: a contributor who only wants to build the library should
not be made to fetch a Go distribution.

Format sources after editing them, especially after scripted edits:

```sh
gren-format            # the whole src/ tree; --diff to see it without writing
gren-format -r tests/src/
```

Bare `gren-format` walks `src/` on its own. A **directory argument is not
recursive** without `-r`, so `gren-format src/` sees `src/Toml.gren` and nothing
under `src/Toml/` — and says so by printing nothing, which looks like success.

**Never format `tests/src/Literals.gren`.** It holds characters above ASCII
raw, on purpose; `gren-format` escapes a raw U+FFFF back to `\u{FFFF}`, which is
the one code point the compiler reads back wrong (gren-lang/compiler#384, below),
and the Literals suite fails. `-r tests/src/` will do it, so re-run
`devbox run gen` afterwards — it rewrites the file the way the suite needs.

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

The second one has a trap in it. A file that ends with a newline parses to a
final expression that is empty, has no comment and has no newline of its own --
`Toml.Edit.isTerminator` recognises it. Appending *after* that expression makes
it interior, `rebuild` then gives it a newline, and the file quietly stops
ending with one. `append` goes through `beforeTerminator` for exactly this, and
`Editing` has the two cases side by side.

Both were caught by the editing suite comparing whole files rather than the
value that changed. Keep it that way: "the edit was wrong" is not the failure
mode this package has, "everything else moved" is.

Two more rules of `Toml.Edit` that are easy to lose:

- **A top-level key never goes after a header.** `insert` puts it after the
  last top-level key, and when there is none, *before* the first header. The
  fallback `append` is only for a file with no headers at all, or for a key
  that brings its own header with it.
- **A path into an array of tables means the last item**, for reading and
  writing alike. `indexOf` takes the last match for exactly this reason. The one
  exception is a header's own comments: `tableComments` and `setTableComments`
  mean the *first* `[[header]]`, because that block explains the key and it is
  where `Toml.Encode.commented` writes it. `headerIndexOf` is a separate function
  from `indexOf` so the two choices cannot leak into each other.

## Parse errors are chosen, not taken

`String.Parser.Advanced` returns every alternative that failed where it
stopped, and the first one is usually the least helpful -- for `a = @` it is
the opening quote of a string. `Toml.chooseError` takes the furthest position
and, among ties, the highest `Toml.Parse.rank`. **A new `Problem` constructor
needs a rank**, and the Decoding suite pins the messages for the common
mistakes.

## `set` compares before it writes

`Toml.Edit.set` leaves a value alone when the document already means what it is
being set to, and that is load-bearing rather than thrifty: setting a value
replaces the whitespace *inside* it, so a program that writes its whole
configuration back on every save would flatten a hand-arranged array on the key
it was not changing. `sameValue` is the comparison, and it is by meaning and not
by text -- `0x1F` equals `31`, `1.50` equals `1.5`.

**A new `Ast.Value` constructor needs a branch in `sameValue`**, or two values
of that type will always compare unequal and `set` will quietly go back to
rewriting them. The fall-through is `_ -> False`, so nothing complains.

`respell` is `set` with the comparison taken out, and `respellAt` is `setAt`
the same way. They exist so that the comparison never has to be weakened. Changing `sameValue` to compare the
*spelling* as well as the meaning would look like a small fix for "my program
switched to `multilineString` and old files keep the old form", and it would
reverse who wins on every save: the program's form would beat the user's, in
arrays and inline tables too, since `sameValue` recurses -- so a user who
rewrote one element as `'a literal string'` would have their whole
hand-arranged array flattened by a save about some other key. Keep the default
comparison by meaning; the caller who means to change a spelling says so.

`introduce` is `set` plus `setComments` for a key that was not there. The "was
not there" is the whole of it: writing the comments unconditionally would
overwrite whatever the user put in their config file every time the program
saved.

## The four string forms are chosen in one place

`Toml.Strings.escape` and `Toml.Strings.literal` are the writing side, and each
takes the `{ multiline : Bool }` that `unescape` and `verbatim` take on the
reading side. `Toml.Literal` is their only caller; `Toml.Edit` and `Toml.Encode`
are two more names for what it does. A new spelling goes there, never in a
caller.

**`string` writes a basic string and has to go on writing one.** Changing which
form it picks would move the output of every program already using it, on the
next save, for a library whose whole promise is that the file comes back the way
it was left. A new form gets a new constructor.

`literalString` and `multilineLiteralString` return a `Maybe` because `'...'`
has no escapes and genuinely cannot spell an apostrophe. Do not "help" by
falling back to a basic string: a constructor whose output form depends on its
data is one that changes the shape of a key between two saves because somebody
typed an apostrophe.

None of this reaches `Toml.Ast` -- which of the four a value is written as is
recoverable from `raw` through `Strings.kindOf` -- so `Toml.Write` has nothing
to learn and the round trip has nothing to say about it. The `Writing` suite is
what does: it writes each of 26 awkward bodies, parses it back and compares,
because a `raw` the parser would reject makes a document that fails later, in
`Toml.Table.fromDocument`, rather than where it was written.

## An array element's note is not where it looks like it is

`appendTo`, `setAt` and `removeAt` change one element and leave the rest of the
array's text alone. Two pieces of trivia decide whether that works, and neither
of them sits under the element it belongs to:

- the note written after an element's comma lives in the **next** element's
  `before` -- and in the array's `trailing` for the last element;
- when the last element has **no comma**, everything between it and the `]` --
  the space in `[ 1, 2 ]`, but also a note and the newline after it -- lives in
  that element's **`after`**, and `trailing` is empty. The parser's `Done`
  branch for a bare last element says so.

The convention that follows from the first: everything up to and including the
first `Break` of a boundary belongs to the line above it, and everything after
that is the next element's indent. `upToFirstBreak` and `afterFirstBreak` are
the whole of the arithmetic.

The second is why `appended` and `removedFrom` read `last.after ++ trailing` as
**one boundary** and never look at either field on its own. The first version
looked at them separately, treated `after` as if it could only hold a space,
and on `2 # two` with no comma it copied the previous element's note onto the
new element and moved `# two` onto it as well; `removeAt` left the removed
element's note on the survivor. The `noted` and `closed` arrays in the Editing
fixture are the two shapes that catch this. `closingOf` is what goes back in
front of the bracket once a note has moved up: the line ending is kept even
though the note took one with it, because the element the note moved to now
ends that line and the `]` still needs its own.

**`Array.get -1` in Gren is the last element**, so `elementAt` guards
`index < 0`. Without it, `setAt path -1` would quietly change the last element.

## Comments come in two shapes, and that is deliberate

`Toml.Edit.Comments` has `blankBefore`; `Toml.Encode.Comments` does not. Editing
works on somebody's file, so the spacing is theirs to ask for; encoding builds a
file with no author, so the spacing is the module's, and `Toml.Encode`'s style
section already says nobody gets to change it. Do not "fix" the asymmetry by
adding the field to `Encode`.

The one rule the two share: **no blank line between a `[header]` and the first
key of its own table.** `Encode` takes it out in `tidyBlanks`; `Edit.spacedTo`
never puts it in, even when `blankBefore = True` asks. That second half exists
for `introduce` on a first run, where every key asks for a blank above its
explanation and the first key of each new table would otherwise land under an
empty line. `comments` and `setComments` stay inverses either way, since a file
that already has the blank still reads as `True` and writes back unchanged.
The rule is for *keys*: `spacedTo` takes an `Owner`, and for `ATable` the blank
under a parent header is honoured, because a nested header under its parent is
two sections meeting and Encode keeps that one. The Editing suite has a test
that builds the same file through `introduce` and through `Encode` and compares
the two strings, which is what stops the two modules' blank-line rules drifting.

`Toml.Encode` puts its blank lines in unconditionally and takes the useless ones
out again in `tidyBlanks`, because neither the header writer nor the comment
writer can see what is around it. Two of them come out: the one at the top of
the file, and the one between a `[header]` and the first key of its own table --
but *not* the one between a header and a nested header, which is why that
function looks forwards as well as back -- and looks *past* a comment block when
it does, since a nested header with an explanation over it is still a nested
header and still wants the blank.

**`Array.get -1` in Gren is the last element.** `separatesAnything` guards
`index <= 0` for exactly that reason, and the failing test looked like a stray
blank line at the top of the file rather than like an off-by-one. `Toml.Edit`'s
`isBlank` guards `index < 0` for the same reason: without it `comments` on the
first key of a file said there was a blank line above it, because the expression
after the final newline is one.

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
`U+D7FF U+DFFF`, which is not a surrogate pair: the threshold for splitting a
code point into surrogates is `>= 0xFFFF` where it should be `> 0xFFFF`, so
U+FFFF is the only one affected — U+E000, U+FEFF and U+10FFFF all survive.
`tools/gen-strings.py` therefore writes characters above ASCII into the fixture
as themselves, which is why `gren-format` must not touch `Literals.gren`.

**gren-lang/core#138** — `chompIf`/`chompWhile` hand the predicate the leading
surrogate instead of the code point for a character outside the BMP. `Toml.Parse`
has an `orSurrogate` wrapper for this; without it a comment containing an emoji
ends at the emoji. Remove it when the fix lands, and the round-trip suite will
say whether it was safe to.

## Tests

`tests/src/Writing.gren` is the hand-written counterpart to the generated
`Literals.gren`: that one is every string literal in the corpus read, this one
is every form written. It is where a new spelling rule belongs.

`tests/src/Numbers.gren` and `tests/src/Literals.gren` are **generated** by
`tools/gen-numbers.py` and `tools/gen-strings.py` — or both at once, with
`devbox run gen`. Neither script contains any Gren. The output is the matching
file in `tools/templates/` rendered with jinja2, and the script only walks the
corpus and hands over rows. Edit the shape of a suite in the template, not in a
Python string.

Both reproduce their file byte for byte, so a diff afterwards means the template
and the file have drifted — with the one exception that `Literals.gren` does
*not* match what `gren-format` would write, and must not be made to. Each writes
its row counts into a guard test, so an extractor that quietly found nothing
cannot produce a passing suite.

`tools/templates/*.gren` are not compilable Gren — they are jinja2 — so keep
them out of `gren-format` and off any source path.

`toml-test/` is an application, not part of the package, and it depends on
`gilramir/gren-toml` as `local:../` rather than putting `../src` on its source
path. **Keep it that way.** It is the only thing in the repo that goes through
the published API, so it is what notices when something a consumer needs is not
exposed — importing `Toml.Write` from there is a compile error, and should stay
one.

`RoundTrip`, `Semantics` and `Values` read the corpus off the disk through
`tests/src/Corpus.gren`, so they follow the vendored `toml-test` rather than a
snapshot of it. They read `../vendor/toml-test`, which is a submodule: clone
with `--recurse-submodules`, or run `git submodule update --init` in an existing
checkout, or the three corpus suites have nothing to read.

`Values` compares against the suite's own `.json` the way the official runner
does — numerically for numbers, semantically for date-times — rather than as
text.
