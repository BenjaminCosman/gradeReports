import subprocess
from pathlib import Path

def test_answer():
    res = subprocess.run(['python3', 'main.py', 'examples/config.json'], capture_output=True)
    assert res.stdout.decode("utf-8") == Path('test/exampleOutput.txt').read_text()
