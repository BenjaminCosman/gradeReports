# gradeReports

Very much a work in progress; contact owner with questions.

## Installation

Requires Python (possibly even Python 3.7.2+ ?)

- Recommended: set up a virtual environment

`python3 -m venv .venv`

(If you do this, make sure to activate that environment for the rest of installation as well as whenever you run the programs:)

`source .venv/bin/activate` (This may vary depending on your shell)

- Install all required python packages

`pip3 install -r requirements.txt`

## Configuration

Edit `config.json`. See `examples/config.json` for a more complete example.

## Running

Run `python3 main.py CONFIG_FILE`

## Other

`configure.py` should be ignored for now but will eventually be usable to write the config file for you.

## Known issues

- No two assignments can have the same name, even if they are in different categories (e.g. "Week 1" for both discussion attendance and weekly review quiz), or else the grades from one will silently overwrite the other's.
