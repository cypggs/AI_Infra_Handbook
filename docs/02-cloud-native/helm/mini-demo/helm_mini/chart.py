"""Chart 数据结构 —— Helm “软件包”的内存表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any


@dataclass
class ChartMetadata:
    """对应 ``Chart.yaml`` 的关键字段。

    易错点辨析（见正文 2.1）：
      * ``version``      —— Chart **自己**的版本（Helm 依赖解析/索引用它）。
      * ``appVersion``   —— 被打包应用/镜像的版本，**仅给人读**，Helm 计算时不读它。
      * ``apiVersion``   —— Chart 格式版本（v2 = Helm 3），不是 K8s apiVersion。
    """

    name: str
    version: str = "0.1.0"
    appVersion: str = ""
    apiVersion: str = "v2"
    type: str = "application"          # application | library
    description: str = ""
    dependencies: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Chart:
    """一个 Chart = 元数据 + 默认 values + 一组模板文件。"""

    metadata: ChartMetadata
    templates: List[Tuple[str, str]] = field(default_factory=list)  # [(name, text), ...]
    values: Dict[str, Any] = field(default_factory=dict)            # values.yaml 内容
    dependencies: List["Chart"] = field(default_factory=list)       # 子 chart（已解析）

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def version(self) -> str:
        return self.metadata.version
