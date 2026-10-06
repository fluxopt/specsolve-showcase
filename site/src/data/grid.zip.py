"""Shape the what-if grid into a zip, exactly as ``runs.zip`` is shaped: one more directory of archives, one more reader.

``SHOWCASE_GRID`` names the directory; the default is ``../grid``, which is
where ``showcase-grid`` writes from the repository root.
"""

import os
import sys
from pathlib import Path

from showcase import warehouse

grid = Path(os.environ.get('SHOWCASE_GRID', '../grid'))
if not any(grid.glob('*/answer/record.parquet')):
    sys.exit(f'{grid.resolve()} holds no archive: run `showcase-grid --runs {grid}` first')
sys.stdout.buffer.write(warehouse.bundle(grid))
