"""CustomTkinter UI for building console packs."""

import shutil
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageOps

from console_pack import (
    ASSET_TYPES,
    COLOR_KEYS,
    CONSOLE_SLUGS,
    ConsolePackExporter,
    apply_palette_to_all,
)
from console_project import (
    LOCAL_EXTENSION,
    PORTABLE_EXTENSION,
    ConsoleProjectManager,
)


class ConsolePackTab(ctk.CTkFrame):
    """Console-pack editor with independent, per-console in-memory state."""

    ASSET_LABEL_KEYS = {
        "cover": "console_cover",
        "background": "console_background",
        "logo": "console_logo",
        "symbol": "console_symbol",
    }
    COLOR_LABEL_KEYS = {
        "color_start": "color_start",
        "color_end": "color_end",
        "color_start_dark": "color_start_dark",
        "color_end_dark": "color_end_dark",
    }

    def __init__(self, master, language_getter):
        super().__init__(master, fg_color="transparent")
        self.language_getter = language_getter
        self.state = {
            slug: {"assets": {}, "colors": {}}
            for slug in CONSOLE_SLUGS
        }
        self.current_slug = CONSOLE_SLUGS[0]
        self.is_portable_project = False
        self._portable_tmp_dir = None
        self.preview_images = {}
        self.asset_name_labels = {}
        self.asset_select_buttons = {}
        self.asset_clear_buttons = {}
        self.asset_title_labels = {}
        self.preview_labels = {}
        self.color_labels = {}
        self.color_entries = {}
        self.color_clear_buttons = {}
        self.color_swatch_buttons = {}
        self._build()
        self.refresh_language()
        self._load_console(self.current_slug)

    def cleanup(self):
        if self._portable_tmp_dir:
            shutil.rmtree(self._portable_tmp_dir, ignore_errors=True)
            self._portable_tmp_dir = None

    def _empty_state(self):
        return {slug: {"assets": {}, "colors": {}} for slug in CONSOLE_SLUGS}

    def _replace_project(self, pack_name, console_state):
        self.state = self._empty_state()
        for slug, entry in console_state.items():
            self.state[slug] = {
                "assets": dict(entry.get("assets", {})),
                "colors": dict(entry.get("colors", {})),
            }
        self.pack_name_entry.delete(0, "end")
        self.pack_name_entry.insert(0, pack_name)
        self.current_slug = CONSOLE_SLUGS[0]
        self.console_menu.set(self.current_slug)
        self._load_console(self.current_slug)

    def new_project(self):
        lang = self.lang
        answer = messagebox.askyesnocancel(
            lang["console_new_project"],
            lang["console_new_project_confirm"],
            parent=self,
        )
        if answer is None:
            return
        if answer and not self.save_project():
            return
        self.cleanup()
        self.is_portable_project = False
        self._replace_project("", {})

    def open_project(self):
        filepath = filedialog.askopenfilename(
            filetypes=[(self.lang["console_local_project_type"], "*" + LOCAL_EXTENSION)]
        )
        if not filepath:
            return
        try:
            project = ConsoleProjectManager.load_local(filepath)
        except Exception as error:
            messagebox.showerror(self.lang["error"], str(error), parent=self)
            return
        self.cleanup()
        self.is_portable_project = False
        self._replace_project(project["pack_name"], project["consoles"])
        missing = ConsoleProjectManager.missing_assets(project["consoles"])
        if missing:
            messagebox.showwarning(
                self.lang["missing_files"],
                self.lang["console_missing_assets"].format(assets="\n".join(missing)),
                parent=self,
            )

    def save_project(self):
        self._save_visible_colors()
        pack_name = self.pack_name_entry.get().strip()
        if not pack_name:
            messagebox.showerror(self.lang["error"], self.lang["project_name"], parent=self)
            return False
        filepath = filedialog.asksaveasfilename(
            defaultextension=LOCAL_EXTENSION,
            filetypes=[(self.lang["console_local_project_type"], "*" + LOCAL_EXTENSION)],
            initialfile=pack_name,
        )
        if not filepath:
            return False
        try:
            if self.is_portable_project:
                _path, local_state = ConsoleProjectManager.save_imported_as_local(
                    filepath, pack_name, self.state
                )
                self.cleanup()
                self.is_portable_project = False
                self._replace_project(pack_name, local_state)
            else:
                ConsoleProjectManager.save_local(filepath, pack_name, self.state)
        except Exception as error:
            messagebox.showerror(self.lang["error"], str(error), parent=self)
            return False
        messagebox.showinfo(self.lang["success"], self.lang["project_saved"], parent=self)
        return True

    def export_portable_project(self):
        self._save_visible_colors()
        pack_name = self.pack_name_entry.get().strip()
        if not pack_name:
            messagebox.showerror(self.lang["error"], self.lang["project_name"], parent=self)
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=PORTABLE_EXTENSION,
            filetypes=[(self.lang["console_portable_project_type"], "*" + PORTABLE_EXTENSION)],
            initialfile=pack_name,
        )
        if not filepath:
            return
        try:
            ConsoleProjectManager.export_portable(filepath, pack_name, self.state)
        except Exception as error:
            messagebox.showerror(self.lang["error"], str(error), parent=self)
            return
        messagebox.showinfo(
            self.lang["success"], self.lang["console_portable_export_success"], parent=self
        )

    def import_portable_project(self):
        filepath = filedialog.askopenfilename(
            filetypes=[(self.lang["console_portable_project_type"], "*" + PORTABLE_EXTENSION)]
        )
        if not filepath:
            return
        try:
            project = ConsoleProjectManager.import_portable(filepath)
        except Exception as error:
            messagebox.showerror(self.lang["error"], str(error), parent=self)
            return
        self.cleanup()
        self._portable_tmp_dir = project["tmp_dir"]
        self.is_portable_project = True
        self._replace_project(project["pack_name"], project["consoles"])
        messagebox.showinfo(
            self.lang["success"], self.lang["console_portable_import_success"], parent=self
        )

    @property
    def lang(self):
        return self.language_getter()

    def _build(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=(10, 5))

        self.pack_name_label = ctk.CTkLabel(header, anchor="w")
        self.pack_name_label.grid(row=0, column=0, padx=10, pady=(10, 3), sticky="w")
        self.pack_name_entry = ctk.CTkEntry(header, width=280)
        self.pack_name_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        self.console_label = ctk.CTkLabel(header, anchor="w")
        self.console_label.grid(row=0, column=1, padx=10, pady=(10, 3), sticky="w")
        self.console_menu = ctk.CTkOptionMenu(
            header, values=list(CONSOLE_SLUGS), command=self._switch_console
        )
        self.console_menu.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)

        self.summary_label = ctk.CTkLabel(header, anchor="w", text_color=("#555555", "#BBBBBB"))
        self.summary_label.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="ew")

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=10, pady=5)

        self.assets_heading = ctk.CTkLabel(body, font=("Arial", 17, "bold"), anchor="w")
        self.assets_heading.pack(fill="x", padx=8, pady=(8, 3))
        for asset_type in ASSET_TYPES:
            row = ctk.CTkFrame(body)
            row.pack(fill="x", padx=5, pady=3)
            title = ctk.CTkLabel(row, width=120, anchor="w")
            title.pack(side="left", padx=8, pady=8)
            preview = ctk.CTkLabel(row, text="—", width=64, height=42)
            preview.pack(side="left", padx=4)
            select = ctk.CTkButton(
                row, width=120, command=lambda kind=asset_type: self._select_asset(kind)
            )
            select.pack(side="left", padx=5)
            clear = ctk.CTkButton(
                row, width=70, fg_color="#8B3333", hover_color="#6D2828",
                command=lambda kind=asset_type: self._clear_asset(kind),
            )
            clear.pack(side="left", padx=5)
            status = ctk.CTkLabel(row, anchor="w")
            status.pack(side="left", fill="x", expand=True, padx=8)
            self.asset_title_labels[asset_type] = title
            self.preview_labels[asset_type] = preview
            self.asset_select_buttons[asset_type] = select
            self.asset_clear_buttons[asset_type] = clear
            self.asset_name_labels[asset_type] = status

        self.colors_heading = ctk.CTkLabel(body, font=("Arial", 17, "bold"), anchor="w")
        self.colors_heading.pack(fill="x", padx=8, pady=(14, 3))
        self.color_hint = ctk.CTkLabel(body, anchor="w", text_color=("#555555", "#BBBBBB"))
        self.color_hint.pack(fill="x", padx=8, pady=(0, 5))
        self.apply_colors_button = ctk.CTkButton(
            body, width=190, command=self._apply_colors_to_all
        )
        self.apply_colors_button.pack(anchor="w", padx=8, pady=(0, 7))
        for color_key in COLOR_KEYS:
            row = ctk.CTkFrame(body)
            row.pack(fill="x", padx=5, pady=3)
            label = ctk.CTkLabel(row, width=175, anchor="w")
            label.pack(side="left", padx=8, pady=8)
            entry = ctk.CTkEntry(row, width=130, placeholder_text="RRGGBB")
            entry.pack(side="left", padx=5)
            entry.bind("<KeyRelease>", lambda _event, key=color_key: self._color_typed(key))
            swatch = ctk.CTkButton(
                row, text="", width=42, command=lambda key=color_key: self._choose_color(key)
            )
            swatch.pack(side="left", padx=5)
            clear = ctk.CTkButton(
                row, width=70, fg_color="#8B3333", hover_color="#6D2828",
                command=lambda key=color_key: self._clear_color(key),
            )
            clear.pack(side="left", padx=5)
            self.color_labels[color_key] = label
            self.color_entries[color_key] = entry
            self.color_swatch_buttons[color_key] = swatch
            self.color_clear_buttons[color_key] = clear

        footer = ctk.CTkFrame(self)
        footer.pack(fill="x", padx=10, pady=(5, 10))
        self.export_button = ctk.CTkButton(footer, height=40, command=self._export)
        self.export_button.pack(side="left", padx=10, pady=10)
        self.zip_note = ctk.CTkLabel(footer, anchor="w", text_color=("#555555", "#BBBBBB"))
        self.zip_note.pack(side="left", fill="x", expand=True, padx=5)

    def refresh_language(self):
        lang = self.lang
        self.pack_name_label.configure(text=lang["console_pack_name"])
        self.console_label.configure(text=lang["console_selector"])
        self.assets_heading.configure(text=lang["console_assets"])
        self.colors_heading.configure(text=lang["console_colors"])
        self.color_hint.configure(text=lang["console_color_hint"])
        self.apply_colors_button.configure(text=lang["apply_colors_to_all"])
        self.export_button.configure(text=lang["create_console_pack"])
        self.zip_note.configure(text=lang["console_zip_note"])
        for kind in ASSET_TYPES:
            self.asset_title_labels[kind].configure(text=lang[self.ASSET_LABEL_KEYS[kind]])
            self.asset_clear_buttons[kind].configure(text=lang["clear"])
        for key in COLOR_KEYS:
            self.color_labels[key].configure(text=lang[self.COLOR_LABEL_KEYS[key]])
            self.color_clear_buttons[key].configure(text=lang["clear"])
        self._refresh_assets()
        self._refresh_summary()

    def _save_visible_colors(self):
        colors = self.state[self.current_slug]["colors"]
        for key, entry in self.color_entries.items():
            value = entry.get().strip()
            if value:
                colors[key] = value
            else:
                colors.pop(key, None)

    def _switch_console(self, slug):
        self._save_visible_colors()
        self.current_slug = slug
        self._load_console(slug)

    def _load_console(self, slug):
        colors = self.state[slug]["colors"]
        for key, entry in self.color_entries.items():
            entry.delete(0, "end")
            if colors.get(key):
                entry.insert(0, colors[key])
            self._update_swatch(key)
        self._refresh_assets()
        self._refresh_summary()

    def _select_asset(self, asset_type):
        if asset_type == "symbol":
            filetypes = [("SVG", "*.svg"), (self.lang["all_files"], "*.*")]
        else:
            filetypes = [
                (self.lang["image_files"], "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
                (self.lang["all_files"], "*.*"),
            ]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self.state[self.current_slug]["assets"][asset_type] = path
            self._refresh_assets()
            self._refresh_summary()

    def _clear_asset(self, asset_type):
        self.state[self.current_slug]["assets"].pop(asset_type, None)
        self._refresh_assets()
        self._refresh_summary()

    def _refresh_assets(self):
        if not self.asset_name_labels:
            return
        lang = self.lang
        assets = self.state[self.current_slug]["assets"]
        for kind in ASSET_TYPES:
            path = assets.get(kind)
            self.asset_select_buttons[kind].configure(
                text=lang["change_file"] if path else lang["select_file"]
            )
            self.asset_name_labels[kind].configure(
                text=("✅ {0} — {1}".format(lang["status_selected"], Path(path).name)
                      if path else "❌ {0}".format(lang["status_missing"]))
            )
            self._set_preview(kind, path)

    def _set_preview(self, kind, path):
        label = self.preview_labels[kind]
        if not path:
            label.configure(image=None, text="—")
            self.preview_images.pop(kind, None)
            return
        if kind == "symbol":
            label.configure(image=None, text="SVG")
            self.preview_images.pop(kind, None)
            return
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((64, 42))
                preview = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self.preview_images[kind] = preview
            label.configure(image=preview, text="")
        except (OSError, ValueError):
            label.configure(image=None, text="⚠")
            self.preview_images.pop(kind, None)

    def _color_typed(self, key):
        self._save_visible_colors()
        self._update_swatch(key)
        self._refresh_summary()

    def _choose_color(self, key):
        current = self.color_entries[key].get().strip()
        initial = "#" + current if len(current) == 6 else None
        selected = colorchooser.askcolor(color=initial, parent=self)[1]
        if selected:
            entry = self.color_entries[key]
            entry.delete(0, "end")
            entry.insert(0, selected.lstrip("#").upper())
            self._color_typed(key)

    def _clear_color(self, key):
        self.color_entries[key].delete(0, "end")
        self.state[self.current_slug]["colors"].pop(key, None)
        self._update_swatch(key)
        self._refresh_summary()

    def _apply_colors_to_all(self):
        self._save_visible_colors()
        try:
            apply_palette_to_all(
                self.state,
                self.state[self.current_slug]["colors"],
            )
        except Exception as error:
            messagebox.showerror(
                self.lang["validation_error"], str(error), parent=self
            )
            return
        self._load_console(self.current_slug)
        messagebox.showinfo(
            self.lang["success"],
            self.lang["apply_colors_success"].format(count=len(CONSOLE_SLUGS)),
            parent=self,
        )

    def _update_swatch(self, key):
        value = self.color_entries[key].get().strip()
        color = "#" + value if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value) else "gray50"
        self.color_swatch_buttons[key].configure(fg_color=color, hover_color=color)

    def _refresh_summary(self):
        configured = []
        for slug in CONSOLE_SLUGS:
            entry = self.state[slug]
            count = len(entry["assets"]) + len(entry["colors"])
            if count:
                configured.append("{0} ({1})".format(slug, count))
        value = ", ".join(configured) if configured else self.lang["none"]
        self.summary_label.configure(text=self.lang["configured_consoles"].format(consoles=value))

    def _export(self):
        self._save_visible_colors()
        destination = filedialog.askdirectory()
        if not destination:
            return
        try:
            pack_path, zip_path = ConsolePackExporter.export_bundle(
                destination, self.pack_name_entry.get(), self.state
            )
        except Exception as error:
            messagebox.showerror(self.lang["validation_error"], str(error), parent=self)
            return
        messagebox.showinfo(
            self.lang["success"],
            self.lang["console_export_success"].format(pack=pack_path, zip=zip_path),
            parent=self,
        )
