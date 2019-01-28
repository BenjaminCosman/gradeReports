import json, os, csv, re
from JSONprinter import NoIndentEncoder, NoIndent

CONFIG_FILENAME = 'config.json'
DATA_DIR = 'data'
OUTFILE = 'tempConfig.json'

keywords = {
    "Roster Name": [r'name\b'],
    "Email": [r'\bemail\b'],
    "Student ID": [r'\bpid\b', r'\bsid\b'],
    "Clicker ID": [r'\bclicker\b', r'\biclicker\b', r'\bremote\b']
}

def inferType(fullname):
    (_, ext) = os.path.splitext(fullname)
    if ext != ".csv":
        return "unknown"
    with open(fullname) as f:
        reader = csv.DictReader(f)
        lastCol = ""
        for col in reader.fieldnames:
            if col == lastCol + " - Max Points":
                return "gradescope"
            lastCol = col
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
        if fileType == "other":
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                print(f"WARNING: duplicate column in {filename}")
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
                    continue

                # Otherwise, assume it's an assignment grade
                itemType = "unknown"
                if "hw" in item or "assignment" in item or "homework" in item:
                    itemType = "homework"
                itemConfig.append({"name": item, "match": item, "max_points": 1, "type": itemType})

    globalConfigObj["sources"][filename] = {
        "_fileType": fileType,
        "attributes": attrConfig,
        "items": [NoIndent(x) for x in itemConfig],
        "_ignoredCols": ignoredCols
    }

def main():
    if os.path.exists(CONFIG_FILENAME):
        with open(CONFIG_FILENAME) as configFile:
            globalConfigObj = json.load(configFile)
    else:
        globalConfigObj = {
            "studentAttributes": {
                "Roster Name": {"onePerStudent": True},
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

    print("Searching `%s` for new files..." % DATA_DIR)
    for filename in os.listdir(DATA_DIR):
        fullname = os.path.join(DATA_DIR, filename)
        if fullname not in globalConfigObj["sources"]:
            print("Found new file `%s`" % filename)
            fileType = inferType(fullname)
            print("Inferred file type: %s" % fileType)
            guessConfig(globalConfigObj, fullname, fileType)

    with open(OUTFILE, 'w') as outFile:
        s = json.dumps(globalConfigObj, cls=NoIndentEncoder, indent=2, separators=(',', ': '))
        print(s)
        outFile.write(s)
        # json.dump(globalConfigObj, outFile, cls=NoIndentEncoder, indent=2, separators=(',', ': '))

if __name__ == "__main__":
    main()
