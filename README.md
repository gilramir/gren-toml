# gren-toml

A TOML 1.1 parser for [Gren](https://gren-lang.org/).
You can use it to read TOML files easily.

You can also create TOML files. And, it tracks all positions of tokens,
strings, etc, within the file, including those of comments.  Your program
can *update* TOML files and re-write them accurately, without losing the
author's original comments.  The blank lines are where you left them,
the comments are attached to the keys they were written for, and the
`1.50` you wrote is still `1.50` and not `1.5`.

Parse and re-write:

```gren
Toml.parseBytes source
    |> Result.map Toml.toString
--> Ok (the same bytes back)
```

That round trip is exact for every one of the 220 valid files in the
official TOML test suite. The AST stores the whitespace and the comments as
*text* so that it can re-write correctly.

## Three complete examples

These are examples of using `gren-toml` in Gren `node` programs, each
asking more of the TOML file than the last. Everything below compiles
as written. The first reads a single value.  The second reads the whole
file into a type of your own. The third owns the file: it creates it on
the first run, reads it on every run after, and writes it back without
disturbing anything the user did to it.

### Reading one value

You know the section and you know the key, and you want the one value. There is
nothing to define first.

```toml
# Where the service listens.
[server]
host = "0.0.0.0"
port = 8080
```

```gren
import Toml.Decode as Decode

Decode.fromBytes (Decode.at [ "server", "host" ] Decode.string) bytes
--> Ok "0.0.0.0"

Decode.fromBytes (Decode.at [ "server", "port" ] Decode.int) bytes
--> Ok 8080
```

With the file read off the disk around it, that is the whole program:

```gren
import FileSystem
import FileSystem.Path exposing (Path)
import Task exposing (Task)

readHost : FileSystem.Permission -> Path -> Task String String
readHost fs path =
    FileSystem.readFile fs path
        |> Task.mapError FileSystem.errorToString
        |> Task.andThen
            (\bytes ->
                when Decode.fromBytes (Decode.at [ "server", "host" ] Decode.string) bytes is
                    Ok host ->
                        Task.succeed host

                    Err problem ->
                        Task.fail (Decode.errorToString problem)
            )
```

- **`at` says where, the decoder says what.** `[ "server", "host" ]` is a path
  through the tables, and it finds the value whether the file wrote a
  `[server]` header or `server.host = "0.0.0.0"` on one line. For a key at the
  top level of the file, `Decode.field "name"` is the same thing with one step.
- **The decoder is the type you expect**: `string`, `bool`, `int`, `float`,
  `bigInt`, `bigDecimal`, and one for each of TOML's four date and time shapes.
  Nothing has to be checked afterwards -- a value of the wrong type is an `Err`
  here.
- **`fromBytes` does all of it in one call**: parse, check what the document
  means, walk the path, read the value. There is no document to hold on to.
- **The error names the path**, so it is worth printing as it comes:

  ```
  at server.host: expected an integer, found a string
  at server.nope: no such key
  ```

- **`bigInt` for a number that may not fit.** TOML integers have no width, so
  `int` refuses a number too large for a Gren `Int` rather than truncating it,
  and the error says what to reach for: `9223372036854775807 does not fit in an
  Int; use bigInt to read it exactly`.
- **More than a value or two and this stops paying.** Each one is another parse
  of the file, and nothing anywhere says what the configuration as a whole is.
  That is the next example.

### Reading a config file into your own type

The same file, with a second section in it:

```toml
# Where the service listens.
[server]
host = "0.0.0.0"
port = 8080

[logging]
level = "info"   # one of: debug, info, warn
# Optional. Logs go to stdout when this is missing.
file = "/var/log/svc.log"
```

The type you want it to become, and a decoder that says how the file maps onto
it:

```gren
import Toml.Decode as Decode exposing (Decoder)

type alias Config =
    { host : String
    , listenPort : Int
    , level : String
    , logFile : Maybe String
    }

config : Decoder Config
config =
    Decode.succeed
        (\host listenPort level logFile ->
            { host = host, listenPort = listenPort, level = level, logFile = logFile }
        )
        |> Decode.andMap (Decode.at [ "server", "host" ] Decode.string)
        |> Decode.andMap (Decode.at [ "server", "port" ] Decode.int)
        |> Decode.andMap (Decode.at [ "logging", "level" ] Decode.string)
        |> Decode.andMap (Decode.field "logging" (Decode.optionalField "file" Decode.string))
```

Line by line:

- **`Decode.succeed` starts with a function** that builds the record, and each
  `andMap` feeds it one decoded value, in the order the arguments are written.
  To add a field to the config, add an argument and a line. `map2` and `map3`
  exist for the short cases.
- **`Decode.at [ "server", "host" ]` is a path through the table tree.** It finds
  the value whether the file wrote a `[server]` header with `host` under it, or
  `server.host = "0.0.0.0"` on one line. Your decoder does not know or care how
  the file was laid out.
- **`Decode.int` is where the type is checked.** A value that is not an integer
  fails right here, and the error names the path. Nothing downstream needs to
  check again.
- **`optionalField` is `Nothing` when the key is absent** and still an error when
  the key is present with the wrong type. That is the difference from `maybe`,
  which forgives both.

Reading the file is one function:

```gren
import FileSystem
import FileSystem.Path exposing (Path)
import Task exposing (Task)

loadConfig : FileSystem.Permission -> Path -> Task String Config
loadConfig fs path =
    FileSystem.readFile fs path
        |> Task.mapError FileSystem.errorToString
        |> Task.andThen
            (\bytes ->
                when Decode.fromBytes config bytes is
                    Ok found ->
                        Task.succeed found

                    Err problem ->
                        Task.fail (Decode.errorToString problem)
            )
```

- **`FileSystem.readFile` hands you `Bytes`. Hand the bytes on.** `Decode.fromBytes`
  parses, checks what the document means (duplicate keys, a table defined
  twice) and decodes, in one call. It takes bytes rather than a string because
  a UTF-8 error can only be seen before the text has been repaired -- see
  [start from the bytes](#start-from-the-bytes).
- **Every failure becomes one line of text** through `errorToString`, with the
  path to the problem. Change `level = "info"` to `level = 3` and the program
  reports:

  ```
  at logging.level: expected a string, found an integer
  ```

- **That is the program's entire contact with TOML.** From here on it holds a
  `Config`, and nothing else in it knows there was a file.

### A settings file the program creates, reads and updates

This is the shape a TUI or a desktop tool has: a settings file the program
writes on the first run, the user edits by hand, and the program writes again
on every save. The whole point of this package is that the user's edits, their
comments and their arrangement survive that last step.

```gren
import Array exposing (Array)
import Toml
import Toml.Decode as Decode exposing (Decoder)
import Toml.Edit as Edit

type alias Settings =
    { theme : String
    , zones : Array String
    }

defaults : Settings
defaults =
    { theme = "dark", zones = [ "UTC" ] }
```

**Loading.** Three outcomes, and the difference between the second and the
third is the one that matters:

```gren
load : FileSystem.Permission -> Path -> Task String Toml.Document
load fs path =
    FileSystem.readFile fs path
        |> Task.map Just
        |> Task.onError
            (\problem ->
                if FileSystem.errorIsNoSuchFileOrDirectory problem then
                    Task.succeed Nothing

                else
                    Task.fail (FileSystem.errorToString problem)
            )
        |> Task.andThen
            (\found ->
                when found is
                    Nothing ->
                        Task.succeed Toml.empty

                    Just bytes ->
                        when Toml.parseBytes bytes is
                            Ok document ->
                                Task.succeed document

                            Err problem ->
                                Task.fail (Toml.errorToString problem)
            )
```

- **No file yet means `Toml.empty`.** That is the first run, and it is not a
  special case anywhere else in the program: every key is missing from an empty
  document, and the save below adds keys that are missing.
- **A file that will not parse is an error, and stays one.** Do not write
  `Result.withDefault Toml.empty` here. It reads well and it means that a user
  who leaves a typo in the file gets an empty document written over their whole
  file on the next save. With the code above, `theme = dark` (no quotes) stops
  the program with:

  ```
  line 2, column 13: expected a value, but dark is not one
  ```

  and the file on disk is exactly as they left it.

- **Any other I/O error is also an error.** Permission denied is not "no file".

**Reading the values out of the document you are holding:**

```gren
settings : Decoder Settings
settings =
    Decode.map2 (\theme zones -> { theme = theme, zones = zones })
        (Decode.optionalField "theme" Decode.string
            |> Decode.map (Maybe.withDefault defaults.theme)
        )
        (Decode.optionalField "zones" (Decode.array Decode.string)
            |> Decode.map (Maybe.withDefault defaults.zones)
        )

read : Toml.Document -> Result String Settings
read document =
    Decode.fromDocument settings document
        |> Result.mapError Decode.errorToString
```

- **Every key is optional and has a default**, so a missing key -- on the first
  run, or because the user deleted a line -- is not an error. A key that is
  there with the wrong type still is, which is what you want: `theme = 3` is a
  mistake to report, not a default to fall back to.
- **`fromDocument` decodes the document you already parsed.** The program keeps
  the `Document` for editing, so there is no reason to parse the file twice.

**Writing the values back into that same document:**

```gren
write : Settings -> Toml.Document -> Toml.Document
write current document =
    document
        |> Edit.introduce [ "theme" ]
            { blankBefore = True
            , leading = [ " Colour scheme: \"dark\" or \"light\"." ]
            , trailing = Nothing
            }
            (Edit.string current.theme)
        |> Edit.introduce [ "zones" ]
            { blankBefore = True
            , leading = [ " Time zones, in the order they are shown." ]
            , trailing = Nothing
            }
            (Edit.array (Array.map Edit.string current.zones))
```

- **`introduce` is `set` plus an explanation, written only the first time.** When
  the key is not in the document, the value goes in with the comment block
  above it. When the key is already there, only the value is set and the
  comments -- whatever the user has made of them since -- are left alone.
- **`set` compares before it writes.** A key whose value has not changed is not
  touched at all, spacing and comments included, so writing every key on every
  save is safe. That is what lets `write` be one function that does not need
  to know what changed.
- **Values are built with `Edit.string`, `Edit.int`, `Edit.array` and the
  rest.** Each one chooses a spelling for a value that has no source text yet.
- **Keys under a `[header]` are the same call** with a longer path:
  `Edit.introduce [ "window", "width" ] ...` brings the `[window]` header with
  it when there is none. To explain the section itself, `Edit.setTableComments
  [ "window" ]`, guarded by `Edit.member` on its first key so it happens once.

**Saving:**

```gren
save : FileSystem.Permission -> Path -> Toml.Document -> Task String {}
save fs path document =
    FileSystem.writeFile fs (Toml.toBytes document) path
        |> Task.mapError FileSystem.errorToString
        |> Task.map (\_ -> {})
```

- **`Toml.toBytes` is the way back from `parseBytes`**, byte order mark included
  if there was one. `writeFile` creates the file or overwrites it.

**Putting it together.** Keep the `Document` in your model next to the
`Settings`, because the document is the user's file and the settings are just
what you read out of it. On start, `load`, then `read`. On every save,
`write settings document |> save fs path`. There is no separate "first run"
code: the first run is a save onto `Toml.empty`.

Here is what that looks like on disk. The first run, with no file, writes:

```toml
# Colour scheme: "dark" or "light".
theme = "dark"

# Time zones, in the order they are shown.
zones = ["UTC"]
```

The user opens it, changes the theme, adds a note, and arranges the zones the
way they like:

```toml
# Colour scheme: "dark" or "light".
theme = "light"   # easier on the eyes at work

# Time zones, in the order they are shown.
zones = [
  "Asia/Seoul",      # them
  "America/Chicago", # me
]
```

`read` now gives `{ theme = "light", zones = [ "Asia/Seoul", "America/Chicago" ] }`.
The program switches the theme back to `"dark"` and saves everything:

```toml
# Colour scheme: "dark" or "light".
theme = "dark"   # easier on the eyes at work

# Time zones, in the order they are shown.
zones = [
  "Asia/Seoul",      # them
  "America/Chicago", # me
]
```

One value changed. The note beside it stayed, the array the user arranged by
hand was not rewritten because it already said what the program was setting it
to, and the explanations were not written a second time.

## Editing

```gren
Toml.parseBytes source
    |> Result.map (Toml.Edit.set [ "server", "port" ] (Toml.Edit.int 9090))
    |> Result.map Toml.toString
```

`set` changes only the value: the key keeps its spelling, the equals sign keeps
the whitespace around it, and the comment on the line stays. A key that is not
there yet is added at the end of the table it belongs to, indented to match its
neighbours; if the table is not there either, a `[header]` comes with it.

**A value that is already what you are setting it to is left exactly as it is
written**, and that is the property that makes "write my whole configuration
back" safe to do on every save. Setting a value replaces the whitespace inside
it, so an array somebody arranged over four lines with a note against each
element would otherwise be flattened onto one -- on the key nobody changed,
because the program was saving some other key. The comparison is by value and
not by text: `0x1F` and `31` are the same integer, `1.50` and `1.5` the same
number, so nothing is rewritten to say what it already said.

The value can be an array or an inline table as well as a scalar — `array` and
`inlineTable` write them on one line. Replacing the whole inline table is also
how to change something *inside* one, because a path stops at the brace: an
inline table has no lines to insert into, so the boundary is drawn there rather
than guessed at.

A path into an array of tables names its last item, which is the item TOML
itself means by `[peer.tls]` or `peer.x = 1` after the second `[[peer]]`.

`Toml.Edit` checks syntax and nothing else. A path that points at something a
key cannot be added beside -- inside an inline table, say -- produces a file that
`Toml.Table.fromDocument` will reject, for the same reason and with the same
message as if someone had typed it. Read an edited document back before writing
it out if the paths were not yours to begin with.

`rename` gives a key a new name and touches nothing else on the line, quoting
the name if the grammar will not take it bare. `renameTable` does the same for a
table, taking every header nested under it and every dotted key that spells the
name out — and leaving the last part of a dotted key alone, since that one names
the value rather than a table.

`remove` takes a key out along with the comments that belong to it. Which ones
those are is a convention, since TOML does not say, and it is this one:

- **Leading** — own-line comments directly above a key, no blank line between.
  They go when it goes.
- **Trailing** — a comment after the value on the same line.
- **Floating** — anything after a blank line belongs to nobody and survives.
- **Header** — comments before the first key belong to the document.

The blank line is the escape hatch, and it is worth knowing about: a comment
block that introduces a whole section rather than the one key beneath it should
have a blank line under it, or deleting that key will take the heading too.

`setComments` writes back what `comments` reads, in the same shape, so the two
are inverses. Adding a trailing comment to a line that had none puts a space in
front of it; taking one off takes that whitespace with it. `blankBefore` is
whether an empty line sits above the block, which is here because there is no
other way to ask for one -- a document is a list of expressions and has no
lines to insert between.

`introduce` is `set` and `setComments` in one call, except that the comments
are written **only when the key was not already there**. It is the shape a
program keeping a config file wants: every key it invents arrives with a
sentence saying what it is for, and the user who deletes that sentence, or
rewrites it in their own language, does not get corrected on the next save.

`tableComments` and `setTableComments` do the same for a `[header]` line, which
owns the block above it the way a key does -- `removeTable` already took it with
the table, and now it can be read and written. For an array of tables that is
the *first* `[[header]]`, where `Toml.Encode` puts them, because the block
explains the key rather than one item; it is the one path in the module that
does not mean the last item.

## Writing one that may not exist yet

`Toml.empty` is a document with nothing in it. Every key is missing from it and
`set` adds a key that is missing, so creating the file and updating it are the
same code:

```gren
(when found is
    Nothing ->
        Ok Toml.empty

    Just bytes ->
        Toml.parseBytes bytes
)
    |> Result.map (Toml.Edit.introduce [ "theme" ] note (Toml.Edit.string "dark"))
    |> Result.map Toml.toBytes
```

Without it a program needs a second path that writes the file from scratch,
which is a second place to keep the shape of the file and the first place for
the two to disagree.

`Toml.empty` is for a file that is not there. A file that is there and fails to
parse must stay an `Err` -- `Result.withDefault Toml.empty` would turn a typo in
the user's config into an empty document and write it back over their file on
the next save.

## Writing one from scratch

```gren
Toml.Encode.toString
    [ Toml.Encode.field "name" (Toml.Encode.string "widget")
    , Toml.Encode.field "server"
        (Toml.Encode.table
            [ Toml.Encode.field "host" (Toml.Encode.string "example.com")
            , Toml.Encode.field "port" (Toml.Encode.int 8080)
            ]
        )
    ]
```

```toml
name = "widget"

[server]
host = "example.com"
port = 8080
```

`commented` explains a field, since a file nobody can read is not much better
than no file:

```gren
Toml.Encode.field "port" (Toml.Encode.int 8080)
    |> Toml.Encode.commented
        { leading = [ " What to listen on." ], trailing = Just " http" }
```

There is no blank-line setting to go with it, unlike in `Toml.Edit`, because a
file this wrote has no author to have an opinion about its spacing: a commented
field gets a blank line above it, and not at the top of a file or under a
`[header]`, where there is nothing above to be held off.

You choose the shape rather than a heuristic choosing it: `table` and
`tableArray` write `[header]` sections, `inlineTable` and `array` write braces
and brackets. Fields come out in the order you gave them — except that a table's
own keys are written before its sections, because a key written after a
`[header]` would land inside that header's table instead.

## Two layers, and you pick

**`Toml.Ast`** is the file: a list of expressions in the order they appear,
each carrying the exact whitespace around it and the exact spelling of every
value. This is what an editing API works on.

**`Toml.Table`** is what the file *says*: keys resolved, dotted keys expanded,
arrays of tables assembled, in a `Dict`. It remembers nothing about
formatting, because none of that is part of what a TOML document means. This is
what a program that only wants to read its configuration should use.

It goes one way. A file is written from the AST, never from the table, because
the table is precisely what has forgotten how the file was written.
`Toml.Decode.fromDocument` reads a document you are already holding — one you
parsed in order to edit it — so that a program editing a file and a program
reading it need not parse it twice.

The second is built from the first, and building it is where a document gets
rejected for the things a grammar cannot see -- `[a]` written twice, a key
defined twice, a dotted key reaching into a table a header already defined.

## Positions are not in the AST

A row number goes stale the moment a line is inserted above it. A column number
survives that but cannot tell a tab from eight spaces, and cannot represent the
alignment you chose between two tokens.

So instead of positions, each node holds the string that was actually there:
`indent`, `wsBeforeEq`, `trailing`. Rows and columns still exist in parse
*errors*, where they describe a file that is not about to change.

The same idea covers values. `BigDecimal` reads `1.50` and `1.5` as the same
number, which is correct and is exactly why a value alone cannot be written back
out. Every scalar carries its source text next to its meaning.

## Start from the bytes

```gren
Toml.parseBytes : Bytes -> Result Error Document   -- this one
Toml.parse      : String -> Result Error Document  -- for when you already have text
Toml.toBytes    : Document -> Bytes
Toml.toString   : Document -> String
```

`toBytes` is the way back, and the byte order mark rides along with it.

`parseBytes` is the real entry point, because two of the things that make a TOML
file invalid are decided before there is a `String` to look at. `Bytes.toString`
is a strict UTF-8 decode, so a bad byte sequence is caught there; by the time you
hold a `String`, the error has been repaired into `U+FFFD`, which is a legal TOML
character and cannot be found again. And decoding silently removes one leading
byte order mark, so only the bytes know whether there was one.

## Conformance

Everything is checked against the official
[toml-test](https://github.com/toml-lang/toml-test) suite, filtered to the
1.1.0 manifest, read off the disk at run time.

| | |
| --- | --- |
| valid files that parse and lower | 220 / 220 |
| valid files that round-trip byte for byte | 220 / 220 |
| valid files whose values match the suite's JSON | 220 / 220 |
| invalid files rejected | 494 / 494 |

Nine of those invalid files never reach the parser: they are not valid UTF-8,
deliberately, and the decode refuses them.

Syntactically-fine *invalid* files round-trip too, all 485 of them. That is not
generosity -- it is the point. Round-tripping is a property of the AST, not a
reward for being valid.

## What it is built on

- [`gilramir/gren-bignum`](https://packages.gren-lang.org/) for integers with no
  width and decimals with no rounding, so `9223372036854775807` and `0.1` are
  both exact.
- [`gilramir/gren-civil-time`](https://packages.gren-lang.org/package/gilramir/gren-civil-time)
  for the four date and time shapes, kept lexical so that `-07:00` survives
  instead of being normalised away.

## Tests

```sh
devbox run test          # 186 checks, ~0.9s, no network
devbox run conformance   # the official toml-test runner; needs Go
```

### First, the one thing that has to be beside the repo

**The test corpus is a git submodule.** `vendor/toml-test` holds the 714 files
the suite reads, and it is pinned to one commit — which is load-bearing rather
than tidiness, because the suites assert exact counts (220 valid files, 485
invalid ones, 32 date-times). A floating checkout would turn an upstream
addition into a local failure.

```sh
git clone --recurse-submodules <this repo>
```

**If you already cloned without `--recurse-submodules`**, `vendor/toml-test` is
an empty directory and three of the nine suites cannot start:

```
=== SUITE ERRORS ===
RoundTrip: setUpSuite: ENOENT: no such file or directory,
           open '../vendor/toml-test/tests/files-toml-1.1.0'
Semantics: setUpSuite: ...
Values:    setUpSuite: ...

FAILED — 178 passed, 0 failed, 11 errored
```

`0 failed, 11 errored` is the signature: nothing is wrong with the library,
three suites just have nothing to read. Fix it in place, no re-clone needed:

```sh
git submodule update --init
```

### What the two commands check

`devbox run test` runs `tests/`, which reads the corpus off the disk rather than
from a baked-in fixture, so it follows the submodule rather than a snapshot of
it. Nine suites, in ~0.9s and with no network:

| suite | asks |
|---|---|
| `RoundTrip` | does every file come back from the writer byte for byte? |
| `Semantics` | are exactly the right files accepted and rejected? |
| `Values` | does each one read as the values `toml-test`'s own JSON says? |
| `Numbers`, `Literals` | every number and string literal in the suite, in isolation |
| `Decoding`, `Editing`, `Encoding` | the three APIs, hand-written |
| `Examples` | the examples in the doc comments, against the file from toml.io |

The first three are the ones that need the submodule.

`devbox run conformance` shells into `toml-test/` and runs the **official Go
runner** against both the decoder and encoder interfaces. It needs Go, and a
network the first time to install the runner into `toml-test/.bin`:

```
  valid tests: 214 passed,  0 failed
encoder tests: 214 passed,  0 failed
invalid tests: 467 passed,  0 failed
```

The two runs are not redundant. `toml-test` embeds its own corpus and compares
with the official Go implementation; `tests/` uses the newer pinned checkout, a
comparator written independently in Gren, and the byte-for-byte round trip,
which `toml-test` has no notion of. A bug has to fool two comparators about two
snapshots to get through.

### Regenerating the fixtures

`tests/src/Numbers.gren` and `tests/src/Literals.gren` are generated from the
corpus. The Gren around the generated tables lives in `tools/templates/`, as
`.gren` files with jinja2 placeholders where the rows go, so the scripts hold
extraction and nothing else. Both reproduce their file byte for byte, so a diff
after regenerating means the template and the file have drifted:

```sh
devbox run gen           # both scripts, from the repo root
```
