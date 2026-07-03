"""pytest 配置：保证 crt_mini 可被导入（无需 pip install）。"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
