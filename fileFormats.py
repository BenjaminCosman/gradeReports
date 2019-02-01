import csv, sys, os
import openpyxl

# Dispatches to one of the functions below
def getRows(sourceFileName, isRoster, sheetName):
    (_, ext) = os.path.splitext(sourceFileName)
    if ext == '.csv':
        if isRoster:
            return getRowsRosterCSV(sourceFileName)
        else:
            return getRowsNormalCSV(sourceFileName)
    elif ext == '.xlsx':
        if isRoster:
            if sheetName == None:
                raise Exception("must specify sheetName for roster")
            else:
                return getRowsRosterSingleSheetXLSX(sourceFileName, sheetName)
        else:
            if sheetName == None:
                return getRowsNormalMultiSheetXLSX(sourceFileName)
            else:
                return getRowsNormalSingleSheetXLSX(sourceFileName, sheetName)
    else:
        print(sourceFileName)
        raise Exception("unknown filetype")

def getRowsNormalCSV(sourceFileName):
    with open(sourceFileName) as source:
        return list(csv.DictReader(source))

def getRowsRosterCSV(sourceFileName):
    with open(sourceFileName) as source:
        while peek_line(source) != "Sec ID,PID,Student,Credits,College,Major,Level,Email\n":
            source.readline()
        return list(csv.DictReader(source))

def getRowsNormalSingleSheetXLSX(sourceFileName, sheetname):
    wb = openpyxl.load_workbook(filename=sourceFileName, read_only=True)
    ws = None
    for sheet in wb:
        if sheet.title == sheetname:
            ws = sheet
            break
    if ws == None:
        raise Exception("sheet not found")
    it = ws.values
    header = it.__next__()
    fieldnames = list(header)
    return xlsxRows(fieldnames, it)

def getRowsNormalMultiSheetXLSX(sourceFileName):
    wb = openpyxl.load_workbook(filename=sourceFileName, read_only=True)
    output = []
    for ws in wb:
        it = ws.values
        header = it.__next__()
        fieldnames = list(header)
        rows = xlsxRows(fieldnames, it)
        for row in rows:
            row.update({"_sheetName": ws.title})
        output += rows
    return output

def getRowsRosterSingleSheetXLSX(sourceFileName, sheetname):
    wb = openpyxl.load_workbook(filename=sourceFileName, read_only=True)
    ws = None
    for sheet in wb:
        if sheet.title == sheetname:
            ws = sheet
            break
    if ws == None:
        raise Exception("sheet not found")

    it = ws.values
    fieldnames = ['Sec ID','PID','Student','Credits','College','Major','Level','Email']
    foundHeader = False
    for row in it:
        if list(row) == fieldnames:
            foundHeader = True
            break
    if not foundHeader:
        raise Exception("roster header not found")

    return xlsxRows(fieldnames, it)


def xlsxRows(fieldnames, it):
    rows = []
    for row in it:
        row = list(row)
        if len(row) > len(fieldnames):
            print("WARNING: row is longer than header")
        if len(row) < len(fieldnames):
            row = row + [None]*(len(fieldnames)-len(row))
        rows.append(dict(zip(fieldnames, map(str, row))))
    return rows
