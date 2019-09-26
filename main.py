import datetime, argparse
import dateutil.parser
from pathlib import Path
import tqdm

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)
logging.addLevelName(logging.WARNING, "\033[33m%s\033[0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[31m%s\033[0m" % logging.getLevelName(logging.ERROR))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DuplicateFilter(logging.Filter):
    msgs = set()
    def filter(self, record):
        retVal = record.msg not in self.msgs
        self.msgs.add(record.msg)
        return retVal
logger.addFilter(DuplicateFilter())

from lib.spreadsheetReader import getRows
from lib.printing import printReport, makeCsvSummary
from lib.constants import INFO_KEY, GRADES_KEY, ASSIGNMENTS_KEY, ALL_DEFAULT_FILTERS
from lib.mung import IncorrectFormatException, checkAndClean
from lib.config import loadConfig

def sourceToGrades(sourceConfigObj, studentAttrDict):
    '''returns [(Student, [Grade])]'''
    sourcePath = Path(sourceConfigObj['file'])
    rows = getRows(sourcePath, isRoster=sourceConfigObj.get("isRoster", False), sheetName=sourceConfigObj["sheetName"])
    identDict = sourceConfigObj["attributes"]
    sourceConfigReader = sourceConfigObj[ASSIGNMENTS_KEY]
    outputList = []
    for record in rows:
        studentInfo = {}
        for (identCol, internalName) in identDict.items():
            identVal = record[identCol]
            try:
                studentInfo[internalName] = checkAndClean(identVal, studentAttrDict[internalName]['filters'])
            except IncorrectFormatException:
                logger.info(f"in file {sourcePath}, invalid value for {internalName}: '{identVal}'")
                logger.info(f"skipping this field; may result in an UnidentifiableStudentException later")
        grades = {}
        for assignment in sourceConfigReader:
            scoreCol = assignment.get('scoreCol', None)
            if scoreCol == None:
                # Full credit for completion (i.e. being in the spreadsheet at all)
                score = assignment['max_points']
            else:
                try:
                    score = record[scoreCol]
                except:
                    logger.error(f"In file '{str(sourcePath)}', expected score column '{scoreCol}' for assignment '{assignment['name']}' not in record '{record}'")
                try:
                    score = checkAndClean(score, assignment.get('filters', ALL_DEFAULT_FILTERS))
                except IncorrectFormatException:
                    logger.error(f"in file {sourcePath}, unreadable score for score column {scoreCol}: '{score}'")
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
    try:
        checkMerge(studentAttrDict, primaryAttr, roster, studentInfo, studentID)
    except Exception as e:
        logger.warning(e)
        return
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
                    raise Exception("This state should be unreachable (see checkMerge)")
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
                raise Exception("This state should be unreachable (see checkMerge)")

def checkMerge(studentAttrDict, primaryAttr, roster, studentInfo, studentID):
    if studentID not in roster[primaryAttr]:
        oldInfo = {}
    else:
        oldInfo = roster[primaryAttr][studentID][INFO_KEY]
    for (key, val) in studentInfo.items():
        if key == primaryAttr:
            continue
        onePerStudent = studentAttrDict[key]["onePerStudent"]
        if onePerStudent:
            if key not in oldInfo:
                pass
            else:
                if oldInfo[key] != val:
                    raise Exception(f"refusing to overwrite singleton value for {key} from {oldInfo[key]} to {val}")
        identifiesStudent = studentAttrDict[key]['identifiesStudent']
        if identifiesStudent:
            if key not in roster:
                pass
            elif val not in roster[key]:
                pass
            elif roster[key][val] != studentID:
                raise Exception(f"refusing to reassign ({key}: {val}) from {roster[key][val]} to {studentID}")

def gatherData(globalConfigObj):
    studentAttrDict = globalConfigObj["studentAttributes"]
    primaryAttr = findPrimaryAttr(studentAttrDict)
    roster = {k:{} for k in studentAttrDict}

    sourceConfigList = globalConfigObj["sources"]
    allAssignments = {}
    for obj in sourceConfigList:
        for assignmentData in obj[ASSIGNMENTS_KEY]:
            allAssignments[assignmentData["name"]] = assignmentData

    data = []
    for obj in sourceConfigList:
        data += sourceToGrades(obj, studentAttrDict)

    while True:
        newDataMerged = False
        failedToMerge = []
        for (studentInfo, grades) in data:
            try:
                studentID = getStudentID(studentAttrDict, primaryAttr, roster, studentInfo)
            except UnidentifiableStudentException:
                failedToMerge.append((studentInfo, grades))
                continue
            newDataMerged = True
            mergeIntoRoster(studentAttrDict, primaryAttr, roster, studentInfo, studentID)
            for (k,v) in grades.items():
                oldGrade = roster[primaryAttr][studentID][GRADES_KEY].get(k,(-float('inf'), None))
                if oldGrade != (-float('inf'), None):
                    logger.warning(f'Duplicate grade: {(oldGrade, studentInfo, grades)}')
                # Always keep the highest grade for each assignment (TODO: replace with more flexible policy?)
                if type(v[0]) != str:
                    roster[primaryAttr][studentID][GRADES_KEY][k] = max(oldGrade, v)
                else:
                    roster[primaryAttr][studentID][GRADES_KEY][k] = v
        if newDataMerged == False or len(failedToMerge) == 0:
            break
        data = failedToMerge[:]

    for (studentInfo, _) in failedToMerge:
        logger.warning(f"could not identify student ({studentInfo})")

    return (roster[primaryAttr], allAssignments)

def shouldPrint(printFilters, studentInfo):
    for attr in printFilters:
        if attr not in studentInfo:
            return False
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', metavar='CONFIG_FILE', type=str,
        help='The .json file describing your class.')
    parser.add_argument('-p', '--pdf', action='store_true', help='Generate pdf reports')
    args = parser.parse_args()
    globalConfigObj = loadConfig(args.filename)
    (gradebook, allAssignments) = gatherData(globalConfigObj)
    students = gradebook.items()
    if args.pdf:
        # Attach progress bar only if generating pdfs (which is slow). Non-pdf
        # version is fast enough that progress bar is just unnecessary clutter
        students = tqdm.tqdm(students)
    printFilters = []
    for (k,v) in globalConfigObj["studentAttributes"].items():
        if v.get("onlyPrintIfPresent", False):
            printFilters.append(k)
    makeCsvSummary(list(globalConfigObj["studentAttributes"].keys()), students, allAssignments, globalConfigObj["outputs"])
    for (studentIdentifier, studentData) in students:
        if shouldPrint(printFilters, studentData[INFO_KEY]):
            printReport(studentIdentifier, studentData, allAssignments, globalConfigObj["outputs"], args.pdf)
    # logger.info("reports generated in folder 'reports/'")
