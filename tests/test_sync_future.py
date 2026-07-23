import pytest

from graphql_sync_dataloaders import SyncFuture, InvalidStateError


def test_sync_future():

    f = SyncFuture()
    assert not f.done()
    with pytest.raises(InvalidStateError):
        f.result()
    f.set_result(42)
    assert f.result() == 42
    assert f.done()


def test_chaining():
    f = SyncFuture()
    f2 = f.then(lambda x: x * 2)
    f3 = f2.then(lambda x: f"{x}")

    f.set_result(1)

    assert f.done()
    assert f2.done()
    assert f3.done()

    assert f.result() == 1
    assert f2.result() == 2
    assert f3.result() == "2"


def test_nested_chaining():
    f = SyncFuture()
    f2 = SyncFuture()
    f3 = f.then(lambda _: f2).then(lambda x: f"{x}")

    f.set_result(1)

    assert f.done()
    assert not f2.done()
    assert not f3.done()

    f2.set_result(2)

    assert f.done()
    assert f2.done()
    assert f3.done()

    assert f.result() == 1
    assert f2.result() == 2
    assert f3.result() == "2"


def test_resolving_with_already_finished_future_propagates_value():
    """A callback may return a future that has already resolved (e.g. a cache
    hit whose batch already dispatched). Chaining onto such a future must adopt
    its value rather than treating it as still pending."""
    inner = SyncFuture()
    inner.set_result(42)
    assert inner.done()

    outer = SyncFuture()
    chained = outer.then(lambda _: inner)
    outer.set_result("go")

    assert chained.done()
    assert chained.result() == 42


def test_resolving_with_already_finished_future_propagates_exception():
    """When a callback returns an already-finished future that failed, the
    chained future must adopt that exception instead of raising an
    InvalidStateError while trying to register a callback on it."""
    inner = SyncFuture()
    inner.set_exception(ValueError("boom"))
    assert inner.done()

    outer = SyncFuture()
    chained = outer.then(lambda _: inner)
    outer.set_result("go")

    assert chained.done()
    with pytest.raises(ValueError, match="boom"):
        chained.result()
