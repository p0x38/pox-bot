from pathlib import Path

import pytest

from poxbot.core.resources import (
    FilesystemResolver,
    ResourceAddress,
    ResourceManager,
    ResourcePathError,
    ResourcePermissionError,
    ResourceSchemeAlreadyRegisteredError,
    UnknownResourceSchemeError,
)


def test_resource_address_parses_and_normalizes_scheme() -> None:
    address = ResourceAddress.parse("ASSETS:locales/en/command.json")

    assert address.scheme == "assets"
    assert address.parts == ("locales", "en", "command.json")
    assert str(address) == "assets:locales/en/command.json"


@pytest.mark.parametrize(
    "value",
    [
        "assets",
        "assets:",
        "assets:/absolute/path",
        "assets:../outside",
        "assets:folder/../outside",
        "assets:folder//file",
        "assets:folder/./file",
        "1assets:file",
        "assets:folder:name",
    ],
)
def test_resource_address_rejects_invalid_paths(value: str) -> None:
    with pytest.raises(ResourcePathError):
        ResourceAddress.parse(value)


def test_resource_manager_reads_and_writes_registered_resources(
    tmp_path: Path,
) -> None:
    manager = ResourceManager()
    manager.register("assets", FilesystemResolver(tmp_path, writable=True))

    assert manager.write_text("assets:locales/en.json", '{"hello": "world"}') > 0
    assert manager.read_text("assets:locales/en.json") == '{"hello": "world"}'
    assert manager.exists("assets:locales/en.json") is True

    payload = b"\x00\x01\x02"
    manager.write_bytes("assets:data/payload.bin", payload)

    assert manager.read_bytes("assets:data/payload.bin") == payload


def test_read_only_resolver_rejects_writes(tmp_path: Path) -> None:
    manager = ResourceManager()
    manager.register("assets", FilesystemResolver(tmp_path))

    with pytest.raises(ResourcePermissionError):
        manager.write_text("assets:file.txt", "data")


def test_manager_rejects_duplicate_scheme_unless_replaced(
    tmp_path: Path,
) -> None:
    manager = ResourceManager()
    first = FilesystemResolver(tmp_path / "first")
    second = FilesystemResolver(tmp_path / "second", writable=True)

    manager.register("assets", first)

    with pytest.raises(ResourceSchemeAlreadyRegisteredError):
        manager.register("ASSETS", second)

    manager.register("assets", second, replace=True)

    assert manager.resolve_path("assets:file.txt") == (
        tmp_path / "second" / "file.txt"
    ).resolve()


def test_manager_reports_unknown_scheme() -> None:
    manager = ResourceManager()

    with pytest.raises(UnknownResourceSchemeError):
        manager.resolve_path("missing:file.txt")


def test_filesystem_resolver_prevents_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not available in this environment.")

    resolver = FilesystemResolver(root)

    with pytest.raises(ResourcePathError):
        resolver.resolve_path(ResourceAddress.parse("assets:linked/secret.txt"))
