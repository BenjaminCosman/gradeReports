import json, os, csv, re, argparse
# from JSONprinter import NoIndentEncoder, NoIndent

# CONFIG_FILENAME = 'config.json'
DEFAULT_DATA_DIR = 'data'
OUTFILE = 'tempConfig.json'

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
        return "unknown"
    with open(fullname) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames

        if fields[:4] == ['Sect ID', 'Course', 'Title', 'SecCode']:
            return "roster"

        lastCol = ""
        for col in fields:
            if col == lastCol + " - Max Points":
                return "gradescope"
            lastCol = col

        if fields[0] == 'Timestamp':
            if 'Score' in fields:
                return "scoredGoogleForm"
            else:
                return "unscoredGoogleForm"

        return "other"

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
        if fileType == "roster":
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

        if fileType in ["other", "scoredGoogleForm", "unscoredGoogleForm"]:
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
                    if fileType == "other":
                        itemType = "unknown"
                        if "hw" in item or "assignment" in item or "homework" in item:
                            itemType = "homework"
                        itemConfig.append({"name": item, "scoreCol": item, "max_points": 1, "type": itemType})

        if fileType == "scoredGoogleForm":
            row = reader.__next__()
            score = row['Score']
            maxPoints = int(score.split('/')[1].strip())
            name = os.path.splitext(os.path.basename(filename))[0]
            itemConfig.append({"name": name, "scoreCol": "Score", "max_points": maxPoints, "type": fileType, "filters": ["stripDenominator"], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})

        if fileType == "unscoredGoogleForm":
            name = os.path.splitext(os.path.basename(filename))[0]
            itemConfig.append({"name": name, "scoreCol": False, "max_points": 1, "type": fileType, "filters": [], "due_date": "12/31/9999 23:59:59", "timestampCol": "Timestamp"})


    globalConfigObj["sources"][filename] = {
        "_autoconf_fileType": fileType,
        "attributes": attrConfig,
        "items": itemConfig, #[NoIndent(x) for x in itemConfig],
        "_autoconf_ignoredCols": ignoredCols
    }

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
        "sources": {},
        "outputs": {
            "report-name": "CSEnn Grade Report",
            "disclaimer-text": "These are all the scores recorded for you in this course. If there are any discrepancies between the scores you see here and your own records, email...",
            "content": []
        }
    }

    # newGlobalConfigObj = copy.deepcopy(globalConfigObj)

    print("Searching `%s` for csv files..." % dataDir)
    for filename in os.listdir(dataDir):
        fullname = os.path.join(dataDir, filename)
        # if fullname not in globalConfigObj["sources"]:
        print("Found file `%s`" % filename)
        fileType = inferType(fullname)
        print("Inferred file type: %s" % fileType)
        guessConfig(globalConfigObj, fullname, fileType)

    categories = []
    for (_, sourceData) in globalConfigObj['sources'].items():
        for item in sourceData['items']:
            categories.append(item['type'])
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
