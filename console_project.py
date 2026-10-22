"""Local and portable project persistence for console-pack source projects."""

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from console_pack import ASSET_TYPES, CONSOLE_SLUGS, ConsolePackError, normalize_console_state, validate_pack_name


PROJECT_TYPE = "tico-console-pack-project"
PROJECT_VERSION = "1.0"
LOCAL_EXTENSION = ".tcp"
PORTABLE_EXTENSION = ".tcpz"
_MAX_MANIFEST_SIZE = 1024 * 1024
_MAX_PORTABLE_FILES = 1 + len(CONSOLE_SLUGS) * len(ASSET_TYPES)
_MAX_PORTABLE_UNCOMPRESSED = 512 * 1024 * 1024


class ConsoleProjectError(ConsolePackError):
    """Raised when a console-pack project is invalid or unsafe."""


def _project_document(pack_name, console_state):
    return {
        "project_type": PROJECT_TYPE,
        "version": PROJECT_VERSION,
        "pack_name": validate_pack_name(pack_name),
        "consoles": normalize_console_state(console_state),
    }


def _read_project_document(raw):
    if not isinstance(raw, dict):
        raise ConsoleProjectError("The console project must contain a JSON object.")
    if raw.get("project_type") != PROJECT_TYPE:
        raise ConsoleProjectError("This is not a TICO Console Pack project.")
    if raw.get("version") != PROJECT_VERSION:
        raise ConsoleProjectError("Unsupported console project version: {0}".format(raw.get("version")))
    try:
        return _project_document(raw.get("pack_name", ""), raw.get("consoles", {}))
    except ConsolePackError as error:
        raise ConsoleProjectError(str(error)) from error


def _atomic_write_json(filepath, document):
    target = Path(filepath).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".{0}-".format(target.name), suffix=".tmp", dir=str(target.parent)
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(str(temporary), str(target))
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def _asset_extension(asset_type, source):
    if asset_type == "symbol":
        return ".svg"
    suffix = Path(source).suffix.lower()
    return suffix if suffix else ".img"


def _portable_asset_name(slug, asset_type, source):
    return PurePosixPath("assets") / slug / (asset_type + _asset_extension(asset_type, source))


def _validate_asset_sources(state):
    missing = []
    for slug, entry in state.items():
        for asset_type, raw_path in entry["assets"].items():
            source = Path(raw_path).expanduser()
            if not source.is_file():
                missing.append("{0}: {1}".format(slug, asset_type))
    if missing:
        raise ConsoleProjectError("Missing source assets: {0}".format(", ".join(missing)))


def _safe_archive_members(archive):
    members = archive.infolist()
    if len(members) > _MAX_PORTABLE_FILES:
        raise ConsoleProjectError("Portable project contains too many files.")
    total_size = 0
    seen = set()
    for info in members:
        path = PurePosixPath(info.filename)
        if info.is_dir():
            continue
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ConsoleProjectError("Portable project contains an unsafe path.")
        normalized = path.as_posix()
        if normalized in seen:
            raise ConsoleProjectError("Portable project contains duplicate files.")
        seen.add(normalized)
        total_size += info.file_size
        if total_size > _MAX_PORTABLE_UNCOMPRESSED:
            raise ConsoleProjectError("Portable project is too large.")
    return members


class ConsoleProjectManager:
    """Read and write local ``.tcp`` and portable ``.tcpz`` projects."""

    @classmethod
    def save_local(cls, filepath, pack_name, console_state):
        return _atomic_write_json(filepath, _project_document(pack_name, console_state))

    @classmethod
    def load_local(cls, filepath):
        source = Path(filepath).expanduser()
        try:
            if source.stat().st_size > _MAX_MANIFEST_SIZE:
                raise ConsoleProjectError("Console project file is too large.")
            raw = json.loads(source.read_text(encoding="utf-8"))
        except ConsoleProjectError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ConsoleProjectError("Could not read console project: {0}".format(error)) from error
        return _read_project_document(raw)

    @staticmethod
    def missing_assets(console_state):
        missing = []
        state = normalize_console_state(console_state)
        for slug, entry in state.items():
            for asset_type, raw_path in entry["assets"].items():
                if not Path(raw_path).expanduser().is_file():
                    missing.append("{0}: {1}".format(slug, asset_type))
        return missing

    @classmethod
    def export_portable(cls, filepath, pack_name, console_state):
        document = _project_document(pack_name, console_state)
        state = document["consoles"]
        _validate_asset_sources(state)

        portable_state = {}
        asset_sources = []
        for slug, entry in state.items():
            portable_entry = {"assets": {}, "colors": dict(entry["colors"])}
            for asset_type, source in entry["assets"].items():
                archive_path = _portable_asset_name(slug, asset_type, source).as_posix()
                portable_entry["assets"][asset_type] = archive_path
                asset_sources.append((archive_path, Path(source).expanduser()))
            portable_state[slug] = portable_entry

        portable_document = dict(document)
        portable_document["consoles"] = portable_state
        target = Path(filepath).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".{0}-".format(target.name), suffix=".tmp", dir=str(target.parent)
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(str(temporary), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                manifest = json.dumps(portable_document, indent=2, ensure_ascii=False) + "\n"
                archive.writestr("project.json", manifest.encode("utf-8"))
                for archive_path, source in asset_sources:
                    archive.write(str(source), archive_path)
            os.replace(str(temporary), str(target))
        finally:
            if temporary.exists():
                temporary.unlink()
        return target

    @classmethod
    def import_portable(cls, filepath):
        source = Path(filepath).expanduser()
        temporary_root = Path(tempfile.mkdtemp(prefix="tico-console-project-"))
        try:
            with zipfile.ZipFile(str(source), "r") as archive:
                members = _safe_archive_members(archive)
                names = {info.filename for info in members if not info.is_dir()}
                if "project.json" not in names:
                    raise ConsoleProjectError("Portable project is missing project.json.")
                manifest_info = archive.getinfo("project.json")
                if manifest_info.file_size > _MAX_MANIFEST_SIZE:
                    raise ConsoleProjectError("Portable project manifest is too large.")
                try:
                    raw = json.loads(archive.read(manifest_info).decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as error:
                    raise ConsoleProjectError("Portable project manifest is invalid.") from error
                document = _read_project_document(raw)

                resolved_state = {}
                for slug, entry in document["consoles"].items():
                    resolved_entry = {"assets": {}, "colors": dict(entry["colors"])}
                    for asset_type, archive_name in entry["assets"].items():
                        path = PurePosixPath(archive_name)
                        expected = _portable_asset_name(slug, asset_type, archive_name)
                        if path.as_posix() != expected.as_posix() or path.as_posix() not in names:
                            raise ConsoleProjectError(
                                "Portable project has an invalid asset reference for {0}: {1}.".format(
                                    slug, asset_type
                                )
                            )
                        target = temporary_root.joinpath(*path.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(path.as_posix()) as source_file, target.open("wb") as target_file:
                            shutil.copyfileobj(source_file, target_file)
                        resolved_entry["assets"][asset_type] = str(target)
                    resolved_state[slug] = resolved_entry

            return {
                "pack_name": document["pack_name"],
                "consoles": resolved_state,
                "tmp_dir": str(temporary_root),
            }
        except Exception:
            shutil.rmtree(str(temporary_root), ignore_errors=True)
            raise

    @classmethod
    def save_imported_as_local(cls, filepath, pack_name, console_state):
        """Materialize temporary portable assets beside a new local project."""
        project_path = Path(filepath).expanduser()
        project_path.parent.mkdir(parents=True, exist_ok=True)
        document = _project_document(pack_name, console_state)
        state = document["consoles"]
        _validate_asset_sources(state)
        assets_target = project_path.parent / (project_path.stem + "_assets")
        stage = Path(tempfile.mkdtemp(prefix=".{0}-assets-".format(project_path.stem), dir=str(project_path.parent)))
        backup = None
        try:
            local_state = {}
            for slug, entry in state.items():
                local_entry = {"assets": {}, "colors": dict(entry["colors"])}
                for asset_type, source in entry["assets"].items():
                    relative = Path(slug) / (asset_type + _asset_extension(asset_type, source))
                    target = stage / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(source), str(target))
                    local_entry["assets"][asset_type] = str(assets_target / relative)
                local_state[slug] = local_entry

            assets_installed = False
            try:
                if assets_target.exists():
                    backup = Path(tempfile.mkdtemp(
                        prefix=".{0}-backup-".format(project_path.stem), dir=str(project_path.parent)
                    ))
                    backup.rmdir()
                    os.replace(str(assets_target), str(backup))
                os.replace(str(stage), str(assets_target))
                assets_installed = True
                cls.save_local(project_path, pack_name, local_state)
            except Exception:
                if assets_installed and assets_target.exists():
                    shutil.rmtree(str(assets_target), ignore_errors=True)
                if backup is not None and backup.exists() and not assets_target.exists():
                    os.replace(str(backup), str(assets_target))
                raise
            if backup is not None:
                shutil.rmtree(str(backup), ignore_errors=True)
            return project_path, local_state
        finally:
            if stage.exists():
                shutil.rmtree(str(stage), ignore_errors=True)
