import pdfkit
from pathlib import Path
import csv

from lib.constants import INFO_KEY, GRADES_KEY

__all__ = ['printReport', 'makeCsvSummary']

def makeCsvSummary(attrs, students, allAssignments, outputConfigObj):
    fields = attrs + list(allAssignments.keys())
    reportsDir = Path('reports')
    reportsDir.mkdir(exist_ok=True)
    with open(reportsDir / "summary.csv", 'w') as csvFile:
        csvWriter = csv.DictWriter(csvFile, fields)
        csvWriter.writeheader()
        for (studentIdentifier, studentData) in students:
            newRow = {}
            for attr in attrs:
                if attr != "Student ID": #TODO fix this hack
                    newRow[attr] = studentData[INFO_KEY].get(attr, '')
                else:
                    newRow[attr] = studentIdentifier
            for (assignmentName, assignmentData) in allAssignments.items():
                (score, annot) = studentData[GRADES_KEY].get(assignmentName, (0, None))
                newRow[assignmentName] = formatScore(score)
            csvWriter.writerow(newRow)

def printReport(studentIdentifier, studentData, allAssignments, outputConfigObj, makePdf, wkhtmltopdfPath):
    '''This function is the main 'export' from this module.
    Given all relevant data about one student, it prints a text report
    to stdout and also dumps a html or pdf report to ./reports'''
    studentInfo = studentData[INFO_KEY]
    # turns all sets into sorted lists so it has a deterministic output that
    # we can check in the tests
    for (k,v) in studentInfo.items():
        if type(v) == set:
            studentInfo[k] = sorted(list(v))

    printTextReport(studentIdentifier, studentData, allAssignments, outputConfigObj["content"])
    writeHtmlReport(studentIdentifier, studentData, allAssignments, outputConfigObj, makePdf)

    # Convert html report to pdf report
    if makePdf:
        try:
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdfPath)
            pdfkit.from_file(f'./reports/{studentIdentifier}.html', f'./reports/{studentIdentifier}.pdf', configuration=config)
        except OSError as e:
            msg = str(e)
            if "No wkhtmltopdf executable found" not in msg:
                raise e
            print("Fatal error while generating pdf:")
            print(f'\n<\n{msg}\n>\n')
            print("If wkhtmltopdf is already installed and adding it to your path does not resolve this error,")
            print("you can specify its path for this program using the -w option")
            exit(1)

def printTextReport(studentIdentifier, studentData, allAssignments, reportConfig):
    '''Print simple text report to stdout'''
    print('\n--------------------------')
    print(studentIdentifier)
    for item in sorted(studentData[INFO_KEY].items()):
        print(item)
    for obj in reportConfig:
        print(obj["title"])
        for (assignmentName, assignmentData) in allAssignments.items():
            if assignmentData['type'] == obj["from"]:
                (score, annot) = studentData[GRADES_KEY].get(assignmentName, (0, None))
                print(f"\t{assignmentName}\t{formatScore(score)}{getMaxPointsStr(assignmentData)}{formatAnnot(annot)}")
    print('--------------------------\n')

def writeHtmlReport(studentIdentifier, studentData, allAssignments, outputConfigObj, makePdf):
    # Print html report to file
    studentInfo = studentData[INFO_KEY]
    header_str = f"""
        <html>
        <h1>{outputConfigObj["report-name"]}</h1>
        <h2>PID: {studentIdentifier}</h2>
        """
    h2Str = mkInfoStr(studentInfo)
    disclaimer_str = f"<div>{outputConfigObj['disclaimer-text']}</div>"
    assignments_str = get_assignmenthtml(studentData, allAssignments, outputConfigObj)
    total_str = f'{header_str} {h2Str} {disclaimer_str}\n{assignments_str}</body></html>'
    reportsDir = Path('reports')
    reportsDir.mkdir(exist_ok=True)
    reportPath = reportsDir / f'{studentIdentifier}.html'
    reportPath.write_text(total_str)

def mkInfoStr(studentInfo):
    res = "<h2>"
    for (k,v) in studentInfo.items():
        if type(v) == list:
            if len(v) == 0:
                v = "unknown"
            elif len(v) == 1:
                v = v[0]
            else:
                k = k + "s"
        res += f"{k}: {v}<br/>\n"
    res += "</h2><body>"
    return res

def get_assignmenthtml(studentData, allAssignments, outputConfigObj):
    html_str = ""
    for obj in outputConfigObj["content"]:
        html_str += f"<h2>{obj['title']}</h2>\n"
        if 'table' not in obj:
            for (assignmentName, assignmentData) in allAssignments.items():
                if assignmentData['type'] == obj["from"]:
                    (score, annot) = studentData[GRADES_KEY].get(assignmentName, (0, None))
                    ogscore = f"{formatScore(score)}{getMaxPointsStr(assignmentData)}"
                    prefix = f"<b>{assignmentName}:</b> "
                    html_str += f"{prefix} {ogscore}{formatAnnot(annot)} <br/>\n"
        else:
            html_str += "<table border=1>\n"
            for row in obj['table']:
                html_str += "<tr>\n"
                for assignmentName in row:
                    html_str += "<td>"
                    assignmentData = allAssignments[assignmentName]
                    (score, annot) = studentData[GRADES_KEY].get(assignmentName, (0, None))
                    ogscore = f"{formatScore(score)}{getMaxPointsStr(assignmentData)}"
                    prefix = f"<b>{assignmentName}:</b> "
                    html_str += f"{prefix} {ogscore}{formatAnnot(annot)} <br/>"
                    html_str += "</td>\n"
                html_str += "</tr>\n"
            html_str += "</table>\n"
    return html_str

def formatAnnot(annot):
    if annot == None:
        return ''
    else:
        return f' ({annot})'

def formatScore(score):
    '''Returns simplest fixed-point formatting, e.g. 3.10 -> 3.1, 3.00 -> 3'''
    if type(score) == str:
        return score
    return ('%f' % score).rstrip('0').rstrip('.')

def getMaxPointsStr(data):
    if 'max_points' in data:
        return '/'+str(data['max_points'])
    else:
        return ''