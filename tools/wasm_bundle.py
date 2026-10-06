"""Put beside the browser notebook what Pyodide does not ship: our wheels, and the pathway model.

    uv run python -m tools.wasm_bundle site/dist/session-app

The notebook's bootstrap cell installs the packages Pyodide ships by name,
then the wheels ``wheels/manifest.json`` lists with ``deps=False``. This
downloads specsolve and mathspec at the versions locked here, so the browser
runs what the tests ran, and builds this repository's own wheel. The pathway model is copied under
``models/`` because the notebook reads it by path when it runs locally and
fetches it by the same path in the browser. The page is also told to run its
cells on load.
"""

import json
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).parents[1]

#: The wheels the notebook installs, in the order it installs them.
ORDER = ['mathspec', 'specsolve', 'specsolve_showcase']


def main(out: Path) -> None:
    wheels = out / 'wheels'
    wheels.mkdir(parents=True, exist_ok=True)
    pins = [f'{name}=={version(name)}' for name in ORDER[:2]]
    download = [sys.executable, '-m', 'pip', 'download', '--no-deps', '--only-binary', ':all:', '-q', '-d', str(wheels)]
    subprocess.run([*download, *pins], check=True)
    subprocess.run(['uv', 'build', '--wheel', '-q', '-o', str(wheels)], cwd=ROOT, check=True)
    names = sorted((w.name for w in wheels.glob('*.whl')), key=lambda n: ORDER.index(n.split('-')[0]))
    (wheels / 'manifest.json').write_text(json.dumps(names, indent=1))
    (out / 'models').mkdir(exist_ok=True)
    shutil.copy(ROOT / 'models' / 'pathway.yaml', out / 'models' / 'pathway.yaml')
    run_on_load(out / 'index.html')
    print(f'{out}: {", ".join(names)}, models/pathway.yaml')


def run_on_load(index: Path) -> None:
    """Make the exported page run its cells on load in edit mode.

    marimo's export embeds its built-in defaults rather than the project's
    config, and the built-in default leaves an edit-mode notebook idle until
    the reader presses run.
    """
    text = index.read_text()
    flag = '"auto_instantiate": false'
    if text.count(flag) != 1:
        raise LookupError(f'{index} carries {text.count(flag)} copies of {flag}; expected one')
    index.write_text(text.replace(flag, '"auto_instantiate": true'))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
