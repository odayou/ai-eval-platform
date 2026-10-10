"""自定义响应解析器插件加载器。

插件目录：backend/custom_parsers/，每个 ``*.py`` 文件（下划线开头除外）
视为一个解析器，解析器名称即文件名（不含扩展名）。

模块需提供函数::

    def parse(raw_text: str, parsed_response: Any, extracted: dict | None = None) -> dict[str, Any] | Any

参数说明：

- ``raw_text``：接口原始响应文本（截断到 20000 字符）
- ``parsed_response``：JSON 解析成功后的对象，解析失败时为 ``None``
- ``extracted``：按路径映射（response_mapping）已抽取的字段 dict，可在此基础上加工

返回值约定：

- 返回 ``dict`` 时，其中的键值对会合并覆盖 ``extracted``（``None`` 值会被忽略），
  自定义键（如 ``demandType``）会合并进评测行数据，可在自定义 Judge Prompt 中引用；
- 返回其他类型时，视为 ``response`` 字段内容。

注意：解析器是本机执行的任意 Python 代码，平台默认面向可信内部用户，
请勿加载来源不明的插件。
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

PARSER_DIR = Path(__file__).resolve().parents[2] / "custom_parsers"

PARSER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PARSER_TEMPLATE = '''"""解析器说明（第一行会显示在下拉列表中）。"""

from app.core.parser_utils import parse_key_value, pick_content


def parse(raw_text: str, parsed_response, extracted: dict | None = None):
    """把响应解析为字段字典。返回 dict 时合并覆盖 extracted；平台会自动丢弃畸形键。

    - raw_text: 接口原始响应文本
    - parsed_response: JSON 解析成功后的对象（可能为 None）
    - extracted: 路径映射已抽取的字段
    """
    # 通用能力：从原始响应 / 结构化响应 / 已抽取字段中定位模型回答文本
    text = pick_content(raw_text, parsed_response, extracted)

    # TODO: 只写你的加工逻辑即可，例如按「key：value」切分
    return parse_key_value(text)
'''

_cache: dict[str, tuple[float, Callable[..., Any]]] = {}
_lock = threading.Lock()


def _load_parser_file(path: Path) -> Callable[..., Any] | None:
    try:
        spec = importlib.util.spec_from_file_location(f"custom_parsers.{path.stem}", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(spec.name, module)
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("加载自定义解析器失败: %s", path)
        return None

    func = getattr(module, "parse", None)
    if not callable(func):
        logger.warning("自定义解析器缺少 parse 函数: %s", path)
        return None
    return func


def get_parser(name: str) -> Callable[..., Any] | None:
    """按名称获取解析器函数，带 mtime 缓存（开发时改动文件即时生效）。"""
    if not name or not PARSER_DIR.is_dir():
        return None
    path = PARSER_DIR / f"{name}.py"
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    with _lock:
        cached = _cache.get(name)
        if cached and cached[0] == mtime:
            return cached[1]
    func = _load_parser_file(path)
    if func is not None:
        with _lock:
            _cache[name] = (mtime, func)
    return func


def list_parsers() -> list[dict[str, str]]:
    """返回可用解析器列表: [{name, description}]，description 取 parse 函数 docstring 首行。"""
    if not PARSER_DIR.is_dir():
        return []
    parsers: list[dict[str, str]] = []
    for path in sorted(PARSER_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        func = _load_parser_file(path)
        if func is None:
            continue
        doc = inspect.getdoc(func) or ""
        description = doc.strip().splitlines()[0] if doc.strip() else ""
        parsers.append({"name": path.stem, "description": description})
    return parsers


def _parser_path(name: str) -> Path:
    if not PARSER_NAME_RE.match(name or ""):
        raise ValueError("解析器名称只能包含字母、数字和下划线，且以字母或下划线开头")
    return PARSER_DIR / f"{name}.py"


def read_parser_code(name: str) -> str | None:
    """返回解析器源码，不存在时返回 None。"""
    try:
        path = _parser_path(name)
    except ValueError:
        raise
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def save_parser(name: str, code: str, overwrite: bool = False) -> Path:
    """把解析器源码写入插件目录；默认拒绝覆盖已存在的解析器。"""
    path = _parser_path(name)
    if path.exists() and not overwrite:
        raise FileExistsError(f"解析器已存在: {name}")
    PARSER_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    with _lock:
        _cache.pop(name, None)
    return path


def delete_parser(name: str) -> None:
    """删除解析器文件并清除缓存。"""
    path = _parser_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"解析器不存在: {name}")
    path.unlink()
    with _lock:
        _cache.pop(name, None)


def run_parser_code(
    code: str,
    raw_text: str,
    parsed_response: Any = None,
    extracted: dict[str, Any] | None = None,
) -> Any:
    """在独立命名空间中执行解析器源码（用于保存前的在线试解析）。"""
    # 让草稿代码里的 `from app.core.parser_utils import ...` 可用
    backend_root = str(PARSER_DIR.parent)
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    namespace: dict[str, Any] = {"__name__": "custom_parser_draft"}
    try:
        from app.core import parser_utils  # noqa: PLC0415

        namespace.update(
            {
                "FIELD_KEY_RE": parser_utils.FIELD_KEY_RE,
                "get_path": parser_utils.get_path,
                "strip_code_fences": parser_utils.strip_code_fences,
                "content_from_json_text": parser_utils.content_from_json_text,
                "pick_content": parser_utils.pick_content,
                "parse_key_value": parser_utils.parse_key_value,
                "filter_field_keys": parser_utils.filter_field_keys,
            }
        )
    except Exception:  # pragma: no cover - 兜底，正常导入不会失败
        logger.exception("预置解析器通用工具失败")
    exec(compile(code, "<custom_parser_draft>", "exec"), namespace)  # noqa: S102
    func = namespace.get("parse")
    if not callable(func):
        raise ValueError("解析器代码必须定义 parse 函数")
    return func(raw_text or "", parsed_response, dict(extracted or {}))
