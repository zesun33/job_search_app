"""Job Search Application metapackage.
Including this package via `pip install -e .` puts the `src` directory on
`sys.path` so that modules like `src.utils` can be imported simply as
`import src.utils.xxx` or by their short names once the path is added.
"""
import sys
from pathlib import Path

_src_path = Path(__file__).resolve().parent.parent / "src"
if _src_path.exists():
    sys.path.insert(0, str(_src_path))

del _src_path 