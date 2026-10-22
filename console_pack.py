"""Console-pack validation and export, independent of the desktop UI.

A ZIP produced by this module contains ``<pack-name>/...``. The user chooses
where to extract it and then places that folder in TICO manually. Transparent
pixels exported to JPEG are composited over white; PNG logos retain alpha.
"""

import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageOps, UnidentifiedImageError


CONSOLE_SLUGS = (
    "3ds", "dc", "fbneo", "gba", "gb", "gbc", "gc", "game-gear",
    "genesis", "mame", "master-system", "n64", "nds", "nes", "pc98",
    "psp", "psx", "saturn", "sega-cd", "snes", "wii",
)
ASSET_TYPES = ("cover", "background", "logo", "symbol")
COLOR_KEYS = ("color_start", "color_end", "color_start_dark", "color_end_dark")
_ASSET_OUTPUT = {
    "cover": ("covers", ".jpg"),
    "background": ("backgrounds", ".jpg"),
    "logo": ("logos", ".png"),
    "symbol": ("symbols", ".svg"),
}
_PACK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


class ConsolePackError(ValueError):
    """Raised when console-pack input cannot be safely exported."""


def validate_pack_name(name):
    value = str(name).strip()
    if not _PACK_NAME_RE.fullmatch(value):
        raise ConsolePackError(
            "Pack name must be 1-64 letters, numbers, hyphens, or underscores "
            "and must start with a letter or number."
        )
    return value


def validate_slug(slug):
    value = str(slug)
    if value not in CONSOLE_SLUGS:
        raise ConsolePackError("Unsupported console slug: {0}".format(value))
    return value


def validate_hex_color(value):
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip()
    if not _HEX_RE.fullmatch(normalized):
        raise ConsolePackError("Colors must contain exactly 6 RGB hex digits without #.")
    return normalized.upper()


def validate_svg(path):
    source = Path(path)
    if not source.is_file():
        raise ConsolePackError("SVG file does not exist: {0}".format(source))
    try:
        root = ElementTree.parse(str(source)).getroot()
    except (ElementTree.ParseError, OSError) as error:
        raise ConsolePackError("Could not parse SVG file {0}: {1}".format(source, error))
    local_name = root.tag.rsplit("}", 1)[-1].lower()
    if local_name != "svg":
        raise ConsolePackError("SVG root element must be <svg>: {0}".format(source))
    return source


def normalize_console_state(state):
    if state is None:
        return {}
    if not isinstance(state, dict):
        raise ConsolePackError("Console state must be a mapping.")

    normalized = {}
    for slug in CONSOLE_SLUGS:
        if slug not in state:
            continue
        validate_slug(slug)
        raw_entry = state[slug] or {}
        if not isinstance(raw_entry, dict):
            raise ConsolePackError("Configuration for {0} must be a mapping.".format(slug))
        unknown_sections = set(raw_entry) - {"assets", "colors"}
        if unknown_sections:
            raise ConsolePackError("Unknown console fields: {0}".format(", ".join(sorted(unknown_sections))))

        raw_assets = raw_entry.get("assets") or {}
        raw_colors = raw_entry.get("colors") or {}
        if not isinstance(raw_assets, dict) or not isinstance(raw_colors, dict):
            raise ConsolePackError("Assets and colors for {0} must be mappings.".format(slug))
        unknown_assets = set(raw_assets) - set(ASSET_TYPES)
        unknown_colors = set(raw_colors) - set(COLOR_KEYS)
        if unknown_assets:
            raise ConsolePackError("Unknown asset fields: {0}".format(", ".join(sorted(unknown_assets))))
        if unknown_colors:
            raise ConsolePackError("Unknown color fields: {0}".format(", ".join(sorted(unknown_colors))))

        assets = {key: str(raw_assets[key]) for key in ASSET_TYPES if raw_assets.get(key)}
        colors = {}
        for key in COLOR_KEYS:
            color = validate_hex_color(raw_colors.get(key))
            if color:
                colors[key] = color
        if assets or colors:
            normalized[slug] = {"assets": assets, "colors": colors}
    unknown_slugs = set(state) - set(CONSOLE_SLUGS)
    if unknown_slugs:
        raise ConsolePackError("Unsupported console slug: {0}".format(sorted(unknown_slugs)[0]))
    return normalized


def _validate_raster(path):
    source = Path(path)
    if not source.is_file():
        raise ConsolePackError("Image file does not exist: {0}".format(source))
    try:
        with Image.open(str(source)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ConsolePackError("Invalid image file {0}: {1}".format(source, error))
    return source


def _save_jpeg(source, target):
    with Image.open(str(source)) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        image.save(str(target), "JPEG", quality=95, optimize=False, progressive=False)


def _save_png(source, target):
    with Image.open(str(source)) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            image = image.convert("RGBA")
        image.save(str(target), "PNG", optimize=False)


class ConsolePackExporter:
    """Create validated TICO console-pack directories and sharing ZIP files."""

    @classmethod
    def export(cls, destination_folder, pack_name, console_state):
        name = validate_pack_name(pack_name)
        state = normalize_console_state(console_state)
        if not state:
            raise ConsolePackError("A console pack must contain at least one asset or color.")

        # Validate every source before touching an existing exported pack.
        sources = {}
        for slug, entry in state.items():
            for asset_type, raw_path in entry["assets"].items():
                if asset_type == "symbol":
                    sources[(slug, asset_type)] = validate_svg(raw_path)
                else:
                    sources[(slug, asset_type)] = _validate_raster(raw_path)

        destination = Path(destination_folder).expanduser()
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / name
        stage = Path(tempfile.mkdtemp(prefix=".{0}-".format(name), dir=str(destination)))
        backup = None
        try:
            colors_document = {}
            for slug, entry in state.items():
                for asset_type, source_path in entry["assets"].items():
                    folder, extension = _ASSET_OUTPUT[asset_type]
                    output_dir = stage / folder
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output = output_dir / (slug + extension)
                    if asset_type in ("cover", "background"):
                        _save_jpeg(source_path, output)
                    elif asset_type == "logo":
                        _save_png(source_path, output)
                    else:
                        shutil.copyfile(str(source_path), str(output))
                if entry["colors"]:
                    colors_document[slug] = entry["colors"]

            if colors_document:
                (stage / "colors.json").write_text(
                    json.dumps(colors_document, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

            if target.exists():
                backup = Path(tempfile.mkdtemp(prefix=".{0}-backup-".format(name), dir=str(destination)))
                backup.rmdir()
                os.replace(str(target), str(backup))
            os.replace(str(stage), str(target))
            if backup is not None:
                shutil.rmtree(str(backup), ignore_errors=True)
            return target
        except Exception:
            if target.exists() and backup is not None and backup.exists():
                shutil.rmtree(str(target), ignore_errors=True)
            if backup is not None and backup.exists() and not target.exists():
                os.replace(str(backup), str(target))
            raise
        finally:
            if stage.exists():
                shutil.rmtree(str(stage), ignore_errors=True)

    @staticmethod
    def create_zip(pack_path):
        pack = Path(pack_path)
        if not pack.is_dir():
            raise ConsolePackError("ZIP source must be an exported console-pack directory.")
        validate_pack_name(pack.name)
        zip_path = pack.parent / (pack.name + ".zip")
        files = sorted(path for path in pack.rglob("*") if path.is_file())
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".{0}-".format(pack.name), suffix=".zip", dir=str(pack.parent)
        )
        os.close(descriptor)
        temporary_zip = Path(temporary_name)
        try:
            with zipfile.ZipFile(
                str(temporary_zip), "w", zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                for path in files:
                    arcname = (Path(pack.name) / path.relative_to(pack)).as_posix()
                    info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
            os.replace(str(temporary_zip), str(zip_path))
        finally:
            if temporary_zip.exists():
                temporary_zip.unlink()
        return zip_path

    @classmethod
    def export_bundle(cls, destination_folder, pack_name, console_state):
        """Export the pack folder and ZIP as one rollback-safe delivery."""
        name = validate_pack_name(pack_name)
        destination = Path(destination_folder).expanduser()
        destination.mkdir(parents=True, exist_ok=True)
        target_pack = destination / name
        target_zip = destination / (name + ".zip")

        with tempfile.TemporaryDirectory(
            prefix=".{0}-bundle-".format(name), dir=str(destination)
        ) as temporary_root:
            temporary_root = Path(temporary_root)
            staged_pack = cls.export(temporary_root, name, console_state)
            staged_zip = cls.create_zip(staged_pack)

            backup_root = Path(tempfile.mkdtemp(
                prefix=".{0}-backup-".format(name), dir=str(destination)
            ))
            backup_pack = backup_root / name
            backup_zip = backup_root / (name + ".zip")
            pack_installed = False
            zip_installed = False
            try:
                if target_pack.exists():
                    os.replace(str(target_pack), str(backup_pack))
                if target_zip.exists():
                    os.replace(str(target_zip), str(backup_zip))

                os.replace(str(staged_pack), str(target_pack))
                pack_installed = True
                os.replace(str(staged_zip), str(target_zip))
                zip_installed = True
            except Exception:
                if zip_installed and target_zip.exists():
                    target_zip.unlink()
                if pack_installed and target_pack.exists():
                    shutil.rmtree(str(target_pack), ignore_errors=True)
                if backup_pack.exists():
                    os.replace(str(backup_pack), str(target_pack))
                if backup_zip.exists():
                    os.replace(str(backup_zip), str(target_zip))
                raise
            finally:
                shutil.rmtree(str(backup_root), ignore_errors=True)

        return target_pack, target_zip
