# gradeReports

## Installation

### Install dependencies

`pip install pdfkit`

## Configuration

Edit `config.json`. See `examples/config.json` for a more complete example.

## Running

Run `python3 main.py`

## Other

Very much a work in progress; contact owner with questions. `configure.py` should be ignored for now but will eventually be usable to write `config.json` for you.

## Known issues

- No two assignments can have the same name, even if they are in different categories (e.g. "Week 1" for both discussion attendance and weekly review quiz), or else the grades from one will silently overwrite the other's.
