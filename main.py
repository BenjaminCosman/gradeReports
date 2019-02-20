import json, re, datetime
import pdfkit
import argparse
import dateutil.parser
from pathlib import Path

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)
logging.addLevelName(logging.WARNING, "\033[33m%s\033[0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[31m%s\033[0m" % logging.getLevelName(logging.ERROR))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from fileFormats import getRows

GRADES_KEY = 'Grades'
INFO_KEY = 'Info'

def checkAndClean(s, filters):
    for f in filters:
        s = filtersAndChecks[f](s)
    return s

class IncorrectFormatException(Exception):
    pass
def ucsdStudentIDCheck(x):
    if not re.fullmatch(r'^[AU]\d{8}$', x):
        raise IncorrectFormatException()
    return x
def checkNChar(x, n):
    if len(x) != n:
        raise IncorrectFormatException()
    return x
filtersAndChecks = {
    'strip': lambda x: x.strip(),
    'ucsdIDCheck': ucsdStudentIDCheck,
    '8char': lambda x: checkNChar(x, 8),
    'remove#': lambda x: x[1:] if len(x) > 0 and x[0] == '#' else x,
    'toUpper': lambda x: x.upper(),
    'NVto0': lambda x: 0 if x == 'NV' else x,
    'NoneTo0': lambda x: 0 if x == '' or x == 'None' else x,
    'stripDenominator': lambda x: x.split('/')[0].strip()
}

# returns [(Student, [Grade])]
def sourceToGrades(sourceConfigObj, studentAttrDict):
    sourcePath = Path(sourceConfigObj['file'])
    rows = getRows(sourcePath, sourceConfigObj.get("isRoster", False), sourceConfigObj.get("sheetName", None))
    identDict = sourceConfigObj["attributes"]
    sourceConfigReader = sourceConfigObj["items"]
    outputList = []
    for record in rows:
        try:
            studentInfo = {}
            for (identCol, internalName) in identDict.items():
                identVal = record[identCol]
                studentInfo[internalName] = checkAndClean(identVal, studentAttrDict[internalName]['filters'])
            grades = {}
            for assignment in sourceConfigReader:
                sheetName = assignment.get('sheetName', None)
                if (sheetName != None) and (record['_sheetName'] != sheetName):
                    continue

                scoreCol = assignment.get('scoreCol', None)
                if scoreCol == None:
                    # Full credit for completion (i.e. being in the spreadsheet at all)
                    score = assignment['max_points']
                else:
                    try:
                        score = record[scoreCol]
                    except:
                        logger.error(f"Score column not in record {(assignment, str(sourcePath), sheetName, record)}")
                    score = float(checkAndClean(score, assignment['filters']))
                if "due_date" in assignment:
                    dueDatetime = dateutil.parser.parse(assignment['due_date'])
                    turnedInStr = record[assignment['timestampCol']]
                    try:
                        turninDatetime = dateutil.parser.parse(turnedInStr)
                    except ValueError:
                        # Try reading as an xlsx timestamp instead
                        # https://gist.github.com/erikvullings/825283249a5b4617d0f36bcba4fa8be8
                        utcTime = (float(turnedInStr) - 25569) * 86400
                        turninDatetime = datetime.datetime.utcfromtimestamp(utcTime)
                    if turninDatetime > dueDatetime:
                        continue
                grades[assignment['name']] = score
            outputList.append((studentInfo, grades))
        except IncorrectFormatException:
            logger.info(f"in file {sourcePath}, invalid value for {internalName}: '{identVal}'")
            # logger.warning(f"    (therefore, skipping row {','.join(record.values())}")
    return outputList

def findPrimaryAttr(attrDict):
    for (attr, flags) in attrDict.items():
        if flags["identifiesStudent"] and flags["onePerStudent"]:
            return attr
    logger.error("no primary student identifier")

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
                    logger.error("overwriting singleton value")
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
                logger.error(f"reassigning identifer {(key, val, roster[key][val], studentID)}")
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
                print(f"\t{assignmentName}\t{score}/{assignmentData['max_points']}")
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
    total_str = f'{header_str} {disclaimer_str} {assignments_str}</body></html>'
    reportsDir = Path('reports')
    reportsDir.mkdir(exist_ok=True)
    reportPath = reportsDir / f'{studentIdentifier}.html'
    reportPath.write_text(total_str)

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
                prefix = f"<p><b>{assignmentName}:</b> "
                html_str += f"{prefix} {ogscore} </p>"
    return html_str

def main(globalConfigObj):
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

    sourceConfigList = globalConfigObj["sources"]
    allAssignments = {}
    for obj in sourceConfigList:
        for assignmentData in obj["items"]:
            allAssignments[assignmentData["name"]] = assignmentData

    for obj in sourceConfigList:
        data = sourceToGrades(obj, studentAttrDict)
        for (studentInfo, grades) in data:
            try:
                studentID = getStudentID(studentAttrDict, primaryAttr, roster, studentInfo)
                mergeIntoRoster(studentAttrDict, primaryAttr, roster, studentInfo, studentID)
                for (k,v) in grades.items():
                    oldGrade = roster[primaryAttr][studentID][GRADES_KEY].get(k,0)
                    # Always keep the highest grade for each assignment (TODO: replace with more flexible policy?)
                    roster[primaryAttr][studentID][GRADES_KEY][k] = max(oldGrade, v)
            except UnidentifiableStudentException:
                logger.warning(f"could not identify student ({studentInfo})")

    for (studentIdentifier, studentData) in roster[primaryAttr].items():
        printReport(studentIdentifier, studentData, allAssignments, globalConfigObj["outputs"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', metavar='CONFIG_FILE', type=str,
        help='The .json file describing your class.')
    args = parser.parse_args()
    configPath = Path(args.filename)
    main(json.loads(configPath.read_text()))
