# -*- coding: utf-8 -*-
"""单独验证 hub.pyw 里的更新检查函数（不启动界面）。"""
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location(
    "hub", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hub.pyw"))
hub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub)

print("curl:", hub.CURL, os.path.exists(hub.CURL))
for app in hub.APPS:
    latest = None
    try:
        if app["key"] == "maa":
            body = hub.http_get(
                "https://api.maa.plus/MaaAssistantArknights/api/version/stable.json", 8)
            latest = json.loads(body.decode("utf-8", "ignore")).get("version")
        if not latest:
            latest = hub.github_latest_tag(app["release"], timeout=10)
    except Exception as exc:
        print(f"  {app['script']}: check failed -> {type(exc).__name__}: {exc}")
    print(f"{app['script']}: local={app['fallback_version']} latest={latest} "
          f"update={hub.is_newer(latest, app['fallback_version']) if latest else '-'}")
