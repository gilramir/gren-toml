# 1.1.0

Writing the other three string forms, and changing one element of an array.

- `multilineString`, `literalString` and `multilineLiteralString`, in
  `Toml.Literal` and in `Toml.Edit` and `Toml.Encode` beside it. The package
  read all four kinds of string literal and wrote one, so a value with newlines
  in it came out as one long line with `\n` in it. `string` is unchanged and
  still writes a basic string, so nothing a program already writes moves. The
  two forms that have no escapes return a `Maybe` rather than quietly writing
  another form instead.
- `respell` in `Toml.Edit`: `set` without the rule that leaves a value alone when
  the document already means it, for the one case that rule cannot serve --
  changing how a value is *written*, when a program has changed its mind about
  which form it writes. The key keeps its comments and its place, which `remove`
  followed by `set` did not manage. `respellAt` is the same door for one element
  of an array. `set` itself is unchanged: it still compares by meaning, so `'a'`
  still equals `"a"` and a save that changes nothing still touches nothing.
- `appendTo`, `setAt` and `removeAt` in `Toml.Edit`, which change one element of
  an array and leave the other elements' text, indent and comments where they
  are. `set` could only write the array whole, which threw away the formatting
  of the elements it was not changing. `removeAt` takes the note written against
  the element with it.

# 1.0.0

First release.
