# 1.1.0

Write all four string forms, and change one element of an array at a time.

- Add `multilineString`, `literalString` and `multilineLiteralString` to
  `Toml.Literal`, `Toml.Edit` and `Toml.Encode`. The package could read all
  four kinds of string literal but only wrote one, so a value with newlines in
  it came out as one long line full of `\n`. `string` still writes a basic
  string, so nothing a program already writes changes. The two literal forms
  have no escapes, so they return a `Maybe` rather than quietly writing another
  form.
- Add `respell` and `respellAt` to `Toml.Edit`, for changing how a value is
  *written* rather than what it means. `set` compares by meaning, so when a
  program switches from `string` to `multilineString` it sees no change and
  writes nothing. `respell` is `set` without that comparison. It rewrites the
  value and keeps the key's comments and its place in the file, which `remove`
  followed by `set` did not. `respellAt` does the same for one element of an
  array. `set` itself is unchanged: `'a'` still equals `"a"`, and a save that
  changes nothing still touches nothing.
- Add `appendTo`, `setAt` and `removeAt` to `Toml.Edit`, for changing a single
  element of an array. Until now the only way was to `set` the whole array,
  which rewrote every element and lost the indentation and comments of the ones
  that were not changing. These three leave the other elements' text exactly
  where it was. `removeAt` also removes the comment written against the element
  it removes.

# 1.0.0

First release.
