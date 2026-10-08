"""Access logs never contain query strings (they can hold search text). Fake data only."""

import io
import logging
import logging.config
import sys

import pytest
import uvicorn

import app.__main__ as entry
from app.logs import NoQueryStringFilter, log_config


def _access_record(path: str) -> logging.LogRecord:
    # The same message and arguments uvicorn uses for an access-log line.
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:50000", "GET", path, "1.1", 200),
        None,
    )


def test_query_string_is_removed():
    record = _access_record("/api/local/transactions?q=pharmacy%20copay&limit=5")
    assert NoQueryStringFilter().filter(record)
    message = record.getMessage()
    assert message == '127.0.0.1:50000 - "GET /api/local/transactions HTTP/1.1" 200'
    assert "pharmacy" not in message


def test_line_without_query_is_unchanged():
    record = _access_record("/api/health")
    assert NoQueryStringFilter().filter(record)
    assert record.getMessage() == '127.0.0.1:50000 - "GET /api/health HTTP/1.1" 200'


def test_unexpected_line_with_query_is_dropped():
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, "GET /x?q=secret", None, None
    )
    assert not NoQueryStringFilter().filter(record)


def test_log_config_filters_the_access_logger():
    stream = io.StringIO()
    config = log_config()
    config["handlers"]["access"] = {"class": "logging.StreamHandler", "stream": stream}
    logger = logging.getLogger("uvicorn.access")
    saved = (logger.handlers[:], logger.filters[:], logger.level, logger.propagate)
    try:
        logging.config.dictConfig(config)
        logger.handle(_access_record("/api/local/transactions?q=pharmacy"))
    finally:
        logger.handlers, logger.filters, logger.level, logger.propagate = saved
    assert "/api/local/transactions" in stream.getvalue()
    assert "pharmacy" not in stream.getvalue()


def test_server_starts_with_the_filtered_log_config(data_dir, monkeypatch):
    configs = []
    monkeypatch.setattr(uvicorn.Server, "run", lambda self: configs.append(self.config))
    # `python -m app` with no arguments starts the server (see app/cli.py).
    monkeypatch.setattr(sys, "argv", ["app"])
    with pytest.raises(SystemExit) as exited:
        entry.main()
    assert exited.value.code == 0
    (config,) = configs
    assert config.log_config["loggers"]["uvicorn.access"]["filters"] == ["no_query_string"]
    assert config.proxy_headers is False
