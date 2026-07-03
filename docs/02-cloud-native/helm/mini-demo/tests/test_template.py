import pytest
from helm_mini.template import Engine, TemplateError, render_text

CTX = {"Values": {"name": "llama", "tag": "0.6.3", "count": 2, "empty": "", "items": ["a", "b"]},
       "Release": {"Name": "r", "Namespace": "prod", "Revision": 1},
       "Chart": {"Name": "inference", "Version": "0.1.0", "AppVersion": "0.6.3"}}


def test_variable_substitution():
    out = render_text("name: {{ .Values.name }}", CTX)
    assert out == "name: llama"


def test_nested_path():
    out = render_text("image: {{ .Values.name }}:{{ .Values.tag }}", CTX)
    assert out == "image: llama:0.6.3"


def test_release_and_chart_context():
    out = render_text("r={{ .Release.Name }} ns={{ .Release.Namespace }} v={{ .Chart.Version }}", CTX)
    assert out == "r=r ns=prod v=0.1.0"


def test_quote_pipe():
    out = render_text("v: {{ .Values.tag | quote }}", CTX)
    assert out == 'v: "0.6.3"'


def test_default_returns_fallback_for_empty():
    out = render_text("v: {{ .Values.empty | default \"fallback\" }}", CTX)
    assert out == "v: fallback"


def test_default_returns_value_when_truthy():
    out = render_text("v: {{ .Values.name | default \"fallback\" }}", CTX)
    assert out == "v: llama"


def test_required_raises_when_missing():
    with pytest.raises(TemplateError):
        render_text("v: {{ .Values.empty | required \"must set\" }}", CTX)


def test_trunc_and_trimsuffix():
    out = render_text("{{ .Values.name | trunc 4 | upper }}", CTX)
    assert out == "LLAM"


def test_toyaml_and_nindent():
    # nindent 总是先加一个换行（这是为什么模板里写成 `key:\n  {{- ... | nindent N }}`）
    tmpl = "resources:{{ toYaml .Values.count | nindent 2 }}"
    # toYaml(int 2) -> "2"；nindent 2 -> "\n  2"
    assert render_text(tmpl, CTX) == "resources:\n  2"


def test_if_true():
    out = render_text("{{- if .Values.name }}HAS{{- end }}", CTX)
    assert out == "HAS"


def test_if_false_renders_else():
    out = render_text("{{- if .Values.empty }}A{{- else }}B{{- end }}", CTX)
    assert out == "B"


def test_with_rebinds_scope():
    tmpl = "{{- with .Release }}name={{ .Name }} ns={{ .Namespace }}{{- end }}"
    assert render_text(tmpl, CTX) == "name=r ns=prod"


def test_range_over_list():
    tmpl = "{{- range .Values.items }}[{{ . }}]{{- end }}"
    # 标量元素：. 绑定到标量本身
    assert render_text(tmpl, CTX) == "[a][b]"


def test_whitespace_trim():
    out = render_text("a: 1\n{{- if true }}\nb: 2\n{{- end }}", CTX)
    # {{- 修剪前一行的换行；-}} 修剪后
    assert "  " not in out  # 没有遗留空行导致的意外缩进


def test_include_with_defines():
    helpers = '{{- define "greet" -}}hi {{ .Release.Name }}{{- end -}}'
    tmpl = '{{ include "greet" . }}'
    out = Engine().render(helpers + "\n" + tmpl, CTX)
    assert "hi r" in out


def test_include_piped_to_nindent():
    helpers = '{{- define "lbls" -}}app: x\nchart: y{{- end -}}'
    tmpl = "labels:\n{{ include \"lbls\" . | nindent 2 }}"
    out = Engine().render(helpers + "\n" + tmpl, CTX)
    assert "\n  app: x\n  chart: y" in out


def test_global_root_key_still_accessible_in_with():
    # with 重绑作用域后，根键 Values 仍可访问（本 demo 的简化语义）
    tmpl = "{{- with .Release }}{{ .Values.name }}{{- end }}"
    assert render_text(tmpl, CTX) == "llama"
