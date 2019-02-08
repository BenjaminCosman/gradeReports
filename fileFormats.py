import csv, sys, os
import pyexcel as pe

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
    return pe.get_records(file_name=sourceFileName, auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)

def getRowsRosterCSV(sourceFileName):
    with open(sourceFileName) as source:
        while peek_line(source) != "Sec ID,PID,Student,Credits,College,Major,Level,Email\n":
            source.readline()
        #TODO: this is really ugly. pe.get_records supposedly has other input modes like file_content?
        with open('tempTrimmedRoster.csv', 'w') as f:
            f.write(source.read())
        rows = pe.get_records(file_name='tempTrimmedRoster.csv', auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)
        os.remove('tempTrimmedRoster.csv')
        return rows


# https://stackoverflow.com/a/16840747/6036628
def peek_line(f):
    pos = f.tell()
    line = f.readline()
    f.seek(pos)
    return line

def getRowsNormalSingleSheetXLSX(sourceFileName, sheetname):
    return pe.get_records(file_name=sourceFileName, sheet_name=sheetname, auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)

def getRowsNormalMultiSheetXLSX(sourceFileName):
    #TODO: probably terrible performance - loading whole book just to read sheet names
    sheets = pe.get_book_dict(file_name=sourceFileName).keys()
    output = []
    for sheetname in sheets:
        rows = pe.get_records(file_name=sourceFileName, sheet_name=sheetname, auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)
        for row in rows:
            row.update({"_sheetName": sheetname})
        output += rows
    return output

def getRowsRosterSingleSheetXLSX(sourceFileName, sheetname):
    allRows = pe.get_array(file_name=sourceFileName, sheet_name=sheetname, auto_detect_float=False, auto_detect_int=False, auto_detect_datetime=False)
    idx = allRows.index(['Sec ID','PID','Student','Credits','College','Major','Level','Email'])
    if idx == -1:
        raise Exception("not a roster")
    return pe.get_records(array=allRows[idx:])
