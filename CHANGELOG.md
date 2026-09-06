# 1.1.0

Write all four string forms, change an array one element at a time without
losing the note against any of them, and take the blank line with the key it
belongs to.

- Add `multilineString`, `literalString` and `multilineLiteralString` to
  `Toml.Literal`, `Toml.Edit` and `Toml.Encode`. The package could read all
  four kinds of string literal but only wrote one, so a value with newlines in
  it came out as one long line full of `\n`. `string` still writes a basic
  string, so nothing a program already writes changes. The two literal forms
  have no escapes, so they return a `Maybe` rather than quietly writing another
  form.
- Add `appendTo`, `setAt` and `removeAt` to `Toml.Edit`, for changing a single
  element of an array. Until now the only way was to `set` the whole array,
  which rewrote every element and lost the indentation and comments of the ones
  that were not changing. These three leave the other elements' text exactly
  where it was. `removeAt` also removes the comment written against the element
  it removes.
- Add `insertAt` and `moveAt` to `Toml.Edit`. Those three cover adding at the
  end, changing in place and taking out, which still leaves no way to reorder a
  list: a `removeAt` and an `insertAt` lose the note written against the
  element, each of them correctly, and walking the new order down the list with
  `setAt` keeps every note against its *position*, so a move leaves `# me`
  written against somebody else's city. `moveAt` takes the value and its note
  together. `insertAt` puts an element anywhere in the list rather than only on
  the end, and the elements around it keep their lines, their indentation and
  their comments as the others leave them.
- Add `respell` and `respellAt` to `Toml.Edit`, for changing how a value is
  *written* rather than what it means. `set` compares by meaning, so when a
  program switches from `string` to `multilineString` it sees no change and
  writes nothing. `respell` is `set` without that comparison. It rewrites the
  value and keeps the key's comments and its place in the file, which `remove`
  followed by `set` did not. `respellAt` does the same for one element of an
  array. `set` itself is unchanged: `'a'` still equals `"a"`, and a save that
  changes nothing still touches nothing.
- `remove` now takes the blank line above a key's comment block with it, when
  the block leaves a blank line or the end of the file below it. `blankBefore`
  is a field of the key's own `Comments` and `introduce` writes that line, so
  without this a program that wrote a key when a setting was on and removed it
  when the setting went back to its default added one empty line to the file
  per cycle. A block with a blank line on one side only keeps it: that one
  separates what is above the key from what is below it.

# 1.0.0

First release.
