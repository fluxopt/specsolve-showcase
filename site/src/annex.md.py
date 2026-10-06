"""The reference run as an annex: every declaration typeset, with what it cost.

A page loader: it prints Markdown at build time, which the site renders like
any other page, equations included. The join between the math and the numbers
is :mod:`showcase.annex`, which imports no specsolve — the equations come from
mathspec and the numbers come from the archived parquet.
"""

import os
import re
import sys
from pathlib import Path

from showcase.annex import annex

ROOT = Path(__file__).resolve().parents[2]
runs = Path(os.environ.get('SHOWCASE_RUNS', '../runs'))
archives = sorted(p.parent.name for p in runs.glob('*/spec.yaml'))
if not archives:
    sys.exit(f'{runs.resolve()} holds no archive: run `showcase-solve --runs {runs}` first')

run = archives[0]
body = annex(runs, run, ROOT / 'models' / 'pathway.symbols.yaml')
# GitHub's inline math delimiter becomes the site's, as on the model page.
body = re.sub(r'\$`(.+?)`\$', lambda m: '${tex`' + m.group(1) + '`}', body)

sys.stdout.write(f"""---
title: Annex
---

# {run}, as solved

The [model page](./model) prints the spec with nothing bound: no data, no solver, just what the YAML states. The other pages print what the solver returned, with no math beside it. This page is the two joined — every declaration in the notation [`models/pathway.symbols.yaml`](https://github.com/fluxopt/specsolve-showcase/blob/main/models/pathway.symbols.yaml) declares, and under each one what the archive says it cost.

An annex is about one run, and this is `{run}`. Any other archive in the directory prints the same way:

```bash
uv run showcase-annex carbon_cap --runs runs
```

{body}
""")
