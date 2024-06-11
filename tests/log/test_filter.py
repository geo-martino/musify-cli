import logging

from musify_cli.log.filter import format_full_func_name, LogFileFilter


###########################################################################
## Logging formatters/filters
###########################################################################
def test_format_func_name():
    record = logging.LogRecord(
        name="this.is.a.short",
        level=logging.INFO,
        pathname=__name__,
        lineno=10,
        msg=None,
        args=None,
        exc_info=None,
        func="path",
    )
    format_full_func_name(record=record, width=20)
    assert record.funcName == "this.is.a.short.path"

    record.name = "this.is.quite.a.long"
    record.funcName = "path"
    format_full_func_name(record=record, width=20)
    assert record.funcName == "t.i.q.a.long.path"

    record.name = "this.path.has.a.ClassName"
    record.funcName = "in_it"
    format_full_func_name(record=record, width=20)
    assert record.funcName == "t.p.h.a.CN.in_it"


def test_file_filter():
    log_filter = LogFileFilter(name="test")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__name__,
        lineno=10,
        msg=None,
        args=None,
        exc_info=None,
        func="function_name"
    )

    record.msg = "normal message"
    log_filter.filter(record)
    assert record.msg == "normal message"

    # noinspection SpellCheckingInspection
    record.msg = "\33[91;1mcolour \33[94;0mmessage\33[0m"
    log_filter.filter(record)
    assert record.msg == "colour message"
