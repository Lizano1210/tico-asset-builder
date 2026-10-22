import json
import os
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PIL import Image

from gui import SoundpackBuilderApp

from console_project import (
    LOCAL_EXTENSION,
    PORTABLE_EXTENSION,
    ConsoleProjectError,
    ConsoleProjectManager,
)


def make_image(path: Path, color=(20, 40, 60)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (5, 4), color + (255,)).save(path)
    return path


def make_svg(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1z"/></svg>', encoding="utf-8")
    return path


def sample_state(tmp_path):
    return {
        "gba": {
            "assets": {
                "cover": str(make_image(tmp_path / "gba" / "same.png", (10, 20, 30))),
                "symbol": str(make_svg(tmp_path / "gba" / "symbol.svg")),
            },
            "colors": {"color_start": "aabbcc"},
        },
        "nes": {
            "assets": {
                "cover": str(make_image(tmp_path / "nes" / "same.png", (90, 80, 70))),
            },
            "colors": {"color_end_dark": "123456"},
        },
    }


def test_extensions_are_distinct_from_soundpack_projects():
    assert LOCAL_EXTENSION == ".tcp"
    assert PORTABLE_EXTENSION == ".tcpz"


def test_local_project_round_trip_preserves_source_paths_and_normalizes_colors(tmp_path):
    state = sample_state(tmp_path)
    project_path = tmp_path / "retro.tcp"

    assert ConsoleProjectManager.save_local(project_path, "retro", state) == project_path
    loaded = ConsoleProjectManager.load_local(project_path)

    assert loaded["pack_name"] == "retro"
    assert loaded["consoles"]["gba"]["assets"]["cover"] == state["gba"]["assets"]["cover"]
    assert loaded["consoles"]["gba"]["colors"]["color_start"] == "AABBCC"
    assert ConsoleProjectManager.missing_assets(loaded["consoles"]) == []
    raw = json.loads(project_path.read_text(encoding="utf-8"))
    assert raw["project_type"] == "tico-console-pack-project"
    assert raw["version"] == "1.0"


def test_local_project_rejects_wrong_type_version_and_invalid_state(tmp_path):
    path = tmp_path / "bad.tcp"
    base = {
        "project_type": "tico-console-pack-project",
        "version": "1.0",
        "pack_name": "valid",
        "consoles": {},
    }
    for change in (
        {"project_type": "soundpack"},
        {"version": "99"},
        {"consoles": {"xbox": {}}},
    ):
        path.write_text(json.dumps({**base, **change}), encoding="utf-8")
        with pytest.raises(ConsoleProjectError):
            ConsoleProjectManager.load_local(path)


def test_missing_assets_are_reported_and_block_portable_export(tmp_path):
    missing = tmp_path / "gone.png"
    state = {"gba": {"assets": {"cover": str(missing)}, "colors": {}}}
    assert ConsoleProjectManager.missing_assets(state) == ["gba: cover"]
    with pytest.raises(ConsoleProjectError, match="Missing source assets"):
        ConsoleProjectManager.export_portable(tmp_path / "bad.tcpz", "bad", state)


def test_portable_round_trip_bundles_assets_without_filename_collisions(tmp_path):
    state = sample_state(tmp_path)
    archive_path = tmp_path / "retro.tcpz"

    assert ConsoleProjectManager.export_portable(archive_path, "retro", state) == archive_path
    with zipfile.ZipFile(archive_path) as archive:
        assert sorted(archive.namelist()) == [
            "assets/gba/cover.png",
            "assets/gba/symbol.svg",
            "assets/nes/cover.png",
            "project.json",
        ]

    imported = ConsoleProjectManager.import_portable(archive_path)
    try:
        assert imported["pack_name"] == "retro"
        gba_cover = Path(imported["consoles"]["gba"]["assets"]["cover"])
        nes_cover = Path(imported["consoles"]["nes"]["assets"]["cover"])
        assert gba_cover.is_file() and nes_cover.is_file()
        assert gba_cover.read_bytes() != nes_cover.read_bytes()
        assert imported["consoles"]["gba"]["colors"]["color_start"] == "AABBCC"
    finally:
        shutil.rmtree(imported["tmp_dir"], ignore_errors=True)


def test_portable_import_rejects_traversal_and_bad_asset_references(tmp_path):
    traversal = tmp_path / "traversal.tcpz"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("project.json", "{}")
        archive.writestr("../escape.png", b"bad")
    with pytest.raises(ConsoleProjectError, match="unsafe path"):
        ConsoleProjectManager.import_portable(traversal)

    bad_reference = tmp_path / "reference.tcpz"
    manifest = {
        "project_type": "tico-console-pack-project",
        "version": "1.0",
        "pack_name": "retro",
        "consoles": {
            "gba": {"assets": {"cover": "assets/nes/cover.png"}, "colors": {}}
        },
    }
    with zipfile.ZipFile(bad_reference, "w") as archive:
        archive.writestr("project.json", json.dumps(manifest))
        archive.writestr("assets/nes/cover.png", b"not relevant")
    with pytest.raises(ConsoleProjectError, match="invalid asset reference"):
        ConsoleProjectManager.import_portable(bad_reference)


def test_imported_portable_can_be_saved_as_durable_local_project(tmp_path):
    source_state = sample_state(tmp_path / "sources")
    portable = ConsoleProjectManager.export_portable(
        tmp_path / "shared.tcpz", "shared", source_state
    )
    imported = ConsoleProjectManager.import_portable(portable)
    imported_tmp = Path(imported["tmp_dir"])
    project_path = tmp_path / "local" / "shared.tcp"
    project_path.parent.mkdir()

    saved_path, local_state = ConsoleProjectManager.save_imported_as_local(
        project_path, imported["pack_name"], imported["consoles"]
    )
    shutil.rmtree(imported_tmp)

    assert saved_path == project_path
    loaded = ConsoleProjectManager.load_local(project_path)
    assert loaded["consoles"] == local_state
    assert ConsoleProjectManager.missing_assets(loaded["consoles"]) == []
    assert Path(loaded["consoles"]["gba"]["assets"]["cover"]).is_file()
    assert Path(loaded["consoles"]["nes"]["assets"]["cover"]).is_file()


def test_imported_local_overwrite_install_failure_restores_previous_assets(tmp_path, monkeypatch):
    source_state = sample_state(tmp_path / "first-sources")
    project_path = tmp_path / "local" / "shared.tcp"
    project_path.parent.mkdir()
    ConsoleProjectManager.save_imported_as_local(project_path, "shared", source_state)
    previous_project = project_path.read_bytes()
    previous_cover = (project_path.parent / "shared_assets/gba/cover.png").read_bytes()

    replacement_state = sample_state(tmp_path / "replacement-sources")
    real_replace = os.replace

    def fail_stage_install(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path.name.startswith(".shared-assets-") and destination_path.name == "shared_assets":
            raise OSError("injected asset install failure")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_stage_install)
    with pytest.raises(OSError, match="injected asset install failure"):
        ConsoleProjectManager.save_imported_as_local(
            project_path, "shared", replacement_state
        )

    assert project_path.read_bytes() == previous_project
    assert (project_path.parent / "shared_assets/gba/cover.png").read_bytes() == previous_cover
    assert not list(project_path.parent.glob(".shared-backup-*"))


def test_file_menu_actions_follow_active_tab():
    noop = lambda: None
    editor = SimpleNamespace(
        new_project=noop,
        open_project=noop,
        save_project=noop,
        export_portable_project=noop,
        import_portable_project=noop,
    )
    host = SimpleNamespace(
        current_language="en",
        console_tab_title="Console Packs",
        console_pack_editor=editor,
        new_project=noop,
        open_project=noop,
        save_project=noop,
        export_portable_project=noop,
        import_portable_project=noop,
    )

    host.tabview = SimpleNamespace(get=lambda: "Soundpacks")
    sound_labels = [item[0] for item in SoundpackBuilderApp._file_menu_actions(cast(Any, host)) if item]
    assert sound_labels == [
        "Soundpack: New Project",
        "Soundpack: Open Project",
        "Soundpack: Save Project",
        "Soundpack: Export Portable Project",
        "Soundpack: Import Portable Project",
    ]

    host.tabview = SimpleNamespace(get=lambda: "Console Packs")
    console_labels = [item[0] for item in SoundpackBuilderApp._file_menu_actions(cast(Any, host)) if item]
    assert console_labels == [
        "Console Pack: New Project",
        "Console Pack: Open Project",
        "Console Pack: Save Project",
        "Console Pack: Export Portable Project",
        "Console Pack: Import Portable Project",
    ]


def test_portable_export_failure_preserves_existing_file(tmp_path, monkeypatch):
    state = sample_state(tmp_path / "sources")
    target = tmp_path / "safe.tcpz"
    target.write_bytes(b"previous")

    def fail_write(*_args, **_kwargs):
        raise OSError("injected portable failure")

    monkeypatch.setattr(zipfile.ZipFile, "write", fail_write)
    with pytest.raises(OSError, match="injected portable failure"):
        ConsoleProjectManager.export_portable(target, "safe", state)
    assert target.read_bytes() == b"previous"
