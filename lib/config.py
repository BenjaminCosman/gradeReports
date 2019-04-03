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
    for sourceObj in configObj['sources']:
        if 'sheetName' not in sourceObj:
            sourceObj['sheetName'] = None
        for assignment in sourceObj['assignments']:
            if 'filters' not in assignment:
                assignment['filters'] = ALL_DEFAULT_FILTERS

    # Turn multi-sheet xlsx sources into multiple single-sheet ones
    newSources = []
    for sourceObj in configObj['sources']:
        if Path(sourceObj['file']).suffix != '.xlsx' or sourceObj['sheetName'] != None:
            newSources.append(sourceObj)
        else:
            usedSheets = [item['sheetName'] for item in sourceObj[ASSIGNMENTS_KEY]]
            for sheetName in usedSheets:
                newSource = copy.deepcopy(sourceObj)
                newSource['sheetName'] = sheetName
                newSource[ASSIGNMENTS_KEY] = list(filter(lambda x: x['sheetName'] == sheetName, newSource[ASSIGNMENTS_KEY]))
                for item in newSource[ASSIGNMENTS_KEY]:
                    item.pop('sheetName')
                newSources.append(newSource)
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
        del newSourceConfig['sheetName']
        newSourceConfig['assignments'] = allAssignments
        oldFirstIdx = [i for (i,x) in enumerate(newConfig['sources']) if x['file'] == fileName][0]
        newConfig['sources'] = [x for x in newConfig['sources'] if x['file'] != fileName]
        newConfig['sources'].insert(oldFirstIdx, newSourceConfig)

    # Remove default filters and sheetName values
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
