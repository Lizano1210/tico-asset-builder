# TICO Asset Builder <img width="64" height="64" alt="tsb" src="https://github.com/user-attachments/assets/3415c258-f8c7-42e6-bca9-dd03d5080265" /> 


A simple desktop tool for creating custom asset packs for [TICO](https://ticoverse.com/). Add your favorite sounds or artwork, choose your colors, and export a ready-to-use pack—no manual conversion or folder setup required.

TICO Asset Builder can create two kinds of packs:

- **Soundpacks** change TICO's interface sounds and background music.
- **Console Packs** change console covers, backgrounds, logos, symbols, and card colors.

The app is available in English, Spanish, and Portuguese.

## Download

Download the latest build from the [Releases page](https://github.com/Lizano1210/tico-asset-builder/releases).

The Windows build is portable: download the `.exe` and run it directly. No installation is required.

## Creating a Soundpack

1. Open the **Soundpacks** tab.
2. Enter a name for your soundpack.
3. Select or drag and drop an audio file into each sound slot.
4. Use the preview controls to check your sounds.
5. Use **Manage Songs** to add extra background-music tracks when needed.
6. Click **Create Soundpack** and choose where to save it.

The builder automatically converts supported audio files to the formats TICO expects. FFmpeg is included with the bundled release.

To install the finished pack, copy its generated folder into:

```text
sdmc:/tico/theme/soundpacks/
```

Then open TICO and go to:

```text
Settings → Audio → Soundpacks
```

Choose your new soundpack from the list.

## Creating a Console Pack

1. Open the **Console Packs** tab.
2. Enter a name for your console pack.
3. Select a console and add any artwork you want to replace:
   - Cover
   - Background
   - Logo
   - Symbol
4. Optionally choose light- and dark-mode gradient colors.
5. Repeat for any other consoles you want to customize. Use **Apply colors to all consoles** when the whole pack should share one palette.
6. Click **Create Console Pack** and choose where to save it.

Console Packs can be partial. You only need to configure the consoles and assets you want to change; TICO uses its defaults for everything else.

To install the finished pack, copy its generated folder into:

```text
sdmc:/tico/theme/consolepacks/
```

Then open TICO and go to:

```text
Settings → Interface → Card settings → Console Pack
```

Choose your new console pack from the list.

## Projects

Projects let you continue editing a pack later or share the editable project with someone else.

| Pack type | Local project | Portable project |
| --- | --- | --- |
| Soundpack | `.tsbp` | `.tsbz` |
| Console Pack | `.tcp` | `.tcpz` |

Local projects reference files on your computer. Portable projects include the source files so the project can be moved to another computer.

The **File** menu automatically shows the correct project options for the active tab.

## Pack names

Keep pack names simple. Use letters, numbers, underscores, or hyphens so TICO can display and load them reliably.

Examples:

```text
retro_clicks
minimal-pack
my_console_pack
```

## Windows SmartScreen warning

Windows may show a Microsoft Defender SmartScreen warning the first time you run the downloaded `.exe`. This happens because the community-built executable is not digitally signed.

If you downloaded it from this repository's official Releases page:

1. Click **More info**.
2. Confirm that the app is **TICO Asset Builder**.
3. Click **Run anyway**.

You do not need to disable SmartScreen or Windows Defender. The project is open source, so the complete source code can be reviewed here before running the application.

## Run from source

Python 3.9 or newer is recommended.

```bash
python3 -m venv .venv-dev
source .venv-dev/bin/activate       # Windows: .venv-dev\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Soundpack conversion and audio preview require FFmpeg, ffplay, and ffprobe when running from source.

## Official TICO guides

- [Using Soundpacks](https://ticoverse.com/wiki/assets/using-soundpacks)
- [Using Console Packs](https://ticoverse.com/wiki/theming/using-console-packs)

  <img width="640" height="312" alt="tico_logo" src="https://github.com/user-attachments/assets/a9a21566-24fb-4fac-9450-ddb431a88b94" />

