import json, os, csv, re, argparse, glob, pathlib
from enum import Enum
import pyexcel as pe
# from xlsxReader import XLSXReader
from fileFormats import getRows
# from JSONprinter import NoIndentEncoder, NoIndent

FileType = Enum('FileType', 'ROSTER GRADESCOPE SCORED_GOOGLE_FORM UNSCORED_GOOGLE_FORM OTHER')

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

    # if fields[:4] == ['Last Name', 'First Name', 'Student ID', 'Remote ID'] and any([re.match(r'^Session \d+ Total', field) for field in fields]):
    #     return FileType.CLICKERS

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
    fields = rows[0].keys()
    if len(set(fields)) != len(fields):
        print(f"WARNING: duplicate column in {filename}")

    (attrConfig, ignoredCols) = guessAttrConfig(fields, allAttrs)
    itemConfig = []

    if fileType == FileType.OTHER:
        for item in fields:
            if item not in ignoredCols and item not in attrConfig.keys():
                itemType = guessItemType(item)
                itemConfig.append({"name": item, "scoreCol": item, "max_points": 1, "type": itemType, "filters": ["NoneTo0", "NVto0"]})

    if fileType == FileType.SCORED_GOOGLE_FORM:
        row = rows[0]
        score = row['Score']
        if '/' in score:
            maxPoints = int(score.split('/')[1].strip())
            filters = ["stripDenominator"]
        else:
            maxPoints = max([float(x['Score']) for x in rows])
            filters = []
        name = sourceConf.get("sheetName", os.path.basename(sourceConf['file']))
        itemConfig.append({"name": name, "scoreCol": "Score", "max_points": maxPoints, "type": fileType.name, "filters": ["stripDenominator"], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    if fileType == FileType.UNSCORED_GOOGLE_FORM:
        name = sourceConf.get("sheetName", os.path.basename(sourceConf['file']))
        itemConfig.append({"name": name, "scoreCol": False, "max_points": 1, "type": fileType.name, "filters": [], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    sourceConf.update({
        # "_autoconf_fileType": fileType.name,
        "attributes": attrConfig,
        "items": itemConfig, #[NoIndent(x) for x in itemConfig],
        # "_autoconf_ignoredCols": ignoredCols
    })

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
                print(f"WARNING: found two columns for attribute {identifiedAttr}")
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
    print("\tInferred type: %s" % fileType.name)
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
    elif fileType in [FileType.SCORED_GOOGLE_FORM, FileType.UNSCORED_GOOGLE_FORM, FileType.OTHER]:
        updateOtherConfig(globalConfigObj['studentAttributes'], sourceConf, rows, fileType)
    else:
        raise Exception(f"unknown filetype {fileType.name}")

    globalConfigObj["sources"].append(sourceConf)


def main(sources, partialConfig, outfilename):
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
    preconfiguredFiles = map(getSource, globalConfigObj["sources"])
    for source in sources:
        if os.path.isdir(source):
            print("Searching `%s` for csv and xlsx files..." % source)
            sourceIter = glob.iglob(os.path.join(source,'**'), recursive=True)
        else:
            sourceIter = [source]
        for filename in sourceIter:
            if os.path.isdir(filename):
                continue
            print("Handling file `%s`" % filename)
            # if filename in ignoredFiles:
            #     print("Skipping because of _autoconf_ignoredFiles")
            #     continue
            if filename in preconfiguredFiles:
                print("Skipping because file is already configured")
                continue
            ext = pathlib.Path(filename).suffix
            if ext == ".csv":
                rows = getRows(filename, False, None)
                sourceConf = {"file": filename}
                updateConfig(globalConfigObj, sourceConf, rows)
            elif ext == ".xlsx":
                book = pe.get_book(file_name=filename, auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)
                for name in book.sheet_names():
                    print("Found sheet `%s`" % name)
                    # if [filename, name] in ignoredFiles:
                    #     print("Skipping because of _autoconf_ignoredFiles")
                    #     continue
                    if [filename, name] in preconfiguredFiles:
                        print("Skipping because file is already configured")
                        continue
                    rows = getRows(filename, False, name)
                    sourceConf = {"file": filename, "sheetName": name}
                    updateConfig(globalConfigObj, sourceConf, rows)
            else:
                print("Ignoring.")
                continue
    globalConfigObj["sources"].sort(key=mySort, reverse=True)

    categories = set()
    for sourceData in globalConfigObj['sources']:
        for item in sourceData['items']:
            categories.add(item['type'])
    globalConfigObj['outputs']['content'] = [{ "title": f"<Rename me - display name of {c}>", "from": c} for c in categories]

    with open(outfilename, 'w') as outFile:
        s = json.dumps(globalConfigObj, indent=2, separators=(',', ': ')) # cls=NoIndentEncoder,
        outFile.write(s)
        # json.dump(globalConfigObj, outFile, cls=NoIndentEncoder, indent=2, separators=(',', ': '))
        print(f"Wrote config file to `{outfilename}`")

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
    main(args.sourcesDir, args.i, args.o)
