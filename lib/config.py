# The config json file format allows some syntactic sugar to make it easier to
# read and write. Accordingly, the files should always be written and read
# using this module, which desugars on read and resugars on write

import json, copy
from pathlib import Path

from lib.constants import ASSIGNMENTS_KEY

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

def saveConfig():
    raise Exception("not yet implemented (TODO)")