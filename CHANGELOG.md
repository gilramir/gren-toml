# 1.1.0

Add support for writing the other three string forms, and changing one element of an array.

- Add `multilineString`, `literalString` and `multilineLiteralString`, in
  `Toml.Literal` and in `Toml.Edit` and `Toml.Encode`. The package
  read all four kinds of string literal and wrote one, so a value with newlines
  in it came out as one long line with `\n` in it. `string` is unchanged and
  still writes a basic string, so nothing a program already writes moves. The
  two forms that have no escapes return a `Maybe` rather than quietly writing
  another form instead.
- Add `respell` and `respellAt` in `Toml.Edit`, for changing how a value is
  *written* rather than what it says. `set` compares by meaning, so when a
  program switches from `string` to `multilineString` it sees no change and
  writes nothing; `respell` is `set` with that comparison taken out, and it
  rewrites the value while keeping the key's comments and its place, which
  `remove` followed by `set` did not. `respellAt` does the same for one element
  of an array. `set` itself is unchanged: `'a'` still equals `"a"`, and a save
  that changes nothing still touches nothing.
- Add `appendTo`, `setAt` and `removeAt` in `Toml.Edit`, for changing a single
  element of an array. Until now the only way to do that was to `set` the whole
  array, which rewrote every element and threw away the indentation and
  comments of the ones that were not changing; these three leave the other
  elements' text exactly where it was. `removeAt` also takes the comment
  written against the element it removes.

# 1.0.0

First release.
