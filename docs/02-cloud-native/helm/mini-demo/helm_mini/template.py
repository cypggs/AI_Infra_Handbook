"""模板引擎 —— Go text/template + Sprig 的极简子集。

支持（足以渲染真实的 Deployment/Service/ConfigMap）：
  * 取值：``.Values.x.y`` / ``.Release.Name`` / ``.Chart.Version`` / ``.``（当前作用域）
  * 管道函数：``quote`` / ``default`` / ``required`` / ``toYaml`` / ``nindent`` / ``indent``
              ``trunc`` / ``trimSuffix`` / ``lower`` / ``upper`` / ``title``
  * 控制结构：``if`` / ``else`` / ``with``（重绑作用域）/ ``range``（迭代）
  * 命名模板：``define`` + ``include "name" .``
  * 空白修剪：``{{- ... -}}``

有意省略（教学，非生产）：复杂管道、``range ... := ...`` 的 key/val 解构、
Sprig 的 200+ 函数、``tpl`` 二次渲染。详见 07-mini-demo.md 的“与真实 Helm 差异表”。

作用域模型（简化）：路径首段若是根上下文键（Values/Release/Chart/...）则从根解析；
否则从当前 ``.``（with/range 绑定的值）解析。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .yaml_lite import dump as _yaml_dump


class TemplateError(Exception):
    pass


_TAG = re.compile(r"\{\{(-)?(.*?)(-)?\}\}", re.DOTALL)
_ROOT_KEYS = {"Values", "Release", "Chart", "Files", "Capabilities", "Template"}


# --------------------------------------------------------------------------- #
# 词法
# --------------------------------------------------------------------------- #
def _tokenize(text: str) -> List[dict]:
    out: List[dict] = []
    pos = 0
    for m in _TAG.finditer(text):
        if m.start() > pos:
            out.append({"kind": "text", "text": text[pos:m.start()]})
        out.append({
            "kind": "dir",
            "inner": m.group(2).strip(),
            "tl": m.group(1) == "-",
            "tr": m.group(3) == "-",
        })
        pos = m.end()
    if pos < len(text):
        out.append({"kind": "text", "text": text[pos:]})
    return out


def _apply_trim(tokens: List[dict]) -> None:
    for i, tok in enumerate(tokens):
        if tok["kind"] != "dir":
            continue
        if tok["tl"] and i > 0 and tokens[i - 1]["kind"] == "text":
            tokens[i - 1]["text"] = tokens[i - 1]["text"].rstrip()
        if tok["tr"] and i + 1 < len(tokens) and tokens[i + 1]["kind"] == "text":
            tokens[i + 1]["text"] = tokens[i + 1]["text"].lstrip()


# --------------------------------------------------------------------------- #
# 解析为节点树
# --------------------------------------------------------------------------- #
def _build_tree(tokens: List[dict]) -> Tuple[List, Dict[str, list]]:
    """返回 (root_nodes, defines)。defines: 名字 -> 节点列表（include 时渲染）。"""
    defines: Dict[str, list] = {}
    root: List[Any] = []
    stack: List[dict] = []          # 栈帧: {"node", "parent_target", "node_type"}
    target = root

    for tok in tokens:
        if tok["kind"] == "text":
            if tok["text"]:
                target.append(("text", tok["text"]))
            continue
        inner = tok["inner"]
        if not inner:
            continue
        parts = inner.split()
        verb = parts[0]

        if verb in ("if", "with", "range"):
            node = {
                "type": verb,
                "expr": inner[len(verb):].strip(),
                "body": [],
                "orelse": [],
            }
            target.append(node)
            stack.append({"node": node, "parent_target": target})
            target = node["body"]

        elif verb == "else":
            if not stack:
                raise TemplateError("else without if/with/range")
            target = stack[-1]["node"]["orelse"]

        elif verb == "end":
            if not stack:
                raise TemplateError("end without block")
            frame = stack.pop()
            target = frame["parent_target"]

        elif verb == "define":
            # define "name"
            name = _parse_literal_str(" ".join(parts[1:]))
            node = {"type": "define", "name": name, "body": []}
            defines[name] = node["body"]
            target.append(node)
            stack.append({"node": node, "parent_target": target})
            target = node["body"]

        elif verb in ("/*", "*/"):
            continue  # 注释，忽略

        else:
            target.append(("expr", inner))

    if stack:
        raise TemplateError(f"unclosed block: {stack[-1]['node']['type']}")
    return root, defines


def _parse_literal_str(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


# --------------------------------------------------------------------------- #
# 求值
# --------------------------------------------------------------------------- #
def _truthy(v: Any) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and v == 0:
        return False
    if isinstance(v, (str, list, dict)) and len(v) == 0:
        return False
    return True


def _lookup(path: str, ctx: dict, scope: Any) -> Any:
    segs = path.split(".")
    first = segs[0]
    if first in ctx:                       # 根键 -> 从根解析
        cur: Any = ctx[first]
        rest = segs[1:]
    elif isinstance(scope, dict):          # 否则从当前作用域解析
        cur = scope
        rest = segs
    else:
        return None
    for s in rest:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(s)
        elif isinstance(cur, list):
            try:
                cur = cur[int(s)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _eval_value(tok: str, ctx: dict, scope: Any) -> Any:
    tok = tok.strip()
    if tok == ".":
        return scope if scope is not None else ctx
    if tok.startswith("."):
        return _lookup(tok[1:], ctx, scope)
    if len(tok) >= 2 and ((tok[0] == '"' and tok[-1] == '"') or (tok[0] == "'" and tok[-1] == "'")):
        return tok[1:-1]
    if tok in ("true", "True"):
        return True
    if tok in ("false", "False"):
        return False
    if tok in ("nil", "null", "None"):
        return None
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    raise TemplateError(f"cannot evaluate value: {tok!r}")


def _indent(text: str, n: int, leading_newline: bool) -> str:
    pad = " " * n
    body = "\n".join(pad + line if line else line for line in text.split("\n"))
    return ("\n" + body) if leading_newline else body


def _unary(fn: str, value: Any) -> Any:
    if fn == "quote":
        s = str(value)
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if fn == "toYaml":
        return _yaml_dump(value).strip()
    if fn == "lower":
        return str(value).lower()
    if fn == "upper":
        return str(value).upper()
    if fn == "title":
        return str(value).title()
    raise TemplateError(f"not a unary function: {fn}")


def _apply_func(stage: str, value: Any, ctx: dict, scope: Any) -> Any:
    parts = stage.split()
    fn = parts[0]
    args = [_eval_value(a, ctx, scope) for a in parts[1:]]

    if fn == "quote":
        return _unary("quote", value)
    if fn == "toYaml":
        return _unary("toYaml", value)
    if fn in ("lower", "upper", "title"):
        return _unary(fn, value)
    if fn == "default":
        return value if _truthy(value) else (args[0] if args else "")
    if fn == "required":
        if not _truthy(value):
            raise TemplateError(f"required value missing: {args[0] if args else '(no message)'}")
        return value
    if fn == "trunc":
        return str(value)[: int(args[0])]
    if fn == "trimSuffix":
        suf, s = str(args[0]), str(value)
        return s[: -len(suf)] if suf and s.endswith(suf) else s
    if fn == "nindent":
        return _indent(str(value), int(args[0]), leading_newline=True)
    if fn == "indent":
        return _indent(str(value), int(args[0]), leading_newline=False)
    if fn == "replace":
        return str(value).replace(str(args[0]), str(args[1]))
    raise TemplateError(f"unknown function: {fn}")


def _eval_expr(expr: str, ctx: dict, scope: Any, defines: Dict[str, list],
               render_nodes) -> Any:
    expr = expr.strip()

    negate = False
    if expr.startswith("not "):
        negate = True
        expr = expr[4:].strip()

    pipe = [p.strip() for p in expr.split("|")]
    head = pipe[0]
    head_word = head.split(None, 1)[0] if head else ""

    # 函数出现在管道首位（无 piped 输入）：include / 一元变换 / default / required
    UNARY = {"toYaml", "quote", "lower", "upper", "title"}
    if head_word in ("include", "template"):
        rest = head[len(head_word):].strip()
        m = re.match(r'["\']([^"\']+)["\']\s*(.*)$', rest)
        if not m:
            raise TemplateError(f"bad include: {expr!r}")
        name = m.group(1)
        arg_expr = m.group(2).strip()
        arg = _eval_value(arg_expr, ctx, scope) if arg_expr else ctx
        body = defines.get(name)
        if body is None:
            raise TemplateError(f"template not defined: {name!r}")
        value = render_nodes(body, ctx, arg if isinstance(arg, dict) else ctx)
    elif head_word in UNARY:
        arg = head[len(head_word):].strip()
        raw = _eval_value(arg, ctx, scope) if arg else ""
        value = _unary(head_word, raw)
    elif head_word == "default":
        # default DEF VAL  ->  VAL 若真用 VAL，否则 DEF
        parts = head.split(None, 2)
        def_val = _eval_value(parts[1], ctx, scope)
        val = _eval_value(parts[2], ctx, scope) if len(parts) > 2 else ""
        value = val if _truthy(val) else def_val
    elif head_word == "required":
        parts = head.split(None, 2)
        msg = _eval_value(parts[1], ctx, scope)
        val = _eval_value(parts[2], ctx, scope) if len(parts) > 2 else ""
        if not _truthy(val):
            raise TemplateError(f"required value missing: {msg}")
        value = val
    else:
        value = _eval_value(head, ctx, scope)

    for stage in pipe[1:]:
        value = _apply_func(stage, value, ctx, scope)
    return (not _truthy(value)) if negate else value


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class Engine:
    """模板引擎。``defines`` 是命名模板集合（跨文件共享）。"""

    def __init__(self, defines: Optional[Dict[str, list]] = None):
        self.defines: Dict[str, list] = dict(defines or {})

    def _render_nodes(self, nodes: list, ctx: dict, scope: Any = None) -> str:
        out: List[str] = []
        for node in nodes:
            if isinstance(node, tuple) and node[0] == "text":
                out.append(node[1])
            elif isinstance(node, tuple) and node[0] == "expr":
                out.append(_stringify(_eval_expr(node[1], ctx, scope, self.defines, self._render_nodes)))
            elif isinstance(node, dict):
                t = node["type"]
                if t == "define":
                    continue  # define 在此不产出
                elif t == "if":
                    cond = _truthy(_eval_expr(node["expr"], ctx, scope, self.defines, self._render_nodes))
                    branch = node["body"] if cond else node["orelse"]
                    out.append(self._render_nodes(branch, ctx, scope))
                elif t == "with":
                    v = _eval_expr(node["expr"], ctx, scope, self.defines, self._render_nodes)
                    if _truthy(v):
                        out.append(self._render_nodes(node["body"], ctx, v if isinstance(v, dict) else ctx))
                    else:
                        out.append(self._render_nodes(node["orelse"], ctx, scope))
                elif t == "range":
                    v = _eval_expr(node["expr"], ctx, scope, self.defines, self._render_nodes)
                    items = list(v.values()) if isinstance(v, dict) else (list(v) if isinstance(v, list) else [])
                    for it in items:
                        # . 绑定到当前元素（dict/scalar 都直接绑，根键仍可从 ctx 解析）
                        out.append(self._render_nodes(node["body"], ctx, it))
        return "".join(out)

    def render(self, text: str, ctx: dict) -> str:
        tokens = _tokenize(text)
        _apply_trim(tokens)
        tree, extra = _build_tree(tokens)
        # 把本文件内 define 收集进 engine.defines（合并到全局）
        self.defines.update(extra)
        return self._render_nodes(tree, ctx)


def render_text(text: str, ctx: dict, defines: Optional[Dict[str, list]] = None) -> str:
    """便捷函数：单文件渲染。注意 define 只在本次调用内可见。"""
    return Engine(defines).render(text, ctx)
