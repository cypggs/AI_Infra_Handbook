# 让 pytest 无需安装即可从仓库根目录直接跑（pyproject 里也配置了 pythonpath）。
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
