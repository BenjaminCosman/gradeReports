# The config json file format allows some syntactic sugar to make it easier to
# read and write. Accordingly, the files should always be written and read
# using this module, which desugars on read and resugars on write

import json, copy
from pathlib import Path

from lib.constants import ASSIGNMENTS_KEY, ALL_DEFAULT_FILTERS

def loadConfig(filename):
    configObj = json.loads(Path(filename).read_text())

    # Canonicalize studentAttributes dict with defaults
    for (k,v) in configObj["studentAttributes"].items():
        if "identifiesStudent" not in v:
            v["identifiesStudent"] = False
        if "onePerStudent" not in v:
            v["onePerStudent"] = False
        if "filters" not in v:
            v["filters"] = []

    # Turn multi-sheet xlsx sources into multiple single-sheet ones
    newSources = []
    for sourceObj in configObj['sources']:
        if Path(sourceObj['file']).suffix != '.xlsx' or 'sheetName' in sourceObj:
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
    newConfig = copy.deepcopy(configObj)
    for obj in newConfig['sources']:
        for assignment in obj['assignments']:
            if assignment['filters'] == ALL_DEFAULT_FILTERS:
                del assignment['filters']
        if obj['sheetName'] == None:
            del obj['sheetName']
    Path(filename).write_text(json.dumps(newConfig, indent=2, separators=(',', ': ')))