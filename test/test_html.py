import subprocess
from pathlib import Path

def test_answer():
    subprocess.run(['python3', 'main.py', 'examples/config.json'])
    assert Path('reports/A12345678.html').read_text() == Path('test/exampleHtml.html').read_text()
