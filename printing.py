import pdfkit
from pathlib import Path

from constants import INFO_KEY, GRADES_KEY

__all__ = ['printReport']

def printReport(studentIdentifier, studentData, allAssignments, outputConfigObj, makePdf):
    '''This function is the only 'export' from this module.
    Given all relevant data about one student, it prints a text report
    to stdout and also dumps a html or pdf report to ./reports'''
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
                (score, annot) = studentData[GRADES_KEY].get(assignmentName, (0, None))
                print(f"\t{assignmentName}\t{formatScore(score)}/{assignmentData['max_points']}{formatAnnot(annot)}")
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
    if makePdf:
        pdfkit.from_file(f'./reports/{studentIdentifier}.html', f'./reports/{studentIdentifier}.pdf')
#############################

def get_assignmenthtml(studentData, allAssignments, outputConfigObj):
    html_str = ""
    for obj in outputConfigObj["content"]:
        html_str += f"<h2>{obj['title']}</h2>"
        index = 0
        for (assignmentName, assignmentData) in allAssignments.items():
            if assignmentData['type'] == obj["from"]:
                index += 1
                (score, annot) = studentData[GRADES_KEY].get(assignmentName, (0, None))
                ogscore = f"{formatScore(score)}/{assignmentData['max_points']}"
                prefix = f"<p><b>{assignmentName}:</b> "
                html_str += f"{prefix} {ogscore}{formatAnnot(annot)} </p>"
    return html_str

def formatAnnot(annot):
    if annot == None:
        return ''
    else:
        return f' ({annot})'

def formatScore(score):
    '''Returns simplest fixed-point formatting, e.g. 3.10 -> 3.1, 3.00 -> 3'''
    return ('%f' % score).rstrip('0').rstrip('.')