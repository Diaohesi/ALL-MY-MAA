# -*- coding: utf-8 -*-
"""Private, best-effort runtime diagnostics. No configuration/environment collection.

Export is an explicitly requested ZIP of only bounded hub.log + four rotations,
redacted again at export time. It never collects external script logs.
"""
import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import threading
import traceback
import uuid
import zipfile

MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 4
_REDACTED = "[REDACTED]"
_SESSION = uuid.uuid4().hex
_lock = threading.RLock()
_path = None
_handler = None
_old_sys_hook = None
_old_thread_hook = None
_SECRET = re.compile(r"password|passwd|pwd|token|cdk|authorization|cookie|secret|api[_-]?key|credential", re.I)
_HOME = re.compile(r"(?i)([a-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+|/(?:home|Users)/)([^\\/\r\n\"'<>:]+)")
# Redact whole URL query/fragment: credentials can have arbitrary parameter names.
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_ASSIGN = re.compile(r"(?i)(\b(?:[\"']?[\w.-]{0,64}(?:password|passwd|pwd|token|cdk|authorization|cookie|secret|api[_-]?key|credential)[\w.-]{0,64}[\"']?)\s*[:=]\s*)(?:[\"'][^\"'\r\n]*[\"']|[^\s,;}\r\n]+(?:\s+[^\s,;}\r\n]+)?)")
_BEARER = re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=:-]+")
_CLI = re.compile(r"(?i)(--?[\w-]*(?:password|passwd|pwd|token|cdk|authorization|cookie|secret|api-key|credential)[\w-]*\s+)(?:\"[^\"]*\"|'[^']*'|\S+)")


def _text(value):
    def url(match):
        text = match.group(0)
        text = re.sub(r"(https?://)[^/@]+@", r"\1[REDACTED]@", text, flags=re.I)
        text = re.sub(r"[?#].*", "?[REDACTED]", text)
        return text
    if len(value) > 32768:
        return "[oversized text omitted]"
    text = _URL.sub(url, value)
    text = _HOME.sub(lambda m: m.group(1) + _REDACTED, text)
    text = _BEARER.sub(_REDACTED, text)
    text = _CLI.sub(lambda m: m.group(1) + _REDACTED, text)
    return _ASSIGN.sub(lambda m: m.group(1) + _REDACTED, text)


def _redact(value, depth=0, seen=None):
    """Bounded recursive sanitizer; unknown objects are never repr/str dumped."""
    if depth > 10:
        return "[depth limit]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        # Never clip a credential before sanitizing: a missing closing quote
        # could leave its tail outside the assignment match. Omit huge fields.
        return "[oversized text omitted]" if len(value) > 32768 else _text(value)
    if isinstance(value, Path):
        return _text(os.fspath(value))
    seen = set() if seen is None else seen
    if id(value) in seen:
        return "[cycle]"
    seen.add(id(value))
    try:
        if isinstance(value, dict):
            result = {}
            for key, item in list(value.items())[:100]:
                name = key if isinstance(key, str) else "[non-string key]"
                # Never serialize environment or raw configuration containers.
                result[_text(name)] = (_REDACTED if _SECRET.search(name) or
                    name.lower() in ("env", "environ", "environment", "config", "configuration", "settings")
                    else _redact(item, depth + 1, seen))
            return result
        if isinstance(value, (tuple, list, set)):
            return [_redact(item, depth + 1, seen) for item in list(value)[:100]]
        return "[unsupported object]"
    finally:
        seen.discard(id(value))


class _Formatter(logging.Formatter):
    def format(self, record):
        fields = _redact(getattr(record, "event_fields", {}))
        # Do not evaluate arbitrary logging arguments/objects.
        message = record.msg if isinstance(record.msg, str) else "[unsupported message]"
        if record.args:
            message += " " + json.dumps(_redact(record.args), ensure_ascii=False)
        data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).isoformat(),
            "level": record.levelname, "thread": _text(record.threadName),
            "session_id": _SESSION, "logger": _text(record.name),
            "event": _text(message), "fields": fields,
        }
        if record.exc_info:
            # No locals/source lines: source code itself can contain literal secrets.
            exc_type, exc, tb = record.exc_info
            frames = traceback.extract_tb(tb) if tb else []
            rendered = "Traceback (most recent call last):\n" + "".join(
                f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
                for frame in frames)
            rendered += f"{exc_type.__name__}: {exc}"
            data["traceback"] = _text(rendered)
        return json.dumps(data, ensure_ascii=False, allow_nan=False)


class _SafeHandler(RotatingFileHandler):
    def handleError(self, record):
        pass  # Logging is never allowed to crash the application or leak to stderr.

    def emit(self, record):
        try:
            super().emit(record)
        except Exception:
            pass


class _SafeLogger(logging.Logger):
    def _log(self, *args, **kwargs):
        try:
            super()._log(*args, **kwargs)
        except Exception:
            pass


_logger = _SafeLogger("gamehub.runtime", logging.INFO)
_logger.propagate = False
_logger.addHandler(logging.NullHandler())


def get_logger(name="runtime"):
    """Return a non-propagating logger whose formatter enforces redaction."""
    # A shared logger avoids unbounded logger creation from application input.
    return _logger


def log_event(event, **fields):
    try:
        _logger.info(event, extra={"event_fields": fields})
    except Exception:
        pass


def _sys_exception(typ, value, tb):
    try:
        _logger.critical("uncaught_exception", exc_info=(typ, value, tb))
    except Exception:
        pass
    # Do not chain default hooks: they print unredacted traceback data.


def _thread_exception(args):
    _sys_exception(args.exc_type, args.exc_value, args.exc_traceback)


def setup_logging(app_dir):
    """Install logging/hooks, returning the active Path or None on total failure.

    Idempotent until shutdown; each setup after shutdown starts a new session.
    """
    global _path, _handler, _SESSION, _old_sys_hook, _old_thread_hook
    with _lock:
        if _handler is not None:
            return _path
        _SESSION = uuid.uuid4().hex
        candidates = []
        try:
            candidates.append(Path(app_dir) / "logs")
        except Exception:
            pass
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "All-My-Maa" / "logs")
        for directory in candidates:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                candidate = directory / "hub.log"
                handler = _SafeHandler(candidate, maxBytes=MAX_BYTES,
                                       backupCount=BACKUP_COUNT, encoding="utf-8")
                handler.setFormatter(_Formatter())
                _logger.addHandler(handler)
                _handler, _path = handler, candidate
                break
            except Exception:
                continue
        if _old_sys_hook is None:
            _old_sys_hook = sys.excepthook
            sys.excepthook = _sys_exception
        if hasattr(threading, "excepthook") and _old_thread_hook is None:
            _old_thread_hook = threading.excepthook
            threading.excepthook = _thread_exception
        log_event("logging_ready", available=_path is not None)
        return _path


def current_log_path():
    """Active log Path, or None when logging storage is unavailable."""
    return _path


def export_diagnostics(destination):
    """Explicit user action only: write a ZIP, return its Path, raise OSError on failure.

    Max five files, max 2 MiB read per file; no directory traversal/other logs.
    Destination must not overwrite a live runtime log. No automatic export.
    """
    target = Path(destination)
    with _lock:
        if _path is None:
            raise OSError("Runtime log storage is unavailable")
        sources = [_path] + [Path(str(_path) + f".{i}") for i in range(1, BACKUP_COUNT + 1)]
        if target.resolve() in [source.resolve() for source in sources]:
            raise OSError("Cannot overwrite an active runtime log")
        if _handler:
            _handler.flush()
        try:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for source in sources:
                    if not source.is_file() or source.is_symlink():
                        continue
                    with source.open("rb") as stream:
                        text = stream.read(MAX_BYTES).decode("utf-8", "replace")
                    lines = []
                    for line in text.splitlines():
                        # Corrupt/legacy giant lines are not useful diagnostics.
                        if len(line) > 65536:
                            lines.append("[oversized log line omitted]")
                            continue
                        try:
                            lines.append(json.dumps(_redact(json.loads(line)), ensure_ascii=False))
                        except (ValueError, TypeError):
                            lines.append(_text(line))
                    archive.writestr(source.name, "\n".join(lines) + "\n")
        except Exception as exc:
            raise OSError("Unable to export runtime diagnostics") from exc
    log_event("diagnostics_exported", file_count=len(sources))
    return target


def shutdown_logging():
    """Flush/close only our handler and restore hooks if still owned by us."""
    global _handler, _path, _old_sys_hook, _old_thread_hook
    with _lock:
        if sys.excepthook is _sys_exception and _old_sys_hook is not None:
            sys.excepthook = _old_sys_hook
        if getattr(threading, "excepthook", None) is _thread_exception and _old_thread_hook is not None:
            threading.excepthook = _old_thread_hook
        _old_sys_hook = _old_thread_hook = None
        if _handler:
            try:
                _logger.removeHandler(_handler)
                _handler.close()
            except Exception:
                pass
        _handler = _path = None
