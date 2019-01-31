import sys, os, csv, json
import pdfkit
import argparse

DEFAULT_CONFIG_FILENAME = 'config.json'

GRADES_KEY = 'Grades'
INFO_KEY = 'Info'
ASSIGNMENT_NAME_KEY = 'name'

def checkAndClean(s, filters):
    for f in filters:
        s = filtersAndChecks[f](s)
    return s

class IncorrectLengthException(Exception):
    pass
def mkCheckNChar(n):
    def checkNChar(x):
        if len(x) != n:
            raise IncorrectLengthException()
        return x
    return checkNChar
filtersAndChecks = {
    'strip': lambda x: x.strip(),
    '8char': mkCheckNChar(8),
    '9char': mkCheckNChar(9),
    'remove#': lambda x: x[1:] if len(x) > 0 and x[0] == '#' else x,
    'toUpper': lambda x: x.upper(),
    'NVto0': lambda x: 0 if x == 'NV' else x,
    'BlankTo0': lambda x: 0 if x == '' else x,
    'stripDenominator': lambda x: x.split('/')[0].strip()
}

# https://stackoverflow.com/a/16840747/6036628
def peek_line(f):
    pos = f.tell()
    line = f.readline()
    f.seek(pos)
    return line

def getRows(sourceFileName, sourceType):
    with open(sourceFileName) as source:
        if sourceType == "UCSD Roster":
            while peek_line(source) != "Sec ID,PID,Student,Credits,College,Major,Level,Email\n":
                source.readline()
        rows = list(csv.DictReader(source))
        return rows

# returns [(Student, [Grade])]
def sourceToGrades(sourceFileName, assignmentConfigObj, studentAttrDict):
    rows = getRows(sourceFileName, assignmentConfigObj.get("type", None))
    identDict = assignmentConfigObj["attributes"]
    sourceConfigReader = assignmentConfigObj["items"]
    outputList = []
    for record in rows:
        try:
            studentInfo = {}
            for (identCol, internalName) in identDict.items():
                identVal = record[identCol]
                studentInfo[internalName] = checkAndClean(identVal, studentAttrDict[internalName]['filters'])
            grades = {}
            for assignment in sourceConfigReader:
                score = record[assignment['match']]
                grades[assignment[ASSIGNMENT_NAME_KEY]] = float(checkAndClean(score, assignment['filters']))
            outputList.append((studentInfo, grades))
        except IncorrectLengthException:
            print(f"WARNING: in file {sourceFileName}, invalid value for {internalName}: '{identVal}'")
    return outputList

def findPrimaryAttr(attrDict):
    for (attr, flags) in attrDict.items():
        if flags["identifiesStudent"] and flags["onePerStudent"]:
            return attr
    print("ERROR: no primary student identifier")

class UnidentifiableStudentException(Exception):
    pass
def getStudentID(studentAttrDict, primaryAttr, roster, studentInfo):
    if primaryAttr in studentInfo:
        return studentInfo[primaryAttr]
    for (key, val) in studentInfo.items():
        identifiesStudent = studentAttrDict[key]['identifiesStudent']
        if not identifiesStudent:
            continue
        if val in roster[key]:
            return roster[key][val]
    raise UnidentifiableStudentException()

def mergeIntoRoster(studentAttrDict, primaryAttr, roster, studentInfo, studentID):
    if studentID not in roster[primaryAttr]:
        roster[primaryAttr][studentID] = {INFO_KEY: {}, GRADES_KEY: {}}
    oldInfo = roster[primaryAttr][studentID][INFO_KEY]
    for (key, val) in studentInfo.items():
        if key == primaryAttr:
            continue
        onePerStudent = studentAttrDict[key]["onePerStudent"]
        if onePerStudent:
            if key not in oldInfo:
                oldInfo[key] = val
            else:
                if oldInfo[key] != val:
                    print("ERROR: overwriting singleton value")
        else:
            if key not in oldInfo:
                oldInfo[key] = set([val])
            else:
                oldInfo[key].add(val)
        identifiesStudent = studentAttrDict[key]['identifiesStudent']
        if identifiesStudent:
            if key not in roster:
                roster[key] = {}
            if val not in roster[key]:
                roster[key][val] = studentID
            elif roster[key][val] != studentID:
                print(key, val, roster[key][val])
                print("ERROR: reassigning identifer")
    return studentID

def printReport(studentIdentifier, studentData, allAssignments, outputConfigObj):
    studentInfo = studentData[INFO_KEY]
    if 'Roster Name' not in studentInfo:
        return

    # Print simple text report to stdout
    print('\n--------------------------')
    print(studentIdentifier)
    print(studentInfo)
    for obj in outputConfigObj["content"]:
        print(obj["title"])
        for (assignmentName, assignmentData) in allAssignments.items():
            if assignmentData['type'] == obj["from"]:
                score = studentData[GRADES_KEY].get(assignmentName, None)
                print(f"{assignmentName}\t{score}/{assignmentData['max_points']}")
    print('--------------------------\n')

    # Print html report to file
    clickerIDs = studentData[INFO_KEY].get('Clicker ID', set())
    if len(clickerIDs) == 0:
        clickerIDtext = "Clicker ID: unknown"
    elif len(clickerIDs) == 1:
        clickerIDtext = f"Clicker ID: {str(list(clickerIDs)[0])}"
    else:
        clickerIDtext = f"Clicker IDs: {str(clickerIDs)}"
    header_str = f"""
        <html>
        <h1>{outputConfigObj["report-name"]}</h1>
        <h2>Student Name: {studentInfo['Roster Name']} <br/>
        Student PID: {studentIdentifier} <br/>
        {clickerIDtext}</h2><body>"""
    disclaimer_str = f"<div>{outputConfigObj['disclaimer-text']}</div>"
    assignments_str = get_assignmenthtml(studentData, allAssignments, outputConfigObj)
    total_str = f'{header_str} {disclaimer_str} <table style="width:100%"><tr><td valign="top" width="33%"> {assignments_str} </td></tr></table></body></html>'
    f = open(f'./reports/{studentIdentifier}.html','w')
    f.write(total_str)
    f.close()

    # Convert html report to pdf report
    # pdfkit.from_file(f'./reports/{studentIdentifier}.html', f'./reports/{studentIdentifier}.pdf')

def get_assignmenthtml(studentData, allAssignments, outputConfigObj):
    html_str = ""
    for obj in outputConfigObj["content"]:
        html_str += f"<h2>{obj['title']}</h2>"
        index = 0
        for (assignmentName, assignmentData) in allAssignments.items():
            if assignmentData['type'] == obj["from"]:
                index += 1
                score = studentData[GRADES_KEY].get(assignmentName, None)
                ogscore = f"{score}/{assignmentData['max_points']}"
                prefix = f"<p><b>{index}. {assignmentName}:</b> "
                html_str += f"{prefix} {ogscore} </p>"
    return html_str

def main(configFilename):
    with open(args.filename) as configFile:
        globalConfigObj = json.load(configFile)

    studentAttrDict = globalConfigObj["studentAttributes"]
    # Canonicalize with defaults
    for (k,v) in studentAttrDict.items():
        if "identifiesStudent" not in v:
            v["identifiesStudent"] = False
        if "onePerStudent" not in v:
            v["onePerStudent"] = False
        if "filters" not in v:
            v["filters"] = []
    primaryAttr = findPrimaryAttr(studentAttrDict)
    roster = {k:{} for k in studentAttrDict}

    sourceConfigObj = globalConfigObj["sources"]
    allAssignments = {}
    for obj in sourceConfigObj.values():
        for assignmentData in obj["items"]:
            allAssignments[assignmentData["name"]] = assignmentData

    for sourceFilename in sourceConfigObj:
        data = sourceToGrades(sourceFilename, sourceConfigObj[sourceFilename], studentAttrDict)
        for (studentInfo, grades) in data:
            try:
                studentID = getStudentID(studentAttrDict, primaryAttr, roster, studentInfo)
                mergeIntoRoster(studentAttrDict, primaryAttr, roster, studentInfo, studentID)
                roster[primaryAttr][studentID][GRADES_KEY].update(grades)
            except UnidentifiableStudentException:
                print(f"WARNING: could not identify student ({studentInfo})")

    for (k,v) in roster[primaryAttr].items():
        printReport(k, v, allAssignments, globalConfigObj["outputs"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', metavar='CONFIG_FILE', type=str, nargs='?',
        help='The .json file describing your class. Default: `config.json`',
        default=DEFAULT_CONFIG_FILENAME)
    args = parser.parse_args()
    main(args.filename)
