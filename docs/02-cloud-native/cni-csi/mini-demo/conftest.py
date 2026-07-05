"""conftest.py — 保证 `cni_csi_mini` 包在未安装时也可被 pytest 导入。"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
