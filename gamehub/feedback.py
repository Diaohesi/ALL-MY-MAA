# -*- coding: utf-8 -*-
"""Build opt-in feedback text and URLs without opening a browser or sending data.

Only the small, explicit environment allowlist below is collected. User-entered
text is preserved; callers should let users review it before sharing it.
"""

import platform
import sys
from urllib.parse import quote, urlencode

from . import VERSION


ISSUE_URL = "https://github.com/Diaohesi/All-My-Maa/issues/new"
MAX_TITLE_LENGTH = 150


def _title(title):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("反馈标题不能为空")
    return title.strip()[:MAX_TITLE_LENGTH]


def build_report(kind, title, description, steps, expected, actual, component,
                 include_environment=True):
    """Return reviewable Markdown; never read configuration, logs or user paths.

    ``Bug`` is an alias for ``问题反馈``. Diagnostics are optional and contain
    only the application version, OS name/release, architecture, Python version
    and frozen status. No hostname, username or environment variables are read.
    """
    if kind not in ("Bug", "问题反馈", "功能建议"):
        raise ValueError("不支持的反馈类型")
    title = _title(title)
    if not isinstance(description, str) or not description.strip():
        raise ValueError("反馈描述不能为空")
    kind = "问题反馈" if kind == "Bug" else kind
    sections = [
        "# " + title,
        "## 反馈类型\n" + kind,
        "## 相关组件\n" + (component or "未指定"),
        "## 描述\n" + description.strip(),
        "## 复现步骤\n" + (steps or "未提供"),
        "## 预期行为\n" + (expected or "未提供"),
        "## 实际行为\n" + (actual or "未提供"),
    ]
    if include_environment:
        sections.append("## 环境信息\n" + "\n".join((
            "- VERSION: " + VERSION,
            "- System: " + platform.system(),
            "- Release: " + platform.release(),
            "- Machine: " + platform.machine(),
            "- Python: " + platform.python_version(),
            "- Frozen: " + str(bool(getattr(sys, "frozen", False))),
        )))
    return "\n\n".join(sections) + "\n"


def issue_url(title, body, max_length=7500):
    """Return ``(url, body_included)`` for a manually opened GitHub issue.

    The title is limited to 150 characters. If the complete encoded body will
    not fit, omit it entirely so the UI can copy the full report instead. A
    limit too small even for the title-only URL raises ``ValueError``.
    """
    title = _title(title)
    if not isinstance(body, str):
        raise ValueError("反馈正文必须是文本")
    if isinstance(max_length, bool) or not isinstance(max_length, int) or max_length < 1:
        raise ValueError("URL 长度限制必须是正整数")
    title_url = ISSUE_URL + "?" + urlencode({"title": title}, quote_via=quote)
    if len(title_url) > max_length:
        raise ValueError("URL 长度限制不足以容纳标题")
    full_url = title_url + "&" + urlencode({"body": body}, quote_via=quote)
    if len(full_url) <= max_length:
        return full_url, True
    return title_url, False
