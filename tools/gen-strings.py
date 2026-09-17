#!/usr/bin/env python3
"""Regenerate tests/src/Literals.geng from the official TOML test suite.

Pulls every string literal out of the suite's string and key directories and
pairs it with the value the .json says it means. Finding where a literal ends
needs the escape rules, so this script has a small scanner for them -- the same
job Toml.Parse does, done independently, which is the point: if the two ever
disagree about where a triple-quoted literal ends, this suite says so.

Invalid cases are included only when the scanner can find a complete literal
with nothing but whitespace or a comment after it. An unterminated string is
not a literal this module is being asked about, so those are skipped and
counted.

The file it writes is tools/templates/Literals.geng rendered with the two
tables; the Gren lives there rather than in a string constant here.

Run from the package root:  python3 tools/gen-strings.py
"""

import json
import os
import re
import sys

from jinja2 import Environment, FileSystemLoader

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

TESTS = "vendor/toml-test/tests"
# Valid cases come from both directories; invalid ones only from string/,
# because invalid/key is largely about duplicate and conflicting keys, whose
# literals are perfectly well formed and which this module has no opinion on.
DIRS = ["string", "key"]
INVALID_DIRS = ["string"]

ASSIGN = re.compile(r'^([A-Za-z0-9_\-]+|"(?:[^"\\]|\\.)*"|\'[^\']*\')\s*=\s*')


def end_of_literal(text, start):
    """Index just past the literal beginning at `start`, or None."""
    if text.startswith("'''", start):
        return end_multi(text, start, "'", escapes=False)
    if text.startswith('"""', start):
        return end_multi(text, start, '"', escapes=True)
    if text[start:start + 1] == "'":
        return end_single(text, start, "'", escapes=False)
    if text[start:start + 1] == '"':
        return end_single(text, start, '"', escapes=True)
    return None


def end_single(text, start, quote, escapes):
    i = start + 1
    while i < len(text):
        if text[i] == "\n":
            return None
        if escapes and text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return None


def end_multi(text, start, quote, escapes):
    closing = quote * 3
    i = start + 3
    while i < len(text):
        if escapes and text[i] == "\\":
            i += 2
            continue
        if text.startswith(closing, i):
            end = i + 3
            # mlb-quotes: a body may end with one or two more of them
            while end < len(text) and text[end] == quote and end - i < 5:
                end += 1
            return end
        i += 1
    return None


def literals(path):
    """key -> raw literal, for the assignments whose value is a string."""
    text = open(path, encoding="utf-8").read()
    found = {}
    offset = 0
    for line in text.split("\n"):
        match = ASSIGN.match(line)
        if match:
            start = offset + match.end()
            end = end_of_literal(text, start)
            if end is not None:
                found[match.group(1).strip("\"'")] = text[start:end]
        offset += len(line) + 1
    return found


def gren_string(text):
    """A Gren string literal for this text.

    The escapes match what gren-format normalises to -- \\n, \\r and \\t by name,
    everything else below space as lowercase four-digit \\u{...} -- so that the
    generated file needs no reformatting.

    Anything above ASCII goes in as itself rather than as a \\u{...} escape.
    That is partly because it reads better and partly because gren 0.6.6
    mis-encodes \\u{FFFF} in a string literal -- it emits the surrogate pair for
    0xFFFF - 0x10000, so the escape yields U+D7FF U+DFFF instead of one
    character -- and those two are not a surrogate pair, so the string comes out
    one character too long with an unpaired low surrogate in it. See
    https://github.com/gren-lang/compiler/issues/384. Source files are UTF-8, so
    writing the character is both correct and unaffected.
    """
    out = []
    for char in text:
        code = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif code < 0x20 or code == 0x7F:
            # lowercase hex, four digits: what gren-format normalises to, so
            # that the generated file is already formatted
            out.append("\\u{%04x}" % code)
        else:
            out.append(char)
    return "".join(out)


def collect(manifest):
    good, bad, skipped = [], [], 0
    for directory in DIRS:
        valid = os.path.join(TESTS, "valid", directory)
        if os.path.isdir(valid):
            for name in sorted(os.listdir(valid)):
                if not name.endswith(".json"):
                    continue
                rel = "valid/%s/%s.toml" % (directory, name[:-5])
                if rel not in manifest:
                    continue
                expected = json.load(open(os.path.join(valid, name)))
                source = literals(os.path.join(valid, name[:-5] + ".toml"))
                for key, item in expected.items():
                    if not isinstance(item, dict) or item.get("type") != "string":
                        continue
                    if key in source:
                        good.append((rel, source[key], item["value"]))
                    else:
                        skipped += 1

        invalid = os.path.join(TESTS, "invalid", directory)
        if directory in INVALID_DIRS and os.path.isdir(invalid):
            for name in sorted(os.listdir(invalid)):
                if not name.endswith(".toml"):
                    continue
                rel = "invalid/%s/%s" % (directory, name)
                if rel not in manifest:
                    continue
                path = os.path.join(invalid, name)
                try:
                    text = open(path, encoding="utf-8").read()
                except UnicodeDecodeError:
                    skipped += 1
                    continue
                picked = None
                for match in ASSIGN.finditer(text):
                    if match.start() and text[match.start() - 1] != "\n":
                        continue
                    end = end_of_literal(text, match.end())
                    if end is None:
                        continue
                    # Only when the literal is the whole of the value: a bad
                    # literal followed by more text is a different failure.
                    rest = text[end:].split("\n", 1)[0].strip()
                    if rest == "" or rest.startswith("#"):
                        picked = text[match.end():end]
                        break
                if picked is None:
                    skipped += 1
                else:
                    bad.append((rel, picked))
    return good, bad, skipped


def render(good, bad, skipped):
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template("Literals.geng").render(
        good=good, bad=bad, skipped=skipped
    )


def main():
    manifest = set(open(os.path.join(TESTS, "files-toml-1.1.0")).read().split())
    good, bad, skipped = collect(manifest)
    if not good or not bad:
        sys.exit("found no cases; is vendor/toml-test checked out?")

    good_rows = [
        {"raw": gren_string(raw), "want": gren_string(want), "file": path}
        for path, raw, want in good
    ]
    bad_rows = [{"raw": gren_string(raw), "file": path} for path, raw in bad]

    with open("tests/src/Literals.geng", "w") as out:
        out.write(render(good_rows, bad_rows, skipped))
    print("%d valid, %d invalid, %d skipped" % (len(good), len(bad), skipped))


if __name__ == "__main__":
    main()
