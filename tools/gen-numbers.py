#!/usr/bin/env python3
"""Regenerate tests/src/Numbers.gren from the official TOML test suite.

Every integer and float in the valid/ and invalid/ trees, filtered to the
1.1.0 manifest. The valid cases are paired with the expected value from the
.json sibling; the invalid ones only have to be refused.

The expected values are compared numerically rather than as text, because
toml-test writes them as float64 already rounded -- `3e1_4` comes back as
`3.0e14` and `-0.0` as `-0`. The Gren side parses the expected string with the
same BigDecimal and compares, so the rendering never enters into it.

Run from the package root:  python3 tools/gen-numbers.py
"""

import json
import os
import re
import sys

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


def table(rows):
    lines = ["    [ " + rows[0]] + ["    , " + row for row in rows[1:]] + ["    ]"]
    return "\n".join(lines) + "\n"


HEAD = """module Numbers exposing (numbersSuite)

{-| Every integer and float in the official TOML test suite.

%d values that must parse and %d that must not, lifted out of `toml-test` and
filtered to the `files-toml-1.1.0` manifest. Most of the invalid ones are about
one of two rules, which is why they are worth this much attention: where an
underscore may go, and which leading zeroes the grammar allows.

The comparison is numeric, not textual. `toml-test` writes its expected floats
as `float64` has already rounded them -- `3e1_4` comes back as `3.0e14` and
`-0.0` as `-0` -- so both sides are parsed and compared as values. What is being
checked here is the reading, not the writing; the writing is checked by the
round-trip suite, which compares whole files byte for byte.

The invalid cases have to be refused by *both* `integer` and `float`, since the
parser will try both.

@docs numbersSuite

-}

import Array exposing (Array)
import Basics exposing (..)
import BigDecimal
import BigInt
import Expect
import Maybe exposing (Maybe(..))
import String
import Task
import Test.Runner.UnitNode as U
import Toml.Ast as Ast exposing (FloatValue(..), Sign(..))
import Toml.Number as Number


type alias Good =
    { kind : String, text : String, want : String, file : String }


type alias Bad =
    { text : String, file : String }


good : Array Good
good =
"""


MID = """

bad : Array Bad
bad =
"""


TAIL = """

{-| Whether the value read out of the text is the value the suite expects.
Numerically: the expected string goes through the same reader.
-}
matches : Good -> Bool
matches row =
    if row.kind == "integer" then
        Maybe.map2 (\\got want -> BigInt.compare got want == EQ)
            (Number.integer row.text)
            (BigInt.fromString row.want)
            |> Maybe.withDefault False

    else
        when Number.float row.text is
            Just (Finite got) ->
                BigDecimal.fromString row.want
                    |> Maybe.map (\\want -> BigDecimal.compare got want == EQ)
                    |> Maybe.withDefault False

            Just (Infinite Positive) ->
                row.want == "inf"

            Just (Infinite Negative) ->
                row.want == "-inf"

            Just (NotANumber _) ->
                row.want == "nan"

            Nothing ->
                False


{-| -}
numbersSuite : U.Suite
numbersSuite =
    U.suite
        { name = "Numbers"
        , setUpSuite = U.noSuiteFixture
        , tearDownSuite = U.noTearDown
        , setUp = \\_ -> Task.succeed {}
        , tearDown = U.noTearDown
        , tests =
            -- A generated table that came out empty would pass everything
            -- below it without checking anything.
            [ U.test "the tables are the size toml-test says they are" <| \\_ ->
                Task.succeed
                    (Expect.equal { good = %d, bad = %d }
                        { good = Array.length good, bad = Array.length bad }
                    )
            , U.test "every number toml-test accepts reads as the expected value" <| \\_ ->
                Task.succeed
                    (Expect.equal []
                        (good
                            |> Array.keepIf (\\row -> not (matches row))
                            |> Array.map (\\row -> row.file ++ ": " ++ row.text ++ ", wanted " ++ row.want)
                        )
                    )
            , U.test "and every one it rejects is refused as both an integer and a float" <| \\_ ->
                Task.succeed
                    (Expect.equal []
                        (bad
                            |> Array.keepIf
                                (\\row ->
                                    Number.integer row.text /= Nothing
                                        || Number.float row.text /= Nothing
                                )
                            |> Array.map (\\row -> row.file ++ ": " ++ row.text)
                        )
                    )
            ]
        }
"""


def main():
    manifest = set(open(os.path.join(TESTS, "files-toml-1.1.0")).read().split())
    good, bad, skipped = collect(manifest)
    if not good or not bad:
        sys.exit("found no cases; is vendor/toml-test checked out?")

    good_rows = [
        '{ kind = "%s", text = "%s", want = "%s", file = "%s" }'
        % (kind, escape(text), escape(want), path)
        for path, text, kind, want in good
    ]
    bad_rows = ['{ text = "%s", file = "%s" }' % (escape(text), path) for path, text in bad]

    with open("tests/src/Numbers.gren", "w") as out:
        out.write(HEAD % (len(good), len(bad)) + table(good_rows)
                  + MID + table(bad_rows)
                  + (TAIL % (len(good), len(bad))))
    print("%d valid, %d invalid, %d lines skipped as not simple assignments"
          % (len(good), len(bad), skipped))


if __name__ == "__main__":
    main()
