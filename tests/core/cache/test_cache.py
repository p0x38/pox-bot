from pathlib import Path

from poxbot.core.cache import Cache


def test_memory_cache() -> None:
    with Cache(ttl=120) as cache:
        cache.set('key', 'value')

        assert cache.get('key') == 'value'
        assert cache.get('missing') is None
        assert cache.get_count() == 1


def test_entry_ttl_override() -> None:
    with Cache(ttl=0) as cache:
        cache.set('permanent', 'value', ttl=None)

        assert cache.get('permanent') == 'value'
        assert cache.contains('permanent')


def test_expired_entry() -> None:
    with Cache(ttl=0) as cache:
        cache.set('key', 'value')

        assert cache.get('key') is None
        assert cache.get_count() == 0


def test_lru_eviction() -> None:
    with Cache(max_memory_entries=2) as cache:
        cache.set('first', 1)
        cache.set('second', 2)

        assert cache.get('first') == 1

        cache.set('third', 3)

        assert cache.get('first') == 1
        assert cache.get('second') is None
        assert cache.get('third') == 3


def test_disk_persistence(tmp_path: Path) -> None:
    with Cache(
        ttl=300,
        directory=tmp_path,
        namespace='persistent',
    ) as cache:
        cache.set('answer', {'value': 42})

    with Cache(
        ttl=300,
        directory=tmp_path,
        namespace='persistent',
    ) as cache:
        assert cache.get('answer') == {'value': 42}


def test_namespace_isolation(tmp_path: Path) -> None:
    with Cache(directory=tmp_path, namespace='first') as first:
        first.set('key', 'first')

    with Cache(directory=tmp_path, namespace='second') as second:
        assert second.get('key') is None


def test_temporary_directory_cleanup(tmp_path: Path) -> None:
    with Cache(
        directory=tmp_path,
        temporary=True,
        namespace='temporary',
    ) as cache:
        assert cache.directory is not None
        disk_path = cache.directory

        cache.set('key', 'value')
        assert cache.get('key') == 'value'
        assert disk_path.exists()

    assert not disk_path.exists()


def test_clear_removes_disk_entries(tmp_path: Path) -> None:
    with Cache(
        directory=tmp_path,
        namespace='clear-test',
    ) as cache:
        cache.set('first', 1)
        cache.set('second', 2)

        cache.clear()

        assert cache.get('first') is None
        assert cache.get('second') is None
        assert cache.get_count() == 0
