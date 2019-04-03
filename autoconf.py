import re, argparse, glob
from enum import Enum
from pathlib import Path
import pyexcel as pe

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)
logging.addLevelName(logging.WARNING, "\033[33m%s\033[0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[31m%s\033[0m" % logging.getLevelName(logging.ERROR))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from lib.spreadsheetReader import getRows
from lib.mung import checkAndClean
from lib.constants import ASSIGNMENTS_KEY, ALL_DEFAULT_FILTERS
from lib.config import loadConfig, saveConfig

FileType = Enum('FileType', 'ROSTER GRADESCOPE SCORED_GOOGLE_FORM UNSCORED_GOOGLE_FORM CLICKERS OTHER')

DEFAULT_ATTR_DICT = {
    "Roster Name": {"onePerStudent": True},
    "Section": {"onePerStudent": True},
    "Email": {},
    "Student ID": {"identifiesStudent": True, "onePerStudent": True, "filters": ["strip", "toUpper", "ucsdIDCheck"]},
    "Clicker ID": {"identifiesStudent": True, "filters": ["strip", "remove#", "8char", "toUpper"]}
}

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

def updateOtherConfig(allAttrs, sourceConf, rows, fileType, allNames):
    '''updates sourceConf and allNames in place. Returns True if successful; False if the
    file could not be used (i.e. appeared to contain no grade data)'''
    fields = rows[0].keys()
    if len(set(fields)) != len(fields):
        logger.warning("duplicate column!")

    (attrConfig, ignoredAttrCols) = guessAttrConfig(fields, allAttrs)
    if len(attrConfig.keys()) == 0:
        logger.debug("  No student attributes detected; ignoring")
        return False

    itemConfig = []

    if fileType in [FileType.OTHER, FileType.CLICKERS]:
        for item in fields:
            if item not in ignoredAttrCols and item not in attrConfig.keys():
                filters = ALL_DEFAULT_FILTERS
                # try:
                #     [float(checkAndClean(row[item], filters)) for row in rows]
                # except ValueError:
                #     continue
                if fileType == FileType.CLICKERS:
                    itemType = "clickers"
                else:
                    itemType = guessItemType(item)
                name = forceUniqueName(item, allNames)
                itemConfig.append({"name": name, "scoreCol": item, "max_points": 1, "type": itemType, "filters": filters})

    if fileType == FileType.SCORED_GOOGLE_FORM:
        row = rows[0]
        score = row['Score']
        if '/' in score:
            maxPoints = int(score.split('/')[1].strip())
            # filters = ["stripDenominator"]
        else:
            maxPoints = max([int(x['Score']) for x in rows])
            # filters = []
        name = sourceConf.get("sheetName") or Path(sourceConf['file']).stem
        name = forceUniqueName(name, allNames)
        itemConfig.append({"name": name, "scoreCol": "Score", "max_points": maxPoints, "type": fileType.name, "filters": ALL_DEFAULT_FILTERS, "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    if fileType == FileType.UNSCORED_GOOGLE_FORM:
        name = sourceConf.get("sheetName") or Path(sourceConf['file']).stem
        name = forceUniqueName(name, allNames)
        itemConfig.append({"name": name, "max_points": 1, "type": fileType.name, "filters": ALL_DEFAULT_FILTERS, "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    sourceConf.update({
        # "_autoconf_fileType": fileType.name,
        "attributes": attrConfig,
        ASSIGNMENTS_KEY: itemConfig, #[NoIndent(x) for x in itemConfig],
        # "_autoconf_ignoredAttrCols": ignoredAttrCols
    })
    return True

def forceUniqueName(name, allNames):
    uniqueName = getUniqueName(name, allNames)
    allNames.add(uniqueName)
    return uniqueName

def getUniqueName(name, allNames):
    if name not in allNames:
        return name
    idx = 2
    while True:
        testName = name + "#" + str(idx)
        if testName not in allNames:
            return testName
        idx += 1

def guessItemType(item):
    item = item.lower()
    if "hw" in item or "assignment" in item or "homework" in item:
        return "homework"
    return "unknown"

def guessAttrConfig(potentialAttrFields, allAttrs):
    keywordLookup = {}
    for attr in allAttrs:
        if attr in keywords:
            keywordLookup.update({keyword:attr for keyword in keywords[attr]})

    attrConfig = {}
    ignoredAttrCols = []
    attrsLowered = [attr.lower() for attr in allAttrs]
    for item in potentialAttrFields:
        # Check if the column name is referring to a student attribute
        identifiedAttr = None
        itemLowered = item.lower()
        if itemLowered in attrsLowered:
            identifiedAttr = item
        else:
            for (keyword, attr) in keywordLookup.items():
                if re.search(keyword, itemLowered):
                    identifiedAttr = attr
                    break

        if identifiedAttr == None:
            continue

        if identifiedAttr in attrConfig.values():
            old = next(key for key, value in attrConfig.items() if value == identifiedAttr)
            logger.warning(f"found two columns for attribute {identifiedAttr}: `{old}` and `{item}`")
            ignoredAttrCols.append(item)
        elif allAttrs[identifiedAttr].get("identifiesStudent", False):
            attrConfig.update({item: identifiedAttr})
        else:
            ignoredAttrCols.append(item)
    return (attrConfig, ignoredAttrCols)

def updateGradescopeConfig(allAttrs, sourceConf, rows, allNames):
    fields = rows[0].keys()
    assignments = []
    attrs = []
    for field in fields:
        if field + " - Max Points" in fields:
            assignments.append(field)
        elif " - Max Points" not in field and " - Lateness" not in field:
            attrs.append(field)

    (attrConfig, _) = guessAttrConfig(attrs, allAttrs)

    itemConfig = []
    for item in assignments:
        itemType = guessItemType(item)
        maxPoints = int(rows[0][item + " - Max Points"])
        name = forceUniqueName(item, allNames)
        itemConfig.append({"name": name, "scoreCol": item, "max_points": maxPoints, "type": itemType, "filters": ALL_DEFAULT_FILTERS}) #["NoneTo0"]})

    sourceConf.update({
        "attributes": attrConfig,
        ASSIGNMENTS_KEY: itemConfig,
    })

def updateConfig(globalConfigObj, sourceConf, rows, allNames):
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
            ASSIGNMENTS_KEY: []
        })
    elif fileType == FileType.GRADESCOPE:
        updateGradescopeConfig(globalConfigObj['studentAttributes'], sourceConf, rows, allNames)
    elif fileType in [FileType.SCORED_GOOGLE_FORM, FileType.UNSCORED_GOOGLE_FORM, FileType.CLICKERS, FileType.OTHER]:
        usable = updateOtherConfig(globalConfigObj['studentAttributes'], sourceConf, rows, fileType, allNames)
        if not usable:
            return
    else:
        raise Exception(f"unknown filetype {fileType.name}")

    globalConfigObj["sources"].append(sourceConf)


def main(sources, configInFilename, configOutFilename):
    if configInFilename:
        globalConfigObj = loadConfig(configInFilename)
    else:
        globalConfigObj = {}

    if "studentAttributes" not in globalConfigObj:
        globalConfigObj["studentAttributes"] = DEFAULT_ATTR_DICT
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
    allNames = set()
    for inFile in sources:
        inFilePath = Path(inFile)
        if inFilePath.is_dir():
            logger.debug(f"Recursively searching `{inFilePath}` for csv and xlsx files...")
            fileIter = glob.iglob(str(inFilePath/'**'), recursive=True)
        else:
            fileIter = [inFile]
        fileIter = [Path(filename) for filename in fileIter]
        for filePath in fileIter:
            if filePath.is_dir():
                continue
            # if filename in ignoredFiles:
            #     print("Skipping because of _autoconf_ignoredFiles")
            #     continue

            ext = filePath.suffix
            if ext == ".csv":
                sourceIter = [(filePath, None)]
            elif ext == ".xlsx":
                book = pe.get_book(file_name=str(filePath))
                sourceIter = [(filePath, name) for name in book.sheet_names()]
            else:
                logger.debug(f"Ignoring non-csv/xlsx file: `{filePath}`.")
                continue

            for (filePath, sheetName) in sourceIter:
                logger.debug(f"Handling source `{filePath}`{' (sheet '+sheetName+')' if sheetName else ''}")

                if (str(filePath), sheetName) in preconfiguredFiles:
                    logger.debug("Skipping because file is already configured")
                    continue
                rows = getRows(filePath, sheetName=sheetName)
                sourceConf = {"file": str(filePath), "sheetName": sheetName}
                updateConfig(globalConfigObj, sourceConf, rows, allNames)

    globalConfigObj["sources"].sort(key=mySort)

    categories = set()
    for sourceData in globalConfigObj['sources']:
        for item in sourceData[ASSIGNMENTS_KEY]:
            categories.add(item['type'])
    oldCategories = set(map(lambda z: z['from'], globalConfigObj['outputs']['content']))
    globalConfigObj['outputs']['content'] += [{ "title": f"[Rename me - display name of {c}]", "from": c} for c in categories.difference(oldCategories)]

    saveConfig(configOutFilename, globalConfigObj)
    logger.info(f"Wrote config file to `{configOutFilename}`")

def getSource(sourceObj):
    return (sourceObj["file"], sourceObj.get("sheetName", None))

def mySort(obj):
    return (obj["file"].lower(), obj["sheetName"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('sourcesDir', metavar='SOURCE', type=str, nargs='*',
        help='A csv or xlsx source (roster, gradesheet, etc) or a directory containing such sources')
    parser.add_argument('-i', metavar='CONFIG_FILE', type=str, help='An initial config file to add to')
    parser.add_argument('-o', metavar='OUTPUT_FILE', type=str, help='Output file (default: tempConfig.json)', default='tempConfig.json')
    args = parser.parse_args()
    main(args.sourcesDir, args.i, args.o)
