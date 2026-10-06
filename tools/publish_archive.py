"""Publish directories of archives under the site, where any HTTP client reads them.

    uv run python -m tools.publish_archive site/dist/archive runs grid

Each directory lands at ``<out>/<name>/``: every archive as the solve wrote
it, and beside them every path stacked across the archives, as
[`showcase.warehouse.publish`] writes them.
"""

import sys
from pathlib import Path

from showcase import warehouse


def main(out: Path, directories: list[Path]) -> None:
    for directory in directories:
        warehouse.publish(directory, out / directory.name)
        print(f'{directory} published at {out / directory.name}')


if __name__ == '__main__':
    main(Path(sys.argv[1]), [Path(d) for d in sys.argv[2:]])
