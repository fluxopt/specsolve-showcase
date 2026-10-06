"""Shape the runs directory into the one zip the pages read: every table, across every run.

Reads the directory the solve job wrote and solves nothing itself, so the site
is a reader of the archive like any other. ``SHOWCASE_RUNS`` names the
directory; the default is ``../runs``, which is the repository root's when the
site builds from ``site/``.
"""

import os
import sys
from pathlib import Path

from showcase import warehouse

runs = Path(os.environ.get('SHOWCASE_RUNS', '../runs'))
if not any(runs.glob('*/answer/record.parquet')):
    sys.exit(f'{runs.resolve()} holds no archive: run `showcase-solve --runs {runs}` first')
sys.stdout.buffer.write(warehouse.bundle(runs))
