"""yaml_lite — 一个极简、自包含的 YAML 序列化/解析器。

为什么不用 PyYAML？为了让本 demo **零第三方依赖**、拷下来 ``pytest`` 就能跑
（与容器运行时 mini-demo 一致的“纯 Python、无需安装”理念）。

只覆盖本 demo 会用到的语法子集：
- 多文档（``---`` 分隔）
- 块映射（``key: value``，2 空格缩进）
- 块序列（``- item``）
- 序列项是内联映射（``- name: x`` 续行）
- 标量：int / float / bool / null / 带引号字符串 / 纯字符串

**约定**：缩进恒为 2 空格的整数倍；序列项比所属 key 再深一级。
``dump`` 严格按此约定输出，``load_all`` 据此解析，二者保证本 demo 清单的往返一致。
真实 YAML 远比这复杂（流式、多行字符串、锚点、tag），本模块**不**追求通用。
"""

from __future__ import annotations

MISSING = object()  # “字段缺失”，区别于 None（YAML 的 null）


# --------------------------------------------------------------------------- #
# 标量序列化
# --------------------------------------------------------------------------- #
def _looks_like_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


_NEED_QUOTE = set(":#{}[],&*!|>'\"%@`")


def dump_scalar(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, int):
        return str(v)
    s = str(v)
    needs = (
        s == ""
        or s.strip() != s
        or s.lower() in ("true", "false", "null", "none", "~", "yes", "no", "on", "off")
        or _looks_like_number(s)
        or s[0] in "-? "
        or any(c in _NEED_QUOTE for c in s)
    )
    return ('"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"') if needs else s


# --------------------------------------------------------------------------- #
# 对象 -> YAML 文本
# --------------------------------------------------------------------------- #
def _emit_pair(out, k, v, key_pad, level):
    """把一对 key/value 追加到 out（list），嵌套值用 level+2 缩进。"""
    if isinstance(v, dict):
        if v:
            out.append(f"{key_pad}{k}:")
            out.append(_dump_map(v, level + 2))
        else:
            out.append(f"{key_pad}{k}: {{}}")
    elif isinstance(v, list):
        if v:
            out.append(f"{key_pad}{k}:")
            out.append(_dump_seq(v, level + 2))
        else:
            out.append(f"{key_pad}{k}: []")
    else:
        out.append(f"{key_pad}{k}: {dump_scalar(v)}")


def _dump_map(obj: dict, level: int) -> str:
    pad = "  " * level
    lines = []
    for k, v in obj.items():
        if isinstance(v, dict) and v:
            lines.append(f"{pad}{k}:")
            lines.append(_dump_map(v, level + 1))
        elif isinstance(v, list) and v:
            lines.append(f"{pad}{k}:")
            lines.append(_dump_seq(v, level + 1))
        else:
            lines.append(f"{pad}{k}: {{}}" if isinstance(v, dict) and not v
                         else (f"{pad}{k}: []" if isinstance(v, list) and not v
                               else f"{pad}{k}: {dump_scalar(v)}"))
    return "\n".join(lines)


def _dump_seq(items: list, level: int) -> str:
    pad = "  " * level
    lines = []
    for it in items:
        if isinstance(it, dict):
            if not it:
                lines.append(f"{pad}- {{}}")
                continue
            k0, v0 = next(iter(it.items()))
            # 第一对写在 dash 行（嵌套值换行）
            if isinstance(v0, dict) and v0:
                lines.append(f"{pad}- {k0}:")
                lines.append(_dump_map(v0, level + 2))
            elif isinstance(v0, list) and v0:
                lines.append(f"{pad}- {k0}:")
                lines.append(_dump_seq(v0, level + 2))
            elif isinstance(v0, dict):
                lines.append(f"{pad}- {k0}: {{}}")
            elif isinstance(v0, list):
                lines.append(f"{pad}- {k0}: []")
            else:
                lines.append(f"{pad}- {k0}: {dump_scalar(v0)}")
            # 后续对缩进一级（对齐 dash 之后）
            for k, v in list(it.items())[1:]:
                _emit_pair(lines, k, v, pad + "  ", level)
        elif isinstance(it, list):
            lines.append(f"{pad}-")
            lines.append(_dump_seq(it, level + 1))
        else:
            lines.append(f"{pad}- {dump_scalar(it)}")
    return "\n".join(lines)


def dump(obj) -> str:
    if isinstance(obj, dict):
        return _dump_map(obj, 0)
    if isinstance(obj, list):
        return _dump_seq(obj, 0)
    return dump_scalar(obj)


# --------------------------------------------------------------------------- #
# 文本 -> 对象（解析）
# --------------------------------------------------------------------------- #
def _parse_scalar(s: str):
    s = s.strip()
    if s == "" or s in ("~", "null", "Null", "NULL", "None"):
        return None
    if (s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"):
        return s[1:-1]
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _to_level_lines(text: str):
    """把一段文档文本切成 (level, text) 行，丢弃空行与整行注释。"""
    out = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        if stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        out.append((indent // 2, stripped))
    return out


def _split_docs(text: str):
    docs, cur = [], []
    for raw in text.split("\n"):
        if raw.strip() == "---":
            docs.append("\n".join(cur))
            cur = []
        else:
            cur.append(raw)
    docs.append("\n".join(cur))
    return [d for d in docs if d.strip()]


def _parse_block(lines):
    if not lines:
        return None
    if lines[0][1].startswith("- ") or lines[0][1] == "-":
        return _parse_seq(lines, lines[0][0])
    return _parse_map(lines, lines[0][0])


def _parse_map(lines, base):
    obj, i, n = {}, 0, len(lines)
    while i < n:
        lvl, text = lines[i]
        if lvl < base:
            break
        if lvl > base:  # 越界的深行（不应出现），跳过
            i += 1
            continue
        if text.startswith("- "):  # 同级出现序列 -> 映射结束
            break
        key, sep, val = text.partition(":")
        if not sep:
            i += 1
            continue
        key, val = key.strip(), val.strip()
        if val != "":
            obj[key] = _parse_scalar(val)
            i += 1
        else:
            # 子块 = 紧随其后的、缩进更深的一段“连续”行（遇到回到 base 或更浅即止）
            j = i + 1
            while j < n and lines[j][0] > base:
                j += 1
            child = lines[i + 1:j]
            obj[key] = _parse_block(child) if child else None
            i = j
    return obj


def _parse_seq(lines, base):
    arr, i, n = [], 0, len(lines)
    while i < n:
        lvl, text = lines[i]
        if lvl < base:
            break
        if lvl > base:
            i += 1
            continue
        if not (text.startswith("- ") or text == "-"):
            break
        rest = text[2:].strip() if text.startswith("- ") else ""
        if rest == "":  # dash 下挂嵌套块
            child = []
            j = i + 1
            while j < n and lines[j][0] > base:
                child.append(lines[j])
                j += 1
            arr.append(_parse_block(child) if child else None)
            i = j
            continue
        if ":" in rest:  # 内联映射项 `- k: v` 或 `- k:`
            k, _, v = rest.partition(":")
            k, v = k.strip(), v.strip()
            cont_level = base + 1
            child = []
            j = i + 1
            while j < n and lines[j][0] >= cont_level and not (
                lines[j][0] == base and lines[j][1].startswith("- ")
            ):
                child.append(lines[j])
                j += 1
            if v != "":
                item = {k: _parse_scalar(v)}
                if child:
                    item.update(_parse_map(child, child[0][0]))
            else:  # k 的值是嵌套块
                item = {k: _parse_block(child) if child else None}
            arr.append(item)
            i = j
        else:
            arr.append(_parse_scalar(rest))
            i += 1
    return arr


def load_all(text: str) -> list:
    """解析多文档 YAML 文本，返回 dict 列表（每个文档一个）。"""
    docs = []
    for doc in _split_docs(text):
        lines = _to_level_lines(doc)
        if not lines:
            continue
        parsed = _parse_block(lines)
        if parsed is not None:
            docs.append(parsed)
    return docs
