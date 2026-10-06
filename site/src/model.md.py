"""Typeset the model as solved, as a page: the math the archive's ``spec.yaml`` stands for.

A page loader: it prints Markdown at build time, which the site renders like any
other page, equations included. It reads the spec out of the archive and hands it
to the language's own typesetter, so what is printed is what was solved. The
language package has no solver in it; only the solve job imports specsolve.
"""

import os
import re
import sys
from pathlib import Path

import mathspec

runs = Path(os.environ.get('SHOWCASE_RUNS', '../runs'))
archives = sorted(runs.glob('*/spec.yaml'))
if not archives:
    sys.exit(f'{runs.resolve()} holds no archive: run `showcase-solve --runs {runs}` first')
symbols = Path(__file__).resolve().parents[2] / 'models' / 'pathway.symbols.yaml'

markdown = mathspec.to_markdown(archives[0].read_text(), symbols=symbols)
# GitHub's math delimiters become the site's: a ```tex fence for a block, ${tex`…`} inline.
markdown = markdown.replace('```math', '```tex')
markdown = re.sub(r'\$`(.+?)`\$', lambda m: '${tex`' + m.group(1) + '`}', markdown)

sys.stdout.write(f"""---
title: Model
---

# The model, as math

Printed from the `spec.yaml` that the solve job archived, by the language's own typesetter, in the notation that [`models/pathway.symbols.yaml`](https://github.com/fluxopt/specsolve-showcase/blob/main/models/pathway.symbols.yaml) declares. No data binds and no solver runs to produce this page: every equation below is what the YAML states, and every number on the other pages is what the solver made of it.

{markdown}
""")
