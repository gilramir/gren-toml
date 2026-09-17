#!/usr/bin/env python3
"""Regenerate tests/src/Numbers.geng from the official TOML test suite.

Every integer and float in the valid/ and invalid/ trees, filtered to the
1.1.0 manifest. The valid cases are paired with the expected value from the
.json sibling; the invalid ones only have to be refused.

The expected values are compared numerically rather than as text, because
toml-test writes them as float64 already rounded -- `3e1_4` comes back as
`3.0e14` and `-0.0` as `-0`. The Gren side parses the expected string with the
same BigDecimal and compares, so the rendering never enters into it.

The file it writes is tools/templates/Numbers.geng rendered with the two
tables; the Gren lives there rather than in string constants here.

Run from the package root:  python3 tools/gen-numbers.py
"""

import json
import os
import re
import sys

from jinja2 import Environment, FileSystemLoader

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

TESTS = "vendor/toml-test/tests"
DIRS = ["integer", "float"]
KINDS = ("integer", "float")

# A line this script can read: one key, one =, one scalar, nothing nested. The
# suite keeps its arrays and tables in other directories, so what this skips is
# a handful of lines rather than a category of case.
SIMPLE = re.compile(r'^([A-Za-z0-9_\-]+|"[^"]*"|\'[^\']*\')\s*=\s*([^\s#][^#]*?)\s*(?:#.*)?$')


def assignments(path):
    found = {}
    for line in open(path):
        match = SIMPLE.match(line.strip())
        if match:
            found[match.group(1).strip("\"'")] = match.group(2)
    return found


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
                source = assignments(os.path.join(valid, name[:-5] + ".toml"))
                for key, value in expected.items():
                    if not isinstance(value, dict) or value.get("type") not in KINDS:
                        continue
                    if key not in source:
                        skipped += 1
                        continue
                    good.append((rel, source[key], value["type"], value["value"]))

        invalid = os.path.join(TESTS, "invalid", directory)
        if os.path.isdir(invalid):
            for name in sorted(os.listdir(invalid)):
                if not name.endswith(".toml"):
                    continue
                rel = "invalid/%s/%s" % (directory, name)
                if rel not in manifest:
                    continue
                for line in open(os.path.join(invalid, name)):
                    match = SIMPLE.match(line.strip())
                    if match:
                        bad.append((rel, match.group(2)))
                        break
                else:
                    skipped += 1
    return good, bad, skipped


def escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def render(good, bad):
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template("Numbers.geng").render(good=good, bad=bad)


def main():
    manifest = set(open(os.path.join(TESTS, "files-toml-1.1.0")).read().split())
    good, bad, skipped = collect(manifest)
    if not good or not bad:
        sys.exit("found no cases; is vendor/toml-test checked out?")

    good_rows = [
        {"kind": kind, "text": escape(text), "want": escape(want), "file": path}
        for path, text, kind, want in good
    ]
    bad_rows = [{"text": escape(text), "file": path} for path, text in bad]

    with open("tests/src/Numbers.geng", "w") as out:
        out.write(render(good_rows, bad_rows))
    print("%d valid, %d invalid, %d lines skipped as not simple assignments"
          % (len(good), len(bad), skipped))


if __name__ == "__main__":
    main()
