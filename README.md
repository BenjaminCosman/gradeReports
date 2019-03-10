# gradeReports

[![CircleCI](https://circleci.com/gh/BenjaminCosman/gradeReports.svg?style=svg)](https://circleci.com/gh/BenjaminCosman/gradeReports)

Very much a work in progress; contact owner with questions.

## Overview

This tool consists of two scripts. `main.py` reads in a config file that
describes your class (names and values of assignments, etc) as well as some
number of source spreadsheets (roster, gradesheets, etc, in either csv or xlsx
form), and produces formatted grade reports for each student.

The second script, `autoconf.py`, helps you build the config file required by
`main.py`. It takes in source spreadsheets and outputs its best guess for the
config file, which you can then edit. It can also be run in an incremental
fashion, where it takes in an existing config file as well and adds to it.

## Installation

Requires Python. (possibly even Python 3.7.2+ ?)

### Recommended: set up a virtual environment

`python3 -m venv .venv`

(If you do this, make sure to activate that environment for the rest of
installation as well as whenever you run the scripts:)

`source .venv/bin/activate` (This may vary depending on your shell)

### Install all required python packages

`pip3 install -r requirements.txt`

### Testing your installation

There is an example class in `examples`. Generate reports for that class:

`python3 main.py examples/config.json`

This should dump simplified text versions of the reports to your terminal, and
also produce reports suitable for distribution in a `reports` folder.

## Running

Once you already have your sources and a config file, just run

`python3 main.py CONFIG_FILE`

## Configuration

First download all sources. Now you need to create a JSON config file. Full
documentation follows, but the easiest way to do this may be to just run autoconf:

`python3 autoconf.py SOURCE_FOLDER` or `python3 autoconf.py SOURCE1 SOURCE2 ...`

This will create a config file at `tempConfig.json` (use `-o` to choose a
different output filename). Then as long as your sources were formatted in ways
autoconf could understand, you should be able to immediately generate reports
with `main.py`. You can then see directly what different parts of the config
file are doing, and edit them to get the result you want.

The example class config (`examples/config.json`) may also be useful for
understanding these files.

### The details

key: "studentAttributes"
value: A dictionary of non-grade attributes that are associated with each student,
e.g. name, student ID. For example:
```
"studentAttributes": {
    "Section": {"onePerStudent": true},
    "Student ID": {"identifiesStudent": true, "onePerStudent": true, "filters": ["strip", "toUpper"]},
}
```
- "identifiesStudent" (default: false) should be set to true if the attribute
can be (and is) used to uniquely identify a student. For example, a Student ID
can identify a student; a name usually can NOT (two people can have the same name).
- "onePerStudent" (default: false) should be set to true if each student should only
have one of this attribute. For example, each student probably has only one
university-issued Student ID, but they may have multiple email addresses.
- "filters" (default: []) can be set to a list of operations that should be
performed to clean and validate this attribute whenever it is read. For example,
if students are asked to enter their student ids on a web form, then you may want
to strip off any whitespace and change any letters to uppercase. For a full list
of filter options (and to add your own, if needed), see the definition of
`filtersAndChecks` in `main.py`.

key: "sources"
value: not yet documented; see `examples/config.json`

key: "outputs"
value: not yet documented; see `examples/config.json`

## Known issues

- No two assignments can have the same name, even if they are in different categories (e.g. "Week 1" for both discussion attendance and weekly review quiz), or else the grades from one will silently overwrite the other's.
- Scored google forms *display* the score as SCORE / MAX but *store* only the
raw score. So if you download it as a csv the formatting is turned into the
canonical text and you will
need the "stripDenominator" filter; if you download it as an xlsx then the
formatting remains visible to you but hidden from the code, so you will *not*
want that filter and also autoconf may do a worse job of guessing the intended
max score.