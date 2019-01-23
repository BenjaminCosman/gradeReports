import json, os, csv

CONFIG_FILENAME = 'config.json'
DATA_DIR = 'data'
OUTFILE = 'tempConfig.json'

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
    with open(filename) as f:
        reader = csv.DictReader(f)
        if fileType == "other":
            for item in reader.fieldnames:
                item = item.lower()
                if "name" in item or "email" in item:
                    continue
                itemType = "unknown"
                if "hw" in item or "assignment" in item or "homework" in item:
                    itemType = "homework"
                itemConfig.append({"name": item, "match": item, "max_points": 1, "type": itemType})
    globalConfigObj["sources"][filename] = {
        "attributes": attrConfig,
        "items": itemConfig
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
        json.dump(globalConfigObj, outFile, indent=4, separators=(',', ': '))

if __name__ == "__main__":
    main()
