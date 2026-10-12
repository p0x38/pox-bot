from pathlib import Path

import pytest

from poxbot.core.resources import (
    FilesystemResolver,
    ResourceAddress,
    ResourceManager,
    ResourcePathError,
    ResourcePermissionError,
    ResourceSchemeAlreadyRegisteredError,
)


@pytest.mark.parametrize(
    ("value", "scheme", "parts"),
    [
        ("assets:locales/en_US.json", "assets", ("locales", "en_US.json")),
        ("MY_PLUGIN:locales/custom.json", "my_plugin", ("locales", "custom.json")),
        ("userdata:cache/state.json", "userdata", ("cache", "state.json")),
    ],
)
def test_parse_resource_address(
    value: str,
    scheme: str,
    parts: tuple[str, ...],
) -> None:
    address = ResourceAddress.parse(value)

    assert address.scheme == scheme
    assert address.parts == parts


@pytest.mark.parametrize(
    "value",
    [
        "assets:",
        "assets:/absolute.json",
        "assets:../secret.json",
        "assets:locales/../../secret.json",
        r"assets:locales\..\secret.json",
        "assets:locales//en.json",
        "assets:./en.json",
        "assets:file\x00.json",
        "assets:drive:C:/file.json",
    ],
)
def test_reject_invalid_resource_addresses(value: str) -> None:
    with pytest.raises(ResourcePathError):
        ResourceAddress.parse(value)


def test_read_resource_beneath_registered_root(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "message.txt").write_text("hello", encoding="utf-8")

    manager = ResourceManager()
    manager.register("assets", FilesystemResolver(assets, writable=False))

    assert manager.read_text("assets:message.txt") == "hello"


def test_write_resource_beneath_userdata_root(tmp_path: Path) -> None:
    user_data = tmp_path / "userdata"
    manager = ResourceManager()
    manager.register(
        "userdata",
        FilesystemResolver(user_data, writable=True),
    )

    manager.write_text("userdata:cache/state.json", '{"ready": true}')

    assert (user_data / "cache" / "state.json").read_text(
        encoding="utf-8",
    ) == '{"ready": true}'


def test_read_only_scheme_rejects_writes(tmp_path: Path) -> None:
    manager = ResourceManager()
    manager.register(
        "assets",
        FilesystemResolver(tmp_path, writable=False),
    )

    with pytest.raises(ResourcePermissionError):
        manager.resolve_path("assets:config.json", write=True)


def test_duplicate_scheme_registration_is_rejected(tmp_path: Path) -> None:
    manager = ResourceManager()
    manager.register("assets", FilesystemResolver(tmp_path))

    with pytest.raises(ResourceSchemeAlreadyRegisteredError):
        manager.register("ASSETS", FilesystemResolver(tmp_path))


def test_symlink_cannot_escape_registered_root(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    outside = tmp_path / "outside"
    assets.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    try:
        (assets / "external").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    manager = ResourceManager()
    manager.register("assets", FilesystemResolver(assets))

    with pytest.raises(ResourcePathError):
        manager.resolve_path("assets:external/secret.txt")
