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

### Clone the repository

`git clone https://github.com/BenjaminCosman/gradeReports.git`

`cd gradeReports`

### Recommended: set up a virtual environment

`python3 -m venv .venv`

If you do this, make sure to activate that environment for the rest of
installation as well as whenever you run the scripts:

`source .venv/bin/activate` (This may vary depending on your shell)

### Install all required python packages

`pip3 install -r requirements.txt`

### Testing your installation

Check if the commands in the first few steps of the tutorial work (see below).

## Tutorial

It is week 3 of the fictional class CSE777, and we'd like to generate a preliminary progress report for our students. We've already downloaded all relevant files to local folder `examples/data`: the roster, gradescope gradebook, iclicker and discussion attendance spreadsheets, and google forms responses for quizzes, surveys, and clicker registrations.

1. Later steps will show you how to produce a config file, but for now we'll use the one at `examples/config.json`. Once we have this config file, all we need to do to generate reports is run:

`python3 main.py examples/config.json --pdf`

You should see simplified text versions of the reports on your terminal, and formatted reports suitable for distribution in a `reports` folder.
(The suggested way to distribute these reports would be to upload them all to gradescope as a 0-point assignment; gradescope can automatically match the files with students using the name and student ID fields.)

2. Now we will work backwards and produce that config file needed for step 1. Run:

`python3 autoconf.py examples/data`

This will produce a config file at `tempConfig.json`. Now try using it as in step 1 (except since we're not uploading these reports, there's no need to spend the time converting the html reports to pdfs so we leave out the `--pdf` option from now on):

`python3 main.py tempConfig.json`

Open one of the generated reports (e.g. `reports/A12345678.html`). It  should look mostly correct and ready for distribution, with a few exceptions:

- There are some extra assignments, like clickerRegistrations, and discussion attendance through week 10.
- All headers and some assignments need to be renamed.

These are quick to fix manually:

- Open `tempConfig.json`
- At the bottom of the file (`outputs` -> `content`), rename the `title` values.
- Find and delete unwanted assignments in the middle. For example, to remove weeks 4-10 of discussion attendance, find and delete the objects containing the text `Week 4`, `Week 5`, etc. *Make sure the resulting config file is still valid JSON: in particular, the last element of a list needs to NOT have a comma after it (and each other element does need a comma)*
- For any assignment where a Timestamp column was detected, autoconf has inserted a `due_date` field in the distant future. If there is a deadline you want to enforce, change these fields; late assignemnts will get 0 credit.

After editing the file you can re-generate the reports (`python3 main.py tempConfig.json`) and you should see your changes reflected there. That's it for the most important features; at this point you should be able to generate a real report using your own data.

COMING SOON:

3. Now it's week 5 and you need a config file that includes the last two weeks of assignments. TODO Right now *incremental* autoconfigure doesn't work well, so either edit your old config manually or create a brand new one with autoconf.py and edit that one. Soon however you will be able to automatically update your old config using

`python3 autoconf.py -i oldConfig.json`

## Documentation in non-tutorial format

### Running

Once you already have your sources and a config file, just run

`python3 main.py CONFIG_FILE`

### Configuration

First download all sources. Now you need to create a JSON config file. Full
documentation follows, but the easiest way to do this may be to just run autoconf:

`python3 autoconf.py SOURCE1 SOURCE2 ...`

where each SOURCE is either a csv/xlsx file or a folder containing such files.

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
`filtersAndChecks` in `lib/munge.py`.

key: "sources"
value: not yet documented; see `examples/config.json`

key: "outputs"
value: not yet documented; see `examples/config.json`

## Known issues

- No two assignments can have the same name, even if they are in different
categories (e.g. "Week 1" for both discussion attendance and weekly review
quiz), or else the grades from one will silently overwrite the other's.
- Scored google forms *display* the score as SCORE / MAX but *store* only the
raw score. So if you download it as a csv the formatting is turned into the
canonical text and you will
need the "stripDenominator" filter; if you download it as an xlsx then the
formatting remains visible to you but hidden from the code, so you will not
need that filter and also autoconf may do a worse job of guessing the intended
max score.
