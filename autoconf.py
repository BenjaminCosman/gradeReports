import json, re, argparse, glob
from enum import Enum
from pathlib import Path
import pyexcel as pe

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)
logging.addLevelName(logging.WARNING, "\033[33m%s\033[0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[31m%s\033[0m" % logging.getLevelName(logging.ERROR))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from lib.fileFormats import getRows
from lib.mung import checkAndClean
from lib.constants import ALL_DEFAULT_FILTERS

FileType = Enum('FileType', 'ROSTER GRADESCOPE SCORED_GOOGLE_FORM UNSCORED_GOOGLE_FORM CLICKERS OTHER')

keywords = {
    "Roster Name": [r'name\b'],
    "Section": [r'\bsection\b', r'\bsect\b', r'\bsec\b'],
    "Email": [r'\bemail\b'],
    "Student ID": [r'\bpid\b', r'\bsid\b'],
    "Clicker ID": [r'\bclicker\b', r'\biclicker\b', r'\bremote\b'],

    # "homework": [r'\bhw\b', r'\bhomework\b', r'\bassignment\b'],
    # "quiz": [r'\bquiz\b'],
    # "exam": [r'\bexam\b'],
    # "test": [r'\btest\b'],
}

def inferTypeFromFields(fields):
    if fields[:5] == ['Sect ID', 'Course', 'Title', 'SecCode', 'Instructor']:
        return FileType.ROSTER

    if fields[:4] == ['Last Name', 'First Name', 'Student ID', 'Remote ID'] and any([re.match(r'^Session \d+', field) for field in fields]):
        return FileType.CLICKERS

    lastCol = ""
    for col in fields:
        if col == lastCol + " - Max Points":
            return FileType.GRADESCOPE
        lastCol = col

    if fields[0] == 'Timestamp':
        if 'Score' in fields:
            return FileType.SCORED_GOOGLE_FORM
        else:
            return FileType.UNSCORED_GOOGLE_FORM

    return FileType.OTHER

def updateOtherConfig(allAttrs, sourceConf, rows, fileType):
    '''updates sourceConf in place. Returns True if successful; False if the
    file could not be used (i.e. appeared to contain no grade data)'''
    fields = rows[0].keys()
    if len(set(fields)) != len(fields):
        logger.warning("duplicate column!")

    (attrConfig, ignoredCols) = guessAttrConfig(fields, allAttrs)
    if len(attrConfig.keys()) == 0:
        logger.debug("  No student attributes detected; ignoring")
        return False

    itemConfig = []

    if fileType in [FileType.OTHER, FileType.CLICKERS]:
        for item in fields:
            if item not in ignoredCols and item not in attrConfig.keys():
                filters = ALL_DEFAULT_FILTERS
                # try:
                #     [float(checkAndClean(row[item], filters)) for row in rows]
                # except ValueError:
                #     continue
                if fileType == FileType.CLICKERS:
                    itemType = "clickers"
                else:
                    itemType = guessItemType(item)
                itemConfig.append({"name": item, "scoreCol": item, "max_points": 1, "type": itemType, "filters": filters})

    if fileType == FileType.SCORED_GOOGLE_FORM:
        row = rows[0]
        score = row['Score']
        if '/' in score:
            maxPoints = int(score.split('/')[1].strip())
            filters = ["stripDenominator"]
        else:
            maxPoints = max([int(x['Score']) for x in rows])
            filters = []
        name = sourceConf.get("sheetName", Path(sourceConf['file']).name)
        itemConfig.append({"name": name, "scoreCol": "Score", "max_points": maxPoints, "type": fileType.name, "filters": ["stripDenominator"], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    if fileType == FileType.UNSCORED_GOOGLE_FORM:
        name = sourceConf.get("sheetName", Path(sourceConf['file']).name)
        itemConfig.append({"name": name, "max_points": 1, "type": fileType.name, "filters": [], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    sourceConf.update({
        # "_autoconf_fileType": fileType.name,
        "attributes": attrConfig,
        "items": itemConfig, #[NoIndent(x) for x in itemConfig],
        # "_autoconf_ignoredCols": ignoredCols
    })
    return True

def guessItemType(item):
    item = item.lower()
    if "hw" in item or "assignment" in item or "homework" in item:
        return "Homework"
    return "unknown"

def guessAttrConfig(potentialAttrFields, allAttrs):
    keywordLookup = {}
    for attr in allAttrs:
        if attr in keywords:
            keywordLookup.update({keyword:attr for keyword in keywords[attr]})

    attrConfig = {}
    ignoredCols = []
    for item in potentialAttrFields:
        itemLowered = item.lower()

        # First, check if the column name is referring to a student attribute
        identifiedAttr = None
        if itemLowered in [attr.lower() for attr in allAttrs]:
            identifiedAttr = item
        else:
            # itemWords = itemLowered.split()
            for (keyword, attr) in keywordLookup.items():
                if re.search(keyword, itemLowered):
                    identifiedAttr = attr
                    break

        # If so, record it and move on to next column
        if identifiedAttr is not None:
            if identifiedAttr in attrConfig.values():
                old = next(key for key, value in attrConfig.items() if value == identifiedAttr)
                logger.warning(f"found two columns for attribute {identifiedAttr}: `{old}` and `{item}`")
                ignoredCols.append(item)
            elif allAttrs[identifiedAttr].get("identifiesStudent", False):
                attrConfig.update({item: identifiedAttr})
            else:
                ignoredCols.append(item)
    return (attrConfig, ignoredCols)

def updateGradescopeConfig(allAttrs, sourceConf, rows):
    fields = rows[0].keys()
    assignments = []
    attrs = []
    for field in fields:
        if field + " - Max Points" in fields:
            assignments.append(field)
        elif " - Max Points" not in field and " - Lateness" not in field:
            attrs.append(field)

    (attrConfig, ignoredCols) = guessAttrConfig(attrs, allAttrs)

    itemConfig = []
    for item in assignments:
        itemType = guessItemType(item)
        maxPoints = int(rows[0][item + " - Max Points"])
        itemConfig.append({"name": item, "scoreCol": item, "max_points": maxPoints, "type": itemType, "filters": ["NoneTo0"]})

    sourceConf.update({
        "attributes": attrConfig,
        "items": itemConfig,
    })

def updateConfig(globalConfigObj, sourceConf, rows):
    fileType = inferTypeFromFields(list(rows[0].keys()))
    logger.debug(f"\tInferred type: {fileType.name}")
    if fileType == FileType.ROSTER:
        # It's not a proper csv; more like 2 on top of each other.
        # It gets a special flag in config
        sourceConf.update({
            "isRoster": True,
            "attributes": {
                "Email": "Email",
                "PID": "Student ID",
                "Student": "Roster Name"
            },
            "items": []
        })
    elif fileType == FileType.GRADESCOPE:
        updateGradescopeConfig(globalConfigObj['studentAttributes'], sourceConf, rows)
    elif fileType in [FileType.SCORED_GOOGLE_FORM, FileType.UNSCORED_GOOGLE_FORM, FileType.CLICKERS, FileType.OTHER]:
        usable = updateOtherConfig(globalConfigObj['studentAttributes'], sourceConf, rows, fileType)
        if not usable:
            return
    else:
        raise Exception(f"unknown filetype {fileType.name}")

    globalConfigObj["sources"].append(sourceConf)


def main(sources, partialConfig, outPath):
    if partialConfig:
        with open(partialConfig) as f:
            globalConfigObj = json.load(f)
    else:
        globalConfigObj = {}

    if "studentAttributes" not in globalConfigObj:
        globalConfigObj["studentAttributes"] = {
            "Roster Name": {"onePerStudent": True},
            "Section": {"onePerStudent": True},
            "Email": {},
            "Student ID": {"identifiesStudent": True, "onePerStudent": True, "filters": ["strip", "toUpper", "ucsdIDCheck"]},
            "Clicker ID": {"identifiesStudent": True, "filters": ["strip", "remove#", "8char", "toUpper"]}
        }
    if "sources" not in globalConfigObj:
        globalConfigObj["sources"] = []
    if "outputs" not in globalConfigObj:
        globalConfigObj["outputs"] = {
            "report-name": "CSEnn Grade Report",
            "disclaimer-text": "These are all the scores recorded for you in this course. If there are any discrepancies between the scores you see here and your own records, email...",
            "content": []
        }

    # ignoredFiles = globalConfigObj.get("_autoconf_ignoredFiles", [])
    preconfiguredFiles = list(map(getSource, globalConfigObj["sources"]))
    for source in sources:
        sourcePath = Path(source)
        if sourcePath.is_dir():
            logger.debug(f"Searching `{sourcePath}` for csv and xlsx files...")
            sourceIter = glob.iglob(str(sourcePath/'**'), recursive=True)
        else:
            sourceIter = [source]
        sourceIter = [Path(filename) for filename in sourceIter]
        for filePath in sourceIter:
            if filePath.is_dir():
                continue
            logger.debug(f"Handling file `{filePath}`")
            # if filename in ignoredFiles:
            #     print("Skipping because of _autoconf_ignoredFiles")
            #     continue
            if str(filePath) in preconfiguredFiles:
                logger.debug("Skipping because file is already configured")
                continue
            ext = filePath.suffix
            if ext == ".csv":
                rows = getRows(filePath)
                sourceConf = {"file": str(filePath)}
                updateConfig(globalConfigObj, sourceConf, rows)
            elif ext == ".xlsx":
                book = pe.get_book(file_name=str(filePath), auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)
                for name in book.sheet_names():
                    logger.debug(f"Found sheet `{name}`")
                    # if [filename, name] in ignoredFiles:
                    #     print("Skipping because of _autoconf_ignoredFiles")
                    #     continue
                    if [str(filePath), name] in preconfiguredFiles:
                        logger.debug("Skipping because file is already configured")
                        continue
                    rows = getRows(filePath, sheetName=name)
                    sourceConf = {"file": str(filePath), "sheetName": name}
                    updateConfig(globalConfigObj, sourceConf, rows)
            else:
                logger.debug("  Ignoring.")
                continue
    globalConfigObj["sources"].sort(key=mySort, reverse=True)

    categories = set()
    for sourceData in globalConfigObj['sources']:
        for item in sourceData['items']:
            categories.add(item['type'])
    oldCategories = set(map(lambda z: z['from'], globalConfigObj['outputs']['content']))
    globalConfigObj['outputs']['content'] += [{ "title": f"[Rename me - display name of {c}]", "from": c} for c in categories.difference(oldCategories)]

    outPath.write_text(json.dumps(globalConfigObj, indent=2, separators=(',', ': ')))
    logger.info(f"Wrote config file to `{outPath}`")

def getSource(sourceObj):
    filename = sourceObj["file"]
    if "sheetname" in sourceObj:
        return [filename, sourceObj["sheetname"]]
    else:
        return filename

# TODO: remove dependency on order of sources - right now sources that define and
# connect student attributes should come first (e.g. roster, then clicker registrations)
def mySort(obj):
    return (
        "isRoster" in obj,
        len(obj["attributes"])
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('sourcesDir', metavar='SOURCE', type=str, nargs='*',
        help='A csv or xlsx source (roster, gradesheet, etc) or a directory containing such sources')
    parser.add_argument('-i', metavar='CONFIG_FILE', type=str, help='An initial config file to add to')
    parser.add_argument('-o', metavar='OUTPUT_FILE', type=str, help='Output file (default: tempConfig.json)', default='tempConfig.json')
    args = parser.parse_args()
    main(args.sourcesDir, args.i, Path(args.o))
