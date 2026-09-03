# gren-toml

A TOML 1.1 parser for [Gren](https://gren-lang.org/) that does not lose your
comments.

Read a config file, change one value, write it back, and the result is the file
you started with plus that one change. The blank lines are where you left them,
the comments are attached to the keys they were written for, and the `1.50` you
wrote is still `1.50` and not `1.5`.

```gren
Toml.parseBytes source
    |> Result.map Toml.toString
--> Ok (the same bytes back)
```

That round trip is exact for every one of the 220 valid files in the official
test suite. It is exact by construction rather than by effort: the AST stores
the whitespace and the comments as *text*, so there is nowhere for a character
to go missing.

## Two layers, and you pick

**`Toml.Ast`** is the file: a list of expressions in the order they appear,
each carrying the exact whitespace around it and the exact spelling of every
value. This is what an editing API works on.

**`Toml.Table`** is what the file *says*: keys resolved, dotted keys expanded,
arrays of tables assembled, in a `Dict`. It remembers nothing about
formatting, because none of that is part of what a TOML document means. This is
what a program that only wants to read its configuration should use.

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
```

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
- [`gilramir/gren-civil-time`](../gren-civil-time) for the four date and time
  shapes, kept lexical so that `-07:00` survives instead of being normalised
  away.

## Tests

```sh
devbox run test
```

## License

ISC.
