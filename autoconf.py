import json, os, csv, re, argparse, glob
from enum import Enum
# import openpyxl
# from JSONprinter import NoIndentEncoder, NoIndent

# CONFIG_FILENAME = 'config.json'
DEFAULT_DATA_DIR = 'data'
OUTFILE = 'tempConfig.json'

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

def inferType(fullname):
    (_, ext) = os.path.splitext(fullname)
    if ext != ".csv":
        return FileType.IGNORED
    with open(fullname) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames

        if fields[:5] == ['Sect ID', 'Course', 'Title', 'SecCode', 'Instructor']:
            return FileType.ROSTER

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

    with open(filename) as f:
        reader = csv.DictReader(f)

        # The UCSD roster is not a proper csv (more like 2 on top of each other)
        # it gets special treatment here
        if fileType == FileType.ROSTER:
            globalConfigObj["sources"][filename] = {
                "type": "UCSD Roster",
                "attributes": {
                    "Email": "Email",
                    "PID": "Student ID",
                    "Student": "Roster Name"
                },
                "items": []
            }
            return

        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            print(f"WARNING: duplicate column in {filename}")

        if fileType in [FileType.OTHER, FileType.SCORED_GOOGLE_FORM, FileType.UNSCORED_GOOGLE_FORM]:
            for item in reader.fieldnames:
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
                        itemType = "unknown"
                        if "hw" in item or "assignment" in item or "homework" in item:
                            itemType = "homework"
                        itemConfig.append({"name": item, "scoreCol": item, "max_points": 1, "type": itemType})

        if fileType == FileType.SCORED_GOOGLE_FORM:
            row = reader.__next__()
            score = row['Score']
            maxPoints = int(score.split('/')[1].strip())
            name = os.path.splitext(os.path.basename(filename))[0]
            itemConfig.append({"name": name, "scoreCol": "Score", "max_points": maxPoints, "type": fileType.name, "filters": ["stripDenominator"], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

        if fileType == FileType.UNSCORED_GOOGLE_FORM:
            name = os.path.splitext(os.path.basename(filename))[0]
            itemConfig.append({"name": name, "scoreCol": False, "max_points": 1, "type": fileType.name, "filters": [], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})


    globalConfigObj["sources"].append({
        "file": filename,
        "_autoconf_fileType": fileType.name,
        "attributes": attrConfig,
        "items": itemConfig, #[NoIndent(x) for x in itemConfig],
        "_autoconf_ignoredCols": ignoredCols
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
            "Student ID": {"identifiesStudent": True, "onePerStudent": True, "filters": ["strip", "9char", "toUpper"]},
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
        fileType = inferType(filename)
        print("Inferred file type: %s" % fileType.name)
        if fileType != FileType.IGNORED:
            guessConfig(globalConfigObj, filename, fileType)

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
        print(f"Wrote config file to `{OUTFILE}``")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('sourcesDir', metavar='SOURCES_DIR', type=str, #nargs='?',
        help='The folder containing your roster, grades, etc.',# Default: `data`',
        default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    main(args.sourcesDir)
