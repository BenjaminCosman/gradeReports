# The config json file format allows some syntactic sugar to make it easier to
# read and write. Accordingly, the files should always be written and read
# using this module, which desugars on read and resugars on write

import json, copy, itertools
from pathlib import Path
import pyexcel as pe

from lib.constants import ASSIGNMENTS_KEY, ALL_DEFAULT_FILTERS

def loadConfig(filename):
    configObj = json.loads(Path(filename).read_text())

    # Add various default values
    for (k,v) in configObj["studentAttributes"].items():
        if "identifiesStudent" not in v:
            v["identifiesStudent"] = False
        if "onePerStudent" not in v:
            v["onePerStudent"] = False
        if "filters" not in v:
            v["filters"] = []
        if "onlyPrintIfPresent" not in v:
            v["onlyPrintIfPresent"] = False
    for sourceObj in configObj['sources']:
        if 'sheetName' not in sourceObj:
            sourceObj['sheetName'] = None
        for assignment in sourceObj[ASSIGNMENTS_KEY]:
            if 'filters' not in assignment:
                assignment['filters'] = ALL_DEFAULT_FILTERS
    if 'processing' not in configObj:
        configObj['processing'] = []

    # Turn multi-sheet xlsx sources into multiple single-sheet ones
    newSources = []
    for sourceObj in configObj['sources']:
        if Path(sourceObj['file']).suffix == '.xlsx' and sourceObj['sheetName'] == None:
            # Found a multi-sheet xlsx source (or a single sheet source that did not
            # specify the sheet name)

            assignments = sourceObj[ASSIGNMENTS_KEY]

            # Case 1: No assignment specifies a sheet name. (This case includes if
            # there are no assignments)
            # Duplicate source once for each sheet in document.
            if all('sheetName' not in item for item in assignments):
                book = pe.get_book(file_name=sourceObj['file'])
                for sheetName in book.sheet_names():
                    newSource = copy.deepcopy(sourceObj)
                    newSource['sheetName'] = sheetName
                    newSources.append(newSource)

            # Case 2: There are assignments and each specifies a sheet name.
            # Duplicate source once for each named sheet and partition
            # assignments by sheet name
            elif all('sheetName' in item for item in assignments):
                usedSheets = [item['sheetName'] for item in assignments]
                for sheetName in usedSheets:
                    newSource = copy.deepcopy(sourceObj)
                    newSource['sheetName'] = sheetName
                    newSource[ASSIGNMENTS_KEY] = list(filter(lambda x: x['sheetName'] == sheetName, newSource[ASSIGNMENTS_KEY]))
                    for item in newSource[ASSIGNMENTS_KEY]:
                        item.pop('sheetName')
                    newSources.append(newSource)

            # Case 3: At least one assignment specifies a sheet name and at least
            # one does not. This is not allowed
            else:
                raise Exception(f"In source {sourceObj['file']}, either all or none of the assignments must specify a sheet name.")
        else:
            # Single-sheet source; no editing needed
            newSources.append(sourceObj)

    configObj['sources'] = newSources

    return configObj


def saveConfig(filename, configObj):
    '''shouldn't modify configObj but TODO probably does'''
    newConfig = copy.deepcopy(configObj)

    # Collapse xlsx sources from the same file if possible
    xlsxSources = [(obj['file'], obj['sheetName']) for obj in newConfig['sources'] if Path(obj['file']).suffix == '.xlsx']
    xlsxSources.sort()
    groups = itertools.groupby(xlsxSources, lambda x: x[0])
    for (fileName, sourceIter) in groups:
        sourceConfigObjs = []
        for source in sourceIter:
            sourceConfigObjs += [x for x in newConfig['sources'] if x['file'] == source[0] and x['sheetName'] == source[1]]

        if not isMultiSheetXLSXResugarable(sourceConfigObjs):
            continue

        allAssignments = list(itertools.chain.from_iterable([addSheetName(x['assignments'], x['sheetName']) for x in sourceConfigObjs]))
        newSourceConfig = copy.deepcopy(sourceConfigObjs[0])
        newSourceConfig['sheetName'] = None
        newSourceConfig['assignments'] = allAssignments
        oldFirstIdx = [i for (i,x) in enumerate(newConfig['sources']) if x['file'] == fileName][0]
        newConfig['sources'] = [x for x in newConfig['sources'] if x['file'] != fileName]
        newConfig['sources'].insert(oldFirstIdx, newSourceConfig)

    # Remove some default values
    for (k,v) in newConfig["studentAttributes"].items():
        if "filters" in v and v["filters"] == []:
            del v["filters"]
        if "onlyPrintIfPresent" in v and v["onlyPrintIfPresent"] == False:
            del v["onlyPrintIfPresent"]
    for obj in newConfig['sources']:
        for assignment in obj['assignments']:
            if assignment['filters'] == ALL_DEFAULT_FILTERS:
                del assignment['filters']
        if obj['sheetName'] == None:
            del obj['sheetName']

    Path(filename).write_text(json.dumps(newConfig, indent=2, separators=(',', ': ')))

def isMultiSheetXLSXResugarable(sourceConfigObjs):
    attrConfigs = [x['attributes'] for x in sourceConfigObjs]
    for attrDict in attrConfigs:
        if attrDict != attrConfigs[0]:
            return False
    return True

def addSheetName(assignments, sheetName):
    for assignment in assignments:
        assignment['sheetName'] = sheetName
    return assignments
