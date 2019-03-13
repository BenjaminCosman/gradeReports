import json, re, datetime
import argparse
import dateutil.parser
from pathlib import Path

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)
logging.addLevelName(logging.WARNING, "\033[33m%s\033[0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[31m%s\033[0m" % logging.getLevelName(logging.ERROR))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from lib.fileFormats import getRows
from lib.printing import printReport
from lib.constants import INFO_KEY, GRADES_KEY, ALL_DEFAULT_FILTERS
from lib.mung import IncorrectFormatException, checkAndClean

def sourceToGrades(sourceConfigObj, studentAttrDict):
    '''returns [(Student, [Grade])]'''
    sourcePath = Path(sourceConfigObj['file'])
    rows = getRows(sourcePath, isRoster=sourceConfigObj.get("isRoster", False), sheetName=sourceConfigObj.get("sheetName", None))
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
                        logger.error(f"In file '{str(sourcePath)}', expected score column '{scoreCol}' for assignment '{assignment['name']}' not in record '{record}'")
                    score = float(checkAndClean(score, assignment.get('filters', ALL_DEFAULT_FILTERS)))
                annotation = None
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
                        score = 0
                        annotation = f'late - received {turninDatetime.strftime("%b %d, %T")}'
                grades[assignment['name']] = (score, annotation)
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

def gatherData(globalConfigObj):
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
                    oldGrade = roster[primaryAttr][studentID][GRADES_KEY].get(k,(-float('inf'), None))
                    # Always keep the highest grade for each assignment (TODO: replace with more flexible policy?)
                    roster[primaryAttr][studentID][GRADES_KEY][k] = max(oldGrade, v)
            except UnidentifiableStudentException:
                logger.warning(f"could not identify student ({studentInfo})")

    return (roster[primaryAttr], allAssignments)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', metavar='CONFIG_FILE', type=str,
        help='The .json file describing your class.')
    parser.add_argument('-p', '--pdf', action='store_true', help='Generate pdf reports')
    args = parser.parse_args()
    globalConfigObj = json.loads(Path(args.filename).read_text())
    (gradebook, allAssignments) = gatherData(globalConfigObj)
    for (studentIdentifier, studentData) in gradebook.items():
        printReport(studentIdentifier, studentData, allAssignments, globalConfigObj["outputs"], args.pdf)
    # logger.info("reports generated in folder 'reports/'")

