import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from console_pack import (
    COLOR_KEYS,
    CONSOLE_SLUGS,
    ConsolePackError,
    ConsolePackExporter,
    normalize_console_state,
    validate_hex_color,
    validate_pack_name,
    validate_slug,
    validate_svg,
)


def make_image(path: Path, mode="RGB", color=(20, 40, 60), size=(7, 5)) -> Path:
    Image.new(mode, size, color).save(path)
    return path


def make_svg(path: Path) -> Path:
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<path d="M0 0h10v10H0z"/></svg>',
        encoding="utf-8",
    )
    return path


def test_contract_constants_and_validation():
    assert CONSOLE_SLUGS == (
        "3ds", "dc", "fbneo", "gba", "gb", "gbc", "gc", "game-gear",
        "genesis", "mame", "master-system", "n64", "nds", "nes", "pc98",
        "psp", "psx", "saturn", "sega-cd", "snes", "wii",
    )
    assert COLOR_KEYS == ("color_start", "color_end", "color_start_dark", "color_end_dark")
    assert validate_pack_name("my-pack") == "my-pack"
    assert validate_slug("game-gear") == "game-gear"
    assert validate_hex_color("a1B2c3") == "A1B2C3"
    assert validate_hex_color("") is None

    for name in ("", "../escape", "a/b", ".", "name with spaces"):
        with pytest.raises(ConsolePackError):
            validate_pack_name(name)
    with pytest.raises(ConsolePackError):
        validate_slug("xbox")
    for value in ("#FFFFFF", "FFF", "GGGGGG", "FFFFFF00"):
        with pytest.raises(ConsolePackError):
            validate_hex_color(value)


def test_normalize_state_drops_empty_values_and_rejects_unknown_fields():
    state = normalize_console_state({
        "gba": {
            "assets": {"cover": "cover.png", "logo": ""},
            "colors": {"color_start": "abcdef", "color_end_dark": None},
        }
    })
    assert state == {
        "gba": {
            "assets": {"cover": "cover.png"},
            "colors": {"color_start": "ABCDEF"},
        }
    }
    with pytest.raises(ConsolePackError):
        normalize_console_state({"gba": {"assets": {"poster": "x.png"}}})


def test_svg_validation_requires_real_parseable_svg(tmp_path):
    valid = make_svg(tmp_path / "symbol.svg")
    assert validate_svg(valid) == valid

    malformed = tmp_path / "bad.svg"
    malformed.write_text("<svg>", encoding="utf-8")
    with pytest.raises(ConsolePackError, match="parse"):
        validate_svg(malformed)

    not_svg = tmp_path / "not.svg"
    not_svg.write_text("<html/>", encoding="utf-8")
    with pytest.raises(ConsolePackError, match="root"):
        validate_svg(not_svg)


def test_partial_pack_converts_rasters_copies_svg_and_writes_colors(tmp_path):
    cover = make_image(tmp_path / "cover.png", size=(11, 9))
    logo = make_image(tmp_path / "logo.jpg", size=(13, 6))
    symbol = make_svg(tmp_path / "symbol.svg")

    pack = ConsolePackExporter.export(
        tmp_path / "out",
        "retro-pack",
        {
            "gba": {
                "assets": {"cover": cover, "logo": logo, "symbol": symbol},
                "colors": {"color_start": "aa00ff", "color_end": "00BB11"},
            }
        },
    )

    assert pack == tmp_path / "out" / "retro-pack"
    assert sorted(p.relative_to(pack).as_posix() for p in pack.rglob("*") if p.is_file()) == [
        "colors.json", "covers/gba.jpg", "logos/gba.png", "symbols/gba.svg"
    ]
    with Image.open(pack / "covers/gba.jpg") as image:
        assert image.format == "JPEG"
        assert image.size == (11, 9)
    with Image.open(pack / "logos/gba.png") as image:
        assert image.format == "PNG"
        assert image.size == (13, 6)
    assert (pack / "symbols/gba.svg").read_bytes() == symbol.read_bytes()
    assert json.loads((pack / "colors.json").read_text(encoding="utf-8")) == {
        "gba": {"color_start": "AA00FF", "color_end": "00BB11"}
    }
    assert (pack / "colors.json").read_text(encoding="utf-8").endswith("\n")


def test_jpeg_alpha_is_composited_on_white_and_png_preserves_alpha(tmp_path):
    transparent = make_image(tmp_path / "alpha.png", mode="RGBA", color=(255, 0, 0, 0), size=(4, 4))
    pack = ConsolePackExporter.export(
        tmp_path / "out",
        "alpha-pack",
        {"nes": {"assets": {"cover": transparent, "logo": transparent}}},
    )

    with Image.open(pack / "covers/nes.jpg") as cover:
        pixel = cover.convert("RGB").getpixel((0, 0))
        assert all(channel >= 250 for channel in pixel)
    with Image.open(pack / "logos/nes.png") as logo:
        assert logo.mode == "RGBA"
        assert logo.getpixel((0, 0))[3] == 0


def test_export_rejects_empty_pack_missing_inputs_and_invalid_images(tmp_path):
    with pytest.raises(ConsolePackError, match="at least one"):
        ConsolePackExporter.export(tmp_path, "empty", {})
    with pytest.raises(ConsolePackError, match="does not exist"):
        ConsolePackExporter.export(
            tmp_path, "missing", {"gba": {"assets": {"cover": tmp_path / "none.png"}}}
        )
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    with pytest.raises(ConsolePackError, match="image"):
        ConsolePackExporter.export(
            tmp_path, "bad-image", {"gba": {"assets": {"cover": bad}}}
        )


def test_overwrite_removes_stale_managed_and_unmanaged_files(tmp_path):
    cover = make_image(tmp_path / "cover.png")
    first = ConsolePackExporter.export(
        tmp_path / "out",
        "overwrite",
        {"gba": {"assets": {"cover": cover}, "colors": {"color_start": "123456"}}},
    )
    (first / "stale.txt").write_text("old", encoding="utf-8")

    second = ConsolePackExporter.export(
        tmp_path / "out",
        "overwrite",
        {"nes": {"colors": {"color_end": "ABCDEF"}}},
    )
    assert second == first
    assert not (second / "covers").exists()
    assert not (second / "stale.txt").exists()
    assert json.loads((second / "colors.json").read_text()) == {
        "nes": {"color_end": "ABCDEF"}
    }


def test_zip_has_extraction_ready_consolepacks_layout_and_is_reproducible(tmp_path):
    background = make_image(tmp_path / "background.png")
    pack = ConsolePackExporter.export(
        tmp_path / "out", "zip-pack", {"snes": {"assets": {"background": background}}}
    )
    zip_path = ConsolePackExporter.create_zip(pack)
    first_bytes = zip_path.read_bytes()
    ConsolePackExporter.create_zip(pack)

    assert zip_path == tmp_path / "out" / "zip-pack.zip"
    assert zip_path.read_bytes() == first_bytes
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["zip-pack/backgrounds/snes.jpg"]
