import json, os, csv, re, argparse, glob
from enum import Enum
# from xlsxReader import XLSXReader
# import openpyxl
from fileFormats import getRows
# from JSONprinter import NoIndentEncoder, NoIndent

# CONFIG_FILENAME = 'config.json'
DEFAULT_DATA_DIR = 'data'
OUTFILE = 'tempConfig.json'

FileFormat = Enum('FileFormat', 'CSV_UCSD_ROSTER CSV_OTHER XLSX_ROSTER XLSX_OTHER, IGNORED')
FileType = Enum('FileType', 'ROSTER GRADESCOPE SCORED_GOOGLE_FORM UNSCORED_GOOGLE_FORM OTHER IGNORED')

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

def inferFormat(filename):
    (_, ext) = os.path.splitext(filename)
    if ext == ".csv":
        with open(filename) as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            if fields[:5] == ['Sect ID', 'Course', 'Title', 'SecCode', 'Instructor']:
                return FileFormat.CSV_UCSD_ROSTER
            else:
                return FileFormat.CSV_OTHER
    elif ext == ".xlsx":
        wb = openpyxl.load_workbook(filename=filename, read_only=True)
        ws = wb.active
        fields = ws.values.__next__()
        if fields == ('Sect ID', 'Course', 'Title', 'SecCode', 'Instructor'):
            return FileFormat.XLSX_ROSTER
        else:
            return FileFormat.XLSX_OTHER
    else:
        return FileFormat.IGNORED

def inferType(filename, fileFormat):
    if fileFormat == FileFormat.XLSX_OTHER:
        pass#TODO
    (_, ext) = os.path.splitext(filename)
    if ext in [".csv", ".xlsx"]:
        fields = getFields(filename)
        return inferTypeFromFields(fields)
    else:
        return FileType.IGNORED

def getFields(filename):
    (_, ext) = os.path.splitext(filename)
    if ext == ".csv":
        with open(filename) as f:
            reader = csv.DictReader(f)
            return reader.fieldnames
    elif ext == ".xlsx":
        wb = openpyxl.load_workbook(filename=filename, read_only=True)
        ws = wb.active
        it = ws.values
        return it.__next__()
    else:
        raise Exception("bad file type")

def inferTypeFromFields(fields):
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

def guessConfig(globalConfigObj, filename, fileType):
    attrConfig = {}
    itemConfig = []
    ignoredCols = []
    allAttrs = globalConfigObj['studentAttributes']
    keywordLookup = {}
    for attr in allAttrs:
        if attr in keywords:
            keywordLookup.update({keyword:attr for keyword in keywords[attr]})

    fields = getFields(filename)

    if len(set(fields)) != len(fields):
        print(f"WARNING: duplicate column in {filename}")

    if fileType in [FileType.OTHER, FileType.SCORED_GOOGLE_FORM, FileType.UNSCORED_GOOGLE_FORM]:
        for item in fields:
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
            # Otherwise, assume it's an assignment grade (for 'other' filetypes only)
            else:
                if fileType == FileType.OTHER:
                    itemType = guessItemType(item)
                    itemConfig.append({"name": item, "scoreCol": item, "max_points": 1, "type": itemType, "filters": ["NoneTo0", "NVto0"]})

    if fileType == FileType.SCORED_GOOGLE_FORM:
        rows = getRows(filename, False, None)
        row = rows[0]
        score = row['Score']
        print(row)
        maxPoints = int(score.split('/')[1].strip())
        name = os.path.splitext(os.path.basename(filename))[0]
        itemConfig.append({"name": name, "scoreCol": "Score", "max_points": maxPoints, "type": fileType.name, "filters": ["stripDenominator"], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    if fileType == FileType.UNSCORED_GOOGLE_FORM:
        name = os.path.splitext(os.path.basename(filename))[0]
        itemConfig.append({"name": name, "scoreCol": False, "max_points": 1, "type": fileType.name, "filters": [], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

    globalConfigObj["sources"].append({
        "file": filename,
        # "_autoconf_fileType": fileType.name,
        "attributes": attrConfig,
        "items": itemConfig, #[NoIndent(x) for x in itemConfig],
        # "_autoconf_ignoredCols": ignoredCols
    })

def guessItemType(item):
    item = item.lower()
    if "hw" in item or "assignment" in item or "homework" in item:
        return "homework"
    return "unknown"

def guessGradescopeConfig(globalConfigObj, filename):
    row = getRows(filename, False, None)[0]
    fields = row.keys()
    assignments = []
    attrs = []
    for field in fields:
        if field + " - Max Points" in fields:
            assignments.append(field)
        elif " - Max Points" not in field and " - Lateness" not in field:
            attrs.append(field)

    attrConfig = {}
    itemConfig = []
    ignoredCols = []
    allAttrs = globalConfigObj['studentAttributes']
    keywordLookup = {}
    for attr in allAttrs:
        if attr in keywords:
            keywordLookup.update({keyword:attr for keyword in keywords[attr]})

    for item in attrs:
        itemLowered = item.lower()
        # First, check if the column name is referring to a student attribute
        identifiedAttr = None
        if itemLowered in [attr.lower() for attr in allAttrs]:
            identifiedAttr = item
        else:
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

    for item in assignments:
        itemType = guessItemType(item)
        maxPoints = int(row[item + " - Max Points"])
        itemConfig.append({"name": item, "scoreCol": item, "max_points": maxPoints, "type": itemType, "filters": ["NoneTo0"]})

    globalConfigObj["sources"].append({
        "file": filename,
        # "_autoconf_fileType": FileType.GRADESCOPE.name,
        "attributes": attrConfig,
        "items": itemConfig,
        # "_autoconf_ignoredCols": ignoredCols
    })




def main(dataDir):
    # if os.path.exists(CONFIG_FILENAME):
    #     with open(CONFIG_FILENAME) as configFile:
    #         globalConfigObj = json.load(configFile)
    # else:
    globalConfigObj = {
        "studentAttributes": {
            "Roster Name": {"onePerStudent": True},
            "Section": {"onePerStudent": True},
            "Email": {},
            "Student ID": {"identifiesStudent": True, "onePerStudent": True, "filters": ["strip", "toUpper", "ucsdIDCheck"]},
            "Clicker ID": {"identifiesStudent": True, "filters": ["strip", "remove#", "8char", "toUpper"]}
        },
        "sources": [],
        "outputs": {
            "report-name": "CSEnn Grade Report",
            "disclaimer-text": "These are all the scores recorded for you in this course. If there are any discrepancies between the scores you see here and your own records, email...",
            "content": []
        }
    }

    # newGlobalConfigObj = copy.deepcopy(globalConfigObj)

    print("Searching `%s` for csv files..." % dataDir)
    for filename in glob.iglob(os.path.join(dataDir,'**'), recursive=True):
        print("Found file `%s`" % filename)
        fileFormat = inferFormat(filename)
        if fileFormat == FileFormat.IGNORED:
            print("Ignoring.")
            continue
        if fileFormat in [FileFormat.CSV_UCSD_ROSTER, FileFormat.XLSX_ROSTER]:
            print("Using default ROSTER config")
            # The UCSD roster is not a proper csv (more like 2 on top of each other)
            obj = {
                "file": filename,
                "isRoster": True,
                "attributes": {
                    "Email": "Email",
                    "PID": "Student ID",
                    "Student": "Roster Name"
                },
                "items": []
            }
            globalConfigObj["sources"].append(obj)
            continue
        fileType = inferType(filename, fileFormat)
        print("Inferred file type: %s" % fileType.name)
        if fileType == FileType.IGNORED:
            print("Ignoring.")
        elif fileType == FileType.GRADESCOPE:
            guessGradescopeConfig(globalConfigObj, filename)
        else:
            guessConfig(globalConfigObj, filename, fileType)
    globalConfigObj["sources"].sort(key=mySort, reverse=True)

    categories = set()
    for sourceData in globalConfigObj['sources']:
        for item in sourceData['items']:
            categories.add(item['type'])
    globalConfigObj['outputs']['content'] = [{ "title": c, "from": c} for c in categories]

    with open(OUTFILE, 'w') as outFile:
        s = json.dumps(globalConfigObj, indent=2, separators=(',', ': ')) # cls=NoIndentEncoder,
        # print(s)
        outFile.write(s)
        # json.dump(globalConfigObj, outFile, cls=NoIndentEncoder, indent=2, separators=(',', ': '))
        print(f"Wrote config file to `{OUTFILE}`")

# TODO: remove dependency on order of sources - right now sources that define and
# connect student attributes should come first (e.g. roster, then clicker registrations)
def mySort(obj):
    return (
        "isRoster" in obj,
        len(obj["attributes"])
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('sourcesDir', metavar='SOURCES_DIR', type=str, #nargs='?',
        help='The folder containing your roster, grades, etc.',# Default: `data`',
        default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    main(args.sourcesDir)
