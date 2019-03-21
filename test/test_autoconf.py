import autoconf

def test_answer():
    potentialAttrFields = ['a random column', 'Your SID (required!)', 'your section']
    allAttrs = autoconf.DEFAULT_ATTR_DICT
    expectedMatching = {'Your SID (required!)': 'Student ID'}
    expectedIgnored = ['your section']
    # 'Your SID (required!)' should get matched to 'Student ID' because it's an
    # identifying attribute; 'your section' should be in the ignore list because
    # Section is a non-identifying attribute; 'a random column' should not be in either
    # because it's not a student attribute
    assert autoconf.guessAttrConfig(potentialAttrFields, allAttrs) == (expectedMatching, expectedIgnored)