# TICO Asset Builder

TICO Asset Builder 2.0 creates both classic TICO soundpacks and TICO console packs from a desktop UI. The existing `.tsbp` and portable `.tsbz` soundpack formats remain supported and are intentionally separate from console-pack state.

## Features

- **Soundpacks tab:** the original sound assignment, preview, project, portable-project, FFmpeg conversion, and ZIP workflow.
- **Console Packs tab:** configure any supported console independently with optional covers, backgrounds, logos, symbols, and gradient colors.
- English, Spanish, and Portuguese UI strings.

The console-pack contract follows the [official TICO console-pack guide](https://ticoverse.com/wiki/theming/using-console-packs).

## Console-pack output

Choose a destination folder and the application creates:

```text
<destination>/
├── <pack-name>/
│   ├── covers/<console>.jpg          (optional)
│   ├── backgrounds/<console>.jpg     (optional)
│   ├── logos/<console>.png           (optional)
│   ├── symbols/<console>.svg         (optional)
│   └── colors.json                   (optional)
└── <pack-name>.zip
```

Partial packs are valid. Raster images retain their dimensions and have EXIF orientation applied. PNG logos preserve transparency. Because JPEG has no alpha channel, transparent cover/background pixels are composited onto **white**. Symbols must be parseable SVG files and are copied without raster-to-vector conversion.

The sharing ZIP includes `<pack-name>/...`. Extract it anywhere, then place that folder under `sdmc:/tico/theme/consolepacks/` yourself. It is not a TICO Store package.

## Run from source

Python 3.9 or newer is recommended. FFmpeg/ffplay/ffprobe must be installed or bundled for soundpack conversion and preview; console-pack image export uses Pillow and does not need FFmpeg.

```bash
python3 -m venv .venv-dev
source .venv-dev/bin/activate       # Windows: .venv-dev\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

## Development and tests

```bash
python -m pip install -r requirements-dev.txt
pytest -q
python -m py_compile *.py
pyinstaller --clean --noconfirm main.spec
```

PyInstaller builds are platform-specific. Building on macOS does not produce or replace the Windows executable.

## Install a console pack

Extract the generated ZIP anywhere, then copy its `<pack-name>` directory into `sdmc:/tico/theme/consolepacks/`. You can also copy the generated folder directly. See **Help → How to Install a Console Pack** in the app.
