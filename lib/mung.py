import re

def checkAndClean(s, filters):
    for f in filters:
        s = filtersAndChecks[f](s)
    return s

class IncorrectFormatException(Exception):
    pass
def ucsdStudentIDCheck(x):
    if not re.fullmatch(r'^[AU]\d{8}$', x):
        raise IncorrectFormatException()
    return x
def checkNChar(x, n):
    if len(x) != n:
        raise IncorrectFormatException()
    return x
filtersAndChecks = {
    'strip': lambda x: x.strip(),
    'ucsdIDCheck': ucsdStudentIDCheck,
    '8char': lambda x: checkNChar(x, 8),
    'remove#': lambda x: x[1:] if len(x) > 0 and x[0] == '#' else x,
    'toUpper': lambda x: x.upper(),
    'NVto0': lambda x: 0 if x == 'NV' else x,
    'NoneTo0': lambda x: 0 if x == '' or x == 'None' else x,
    'stripDenominator': lambda x: x.split('/')[0].strip(),
    'toFloat': float
}
