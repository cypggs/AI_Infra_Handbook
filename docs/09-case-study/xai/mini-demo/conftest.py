# 让 tests/ 以包形式被 pytest 收集，并固定 float 显示精度
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
