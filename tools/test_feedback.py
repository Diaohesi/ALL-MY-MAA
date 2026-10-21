# -*- coding: utf-8 -*-
"""Offline feedback regression tests: python tools/test_feedback.py."""

import os
import sys
import unittest
from contextlib import ExitStack
from unittest import mock
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import VERSION, feedback  # noqa: E402


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("system", "TestOS"), ("release", "42"),
                            ("machine", "test64"), ("python_version", "3.12.99")):
            self.stack.enter_context(mock.patch.object(feedback.platform, name,
                                                      return_value=value))
        self.stack.enter_context(mock.patch.object(sys, "frozen", False, create=True))
        self.stack.enter_context(mock.patch.dict(os.environ, {
            "USERNAME": "PRIVATE_USER", "COMPUTERNAME": "PRIVATE_HOST",
            "HOME": "C:/PRIVATE_HOME", "TOKEN": "PRIVATE_TOKEN",
        }, clear=True))

    def report(self, **overrides):
        values = dict(kind="Bug", title="中文标题", description="问题详情",
                      steps="第一步\n第二步", expected="预期结果", actual="实际结果",
                      component="启动器")
        values.update(overrides)
        return feedback.build_report(**values)

    def test_report_fields_and_kind_alias(self):
        body = self.report()
        for text in ("# 中文标题", "问题反馈", "问题详情", "第一步\n第二步",
                     "预期结果", "实际结果", "启动器"):
            self.assertIn(text, body)
        for kind in ("Bug", "问题反馈", "功能建议"):
            self.assertIn("功能建议" if kind == "功能建议" else "问题反馈",
                          self.report(kind=kind))
        with self.assertRaises(ValueError):
            self.report(kind="unknown")

    def test_required_fields(self):
        for field in ("title", "description"):
            for value in ("", " \n\t", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        self.report(**{field: value})
        for title in ("", " \n", None):
            with self.assertRaises(ValueError):
                feedback.issue_url(title, "body")

    def test_title_limit(self):
        title = "测" * 151
        self.assertEqual(self.report(title=title).splitlines()[0], "# " + "测" * 150)
        url, included = feedback.issue_url(title, "报告")
        self.assertTrue(included)
        self.assertEqual(parse_qs(urlsplit(url).query)["title"], ["测" * 150])

    def test_unicode_query_round_trip(self):
        title = "中文 空格 &?# + 😀"
        body = "完整正文\n路径不是自动收集：用户填写 &?#=+/% 😀"
        url, included = feedback.issue_url(title, body)
        self.assertTrue(included)
        self.assertTrue(url.isascii())
        self.assertIn("%20", url)
        parts = urlsplit(url)
        self.assertEqual((parts.scheme, parts.netloc, parts.path, parts.fragment),
                         ("https", "github.com", "/Diaohesi/All-My-Maa/issues/new", ""))
        self.assertEqual(parse_qs(parts.query), {"title": [title], "body": [body]})

    def test_oversize_omits_whole_body_and_boundary(self):
        body = "正文😀" * 10000
        url, included = feedback.issue_url("测试", body)
        self.assertFalse(included)
        self.assertLessEqual(len(url), 7500)
        self.assertEqual(parse_qs(urlsplit(url).query), {"title": ["测试"]})
        full_url, _ = feedback.issue_url("测试", "正文")
        self.assertEqual(feedback.issue_url("测试", "正文", len(full_url)),
                         (full_url, True))
        short_url, included = feedback.issue_url("测试", "正文", len(full_url) - 1)
        self.assertFalse(included)
        self.assertNotIn("body=", short_url)
        for limit in (0, -1, 1, True, 7.5):
            with self.assertRaises(ValueError):
                feedback.issue_url("测试", "正文", limit)

    def test_environment_allowlist(self):
        body = self.report()
        self.assertEqual(body.split("## 环境信息\n")[1].splitlines(), [
            "- VERSION: " + VERSION, "- System: TestOS", "- Release: 42",
            "- Machine: test64", "- Python: 3.12.99", "- Frozen: False",
        ])
        with mock.patch.object(sys, "frozen", True):
            self.assertIn("- Frozen: True", self.report())
        for secret in ("PRIVATE_USER", "PRIVATE_HOST", "PRIVATE_HOME", "PRIVATE_TOKEN"):
            self.assertNotIn(secret, body)

    def test_no_automatic_io_network_or_private_diagnostics(self):
        forbidden = AssertionError("Feedback must not access private data or perform I/O")
        with ExitStack() as stack:
            for target in ("builtins.open", "os.getenv", "os.getcwd", "os.getlogin",
                           "getpass.getuser", "platform.node", "platform.uname",
                           "platform.platform", "socket.gethostname",
                           "socket.create_connection", "socket.socket",
                           "urllib.request.urlopen", "webbrowser.open"):
                stack.enter_context(mock.patch(target, side_effect=forbidden))
            stack.enter_context(mock.patch.object(os, "environ", {}))
            body = self.report()
            self.assertTrue(feedback.issue_url("反馈", body)[1])

    def test_environment_opt_out_does_not_collect(self):
        with ExitStack() as stack:
            for name in ("system", "release", "machine", "python_version"):
                stack.enter_context(mock.patch.object(feedback.platform, name,
                    side_effect=AssertionError("Diagnostics disabled")))
            body = self.report(include_environment=False)
        self.assertNotIn("## 环境信息", body)
        self.assertNotIn("VERSION:", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
