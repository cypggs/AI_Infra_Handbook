"""pytest 配置：把 mini-demo 根目录加入 sys.path，无需 pip install。"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
