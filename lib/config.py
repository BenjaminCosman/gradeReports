# The config json file format allows some syntactic sugar to make it easier to
# read and write. Accordingly, the files should always be written and read
# using this module, which desugars on read and resugars on write

import json
from pathlib import Path

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
    return configObj

def saveConfig():
    raise Exception("not yet implemented (TODO)")