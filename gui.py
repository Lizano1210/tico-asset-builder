# gui.py

from PIL import Image, ImageTk
import sys
import json
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from PIL import Image

from language import LANGUAGES
from ffmpeg_manager import FFmpegManager
from validator import SoundValidator
from exporter import SoundpackExporter
from utils import resource_path
from portable_project import PortableProjectManager
import webbrowser

from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

from audio_preview import AudioPreview
from project_manager import ProjectManager
from drag_drop import DragDropManager
from console_pack_ui import ConsolePackTab

from utils import (
    resource_path,
    assign_file
)

APP_VERSION = "2.0.0"

class SoundpackBuilderApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ==================================================
        # CONFIGURACIÓN VENTANA
        # ==================================================

        self.title("TICO Asset Builder")
        if sys.platform == "win32":
            self.iconbitmap(resource_path("assets/tsb.ico"))
        else:
            self.iconphoto(True, ImageTk.PhotoImage(Image.open(resource_path("assets/tico_logo.png"))))
        self.minsize(1000, 760)
        self.resizable(True, True)
        from tkinterdnd2 import TkinterDnD

        self.TkdndVersion = TkinterDnD._require(self)

        print(
            f"TkDnD cargado: {self.TkdndVersion}"
        )

        # ==================================================
        # ESTADO
        # ==================================================

        self.current_language = "en"

        self.formats = self.load_formats()

        self.sound_files = {}
        self.audio_preview = AudioPreview()
        self.drag_drop = DragDropManager()
        self.play_buttons = {}
        self.stop_buttons = {}
        self.select_buttons = {}
        self.file_labels = {}
        self.manage_buttons = {}
        self.logo_pil = Image.open(resource_path("assets/tico_logo.png"))

        # ==================================================
        # UI
        # ==================================================

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.is_portable_project = False
        self._portable_tmp_dir = None

    def on_closing(self):

        self.audio_preview.cleanup()
        self._cleanup_portable_tmp()
        self.destroy()

    # ==================================================
    # HELPERS
    # ==================================================

    def _has_folders(self, sound_name):
        """
        Retorna True si el recurso soporta
        canciones adicionales según formats.json.
        """

        fmt = self.formats.get(sound_name)

        return (
            isinstance(fmt, dict)
            and fmt.get("folders", False)
        )

    def _get_main_path(self, sound_name):
        """
        Retorna la ruta principal de un recurso,
        independientemente de si es dict o str.
        """

        value = self.sound_files.get(sound_name)

        if isinstance(value, dict):
            return value.get("main")

        return value
    
    def _cleanup_portable_tmp(self):

        if self._portable_tmp_dir:

            import shutil

            shutil.rmtree(
                self._portable_tmp_dir,
                ignore_errors=True
            )

            self._portable_tmp_dir = None

    

    # ==================================================
    # DATOS
    # ==================================================

    def load_formats(self):

        with open(
            resource_path("assets/formats.json"),
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    def change_language(self, language):

        language_map = {
            "Español": "es",
            "English": "en",
            "Português": "pt"
        }

        self.current_language = language_map[language]

        lang = LANGUAGES[self.current_language]

        # ------------------------------
        # Header
        # ------------------------------

        self.title_label.configure(
            text=lang["title"]
        )

        # ------------------------------
        # Nombre del paquete
        # ------------------------------

        self.pack_name_label.configure(
            text=lang["pack_name"]
        )

        # ------------------------------
        # Botón exportar
        # ------------------------------

        self.export_button.configure(
            text=lang["create_pack"]
        )

        # ------------------------------
        # Botones de archivos
        # ------------------------------

        for sound_name, button in self.select_buttons.items():

            main_path = self._get_main_path(sound_name)

            if main_path is None:

                button.configure(
                    text=lang["select_file"]
                )

            else:

                button.configure(
                    text=lang["change_file"]
                )

        for sound_name, label in self.file_labels.items():

            main_path = self._get_main_path(sound_name)

            if main_path is None:

                label.configure(
                    text=f"❌ {lang['status_missing']}"
                )

            else:

                filename = Path(main_path).name

                label.configure(
                    text=f"✅ {lang['status_selected']} - {filename}"
                )

        # ------------------------------
        # Botones Manage Songs
        # ------------------------------

        for sound_name, button in self.manage_buttons.items():

            button.configure(
                text=lang["manage_songs"]
            )

        # ------------------------------
        # Menús
        # ------------------------------

        self.file_button.configure(
            text=lang["file_menu"]
        )

        self.help_button.configure(
            text=lang["help_menu"]
        )

        old_sound_title = self.sound_tab_title
        old_console_title = self.console_tab_title
        self.sound_tab_title = lang["soundpacks_tab"]
        self.console_tab_title = lang["console_packs_tab"]
        if old_sound_title != self.sound_tab_title:
            self.tabview.rename(old_sound_title, self.sound_tab_title)
        if old_console_title != self.console_tab_title:
            self.tabview.rename(old_console_title, self.console_tab_title)
        self.console_pack_editor.refresh_language()

    def handle_drop(
        self,
        sound_name,
        filepath
    ):

        assign_file(
            self,
            sound_name,
            filepath
        )

    def play_sound(
        self,
        sound_name
    ):

        main_path = self._get_main_path(sound_name)

        if not main_path:
            return

        self.audio_preview.play(
            main_path
        )

    def stop_sound(
        self
    ):

        self.audio_preview.stop()

    def load_project_files(
        self,
        sound_files
    ):

        for sound_name, value in sound_files.items():

            if not value:
                continue

            if isinstance(value, dict):

                main = value.get("main")

                if main and Path(main).exists():

                    assign_file(
                        self,
                        sound_name,
                        main
                    )

                extras = value.get("extras", [])

                if extras and self._has_folders(sound_name):

                    self.sound_files[sound_name]["extras"] = [
                        extra for extra in extras
                        if Path(extra.get("path", "")).exists()
                    ]

            else:

                if not Path(value).exists():
                    continue

                assign_file(
                    self,
                    sound_name,
                    value
                )

    def open_project(
        self
    ):

        filepath = filedialog.askopenfilename(
            filetypes=[
                (
                    "TSB Project",
                    "*.tsbp"
                )
            ]
        )

        if not filepath:
            return

        project = (
            ProjectManager.load_project(
                filepath
            )
        )

        if project is None:

            messagebox.showerror(
                LANGUAGES[self.current_language]["error"],
                LANGUAGES[self.current_language]["project_load_error"]
            )

            return

        if not ProjectManager.validate_files(
            project
        ):

            messagebox.showerror(
                LANGUAGES[self.current_language]["error"],
                LANGUAGES[self.current_language]["invalid_project"]
            )

            return

        self.pack_name_entry.delete(
            0,
            "end"
        )

        self.pack_name_entry.insert(
            0,
            project["project_name"]
        )

        self.load_project_files(
            project["files"]
        )

        missing = (
            ProjectManager.get_missing_files(
                project["files"]
            )
        )

        if missing:

            messagebox.showwarning(
                LANGUAGES[self.current_language]["missing_files"],
                "\n".join(missing)
            )

    def save_project(
        self
    ):

        project_name = (
            self.pack_name_entry
            .get()
            .strip()
        )

        if not project_name:

            messagebox.showerror(
                LANGUAGES[self.current_language]["error"],
                LANGUAGES[self.current_language]["project_name"]
            )

            return

        # ----------------------------------
        # Caso especial: proyecto portable
        # ----------------------------------

        if self.is_portable_project:

            messagebox.showinfo(
                LANGUAGES[self.current_language]["save_imported_project"],
                LANGUAGES[self.current_language]["portable_project_loaded"]
            )

            destination_folder = filedialog.askdirectory()

            if not destination_folder:
                return

            local_files, project_folder = (
                PortableProjectManager.save_as_local(
                    destination_folder,
                    project_name,
                    self.sound_files
                )
            )

            # Limpiar temp y desactivar flag ANTES de actualizar
            self._cleanup_portable_tmp()
            self.is_portable_project = False

            # Actualizar sound_files directamente con las rutas locales
            for sound_name, value in local_files.items():

                if sound_name not in self.sound_files:
                    continue

                if isinstance(value, dict):

                    self.sound_files[sound_name] = {
                        "main": value.get("main"),
                        "extras": value.get("extras", [])
                    }

                    main = value.get("main")

                    if main:
                        assign_file(self, sound_name, main)

                else:

                    self.sound_files[sound_name] = value

                    if value:
                        assign_file(self, sound_name, value)

            tsbp_path = project_folder / f"{project_name}.tsbp"

            success = ProjectManager.save_project(
                str(tsbp_path),
                project_name,
                self.sound_files
            )

            if success:

                messagebox.showinfo(
                    LANGUAGES[self.current_language]["success"],
                    LANGUAGES[self.current_language]["portable_saved_location"].format(
                        path=project_folder
                    )
                )

            return

        # ----------------------------------
        # Flujo normal
        # ----------------------------------

        filepath = filedialog.asksaveasfilename(
            defaultextension=".tsbp",
            filetypes=[
                (
                    "TSB Project",
                    "*.tsbp"
                )
            ]
        )

        if not filepath:
            return

        success = ProjectManager.save_project(
            filepath,
            project_name,
            self.sound_files
        )

        if success:

            messagebox.showinfo(
                LANGUAGES[self.current_language]["success"],
                LANGUAGES[self.current_language]["project_saved"]
            )

    # ==================================================
    # WIDGETS
    # ==================================================

    def create_widgets(self):

        self.create_top_bar()
        self.create_header()
        lang = LANGUAGES[self.current_language]
        self.sound_tab_title = lang["soundpacks_tab"]
        self.console_tab_title = lang["console_packs_tab"]
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.sound_tab = self.tabview.add(self.sound_tab_title)
        self.console_tab = self.tabview.add(self.console_tab_title)
        self.create_pack_name()
        self.create_sound_rows()
        self.create_footer()
        self.console_pack_editor = ConsolePackTab(
            self.console_tab,
            lambda: LANGUAGES[self.current_language]
        )
        self.console_pack_editor.pack(fill="both", expand=True)

    def create_top_bar(self):

        self.top_bar = ctk.CTkFrame(
            self,
            height=40
        )

        self.top_bar.pack(
            fill="x",
            padx=20,
            pady=(10, 0)
        )

        self.file_button = ctk.CTkButton(
            self.top_bar,
            text=LANGUAGES[self.current_language]["file_menu"],
            width=80,
            command=self.show_file_menu
        )

        self.file_button.pack(
            side="left",
            padx=5,
            pady=5
        )

        self.help_button = ctk.CTkButton(
            self.top_bar,
            text=LANGUAGES[self.current_language]["help_menu"],
            width=80,
            command=self.show_help_menu
        )

        self.help_button.pack(
            side="left",
            padx=5,
            pady=5
        )

        self.language_menu = ctk.CTkOptionMenu(
            self.top_bar,
            values=[
                "English",
                "Español",
                "Português"
            ],
            command=self.change_language
        )

        self.language_menu.pack(
            side="right",
            padx=5,
            pady=5
        )

        self.small_logo = ctk.CTkImage(
            light_image=self.logo_pil,
            dark_image=self.logo_pil,
            size=(90, 45)
        )

        self.logo_label = ctk.CTkLabel(
            self.top_bar,
            text="",
            image=self.small_logo
        )

        self.logo_label.pack(
            side="right",
            padx=(0, 10),
            pady=5
        )

    def show_file_menu(self):

        menu = tk.Menu(
            self,
            tearoff=0
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["sound_new_project"],
            command=self.new_project
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["sound_open_project"],
            command=self.open_project
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["sound_save_project"],
            command=self.save_project
        )

        menu.add_separator()

        menu.add_command(
            label=LANGUAGES[self.current_language]["sound_export_portable"],
            command=self.export_portable_project
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["sound_import_portable"],
            command=self.import_portable_project
        )

        menu.add_separator()

        menu.add_command(
            label=LANGUAGES[self.current_language]["exit"],
            command=self.on_closing
        )

        menu.post(
            self.file_button.winfo_rootx(),
            self.file_button.winfo_rooty()
            + self.file_button.winfo_height()
        )

    def show_help_menu(self):

        menu = tk.Menu(
            self,
            tearoff=0
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["github"],
            command=self.open_github
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["install_guide"],
            command=self.show_install_guide
        )

        menu.add_command(
            label=LANGUAGES[self.current_language]["console_install_guide"],
            command=self.show_console_install_guide
        )

        menu.add_separator()

        menu.add_command(
            label=LANGUAGES[self.current_language]["about"],
            command=self.show_about
        )

        menu.post(
            self.help_button.winfo_rootx(),
            self.help_button.winfo_rooty()
            + self.help_button.winfo_height()
        )

    # ==================================================
    # HEADER
    # ==================================================

    def create_header(self):

        header_frame = ctk.CTkFrame(self)

        header_frame.pack(
            fill="x",
            padx=20,
            pady=20
        )

        left_frame = ctk.CTkFrame(
            header_frame,
            fg_color="transparent"
        )

        left_frame.pack(
            side="left",
            padx=10,
            pady=10
        )

        self.title_label = ctk.CTkLabel(
            left_frame,
            text=LANGUAGES[self.current_language]["title"],
            font=("Arial", 24, "bold")
        )

        self.title_label.pack(
            anchor="w",
            pady=5
        )

    # ==================================================
    # NOMBRE DEL PAQUETE
    # ==================================================

    def create_pack_name(self):

        frame = ctk.CTkFrame(self.sound_tab)

        frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        self.pack_name_label = ctk.CTkLabel(
            frame,
            text=LANGUAGES[self.current_language]["pack_name"]
        )

        self.pack_name_label.pack(
            anchor="w",
            padx=10,
            pady=(10, 5)
        )

        self.pack_name_entry = ctk.CTkEntry(
            frame
        )

        self.pack_name_entry.pack(
            fill="x",
            padx=10,
            pady=(0, 10)
        )

    # ==================================================
    # SONIDOS
    # ==================================================

    def create_sound_rows(self):

        self.sounds_frame = ctk.CTkScrollableFrame(self.sound_tab)

        self.sounds_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=10
        )

        for sound_name, fmt in self.formats.items():

            has_folders = (
                isinstance(fmt, dict)
                and fmt.get("folders", False)
            )

            # Inicializar estructura según tipo
            if has_folders:

                self.sound_files[sound_name] = {
                    "main": None,
                    "extras": []
                }

            else:

                self.sound_files[sound_name] = None

            row = ctk.CTkFrame(self.sounds_frame)

            row.pack(
                fill="x",
                pady=4,
                padx=5
            )

            # ----------------------------------
            # Nombre
            # ----------------------------------

            name_label = ctk.CTkLabel(
                row,
                text=sound_name,
                width=220,
                anchor="w"
            )

            name_label.pack(
                side="left",
                padx=10
            )

            # ----------------------------------
            # Botón seleccionar
            # ----------------------------------

            select_button = ctk.CTkButton(
                row,
                text=LANGUAGES[self.current_language]["select_file"],
                width=170,
                command=lambda name=sound_name:
                self.select_file(name)
            )

            select_button.pack(
                side="left",
                padx=10
            )

            # ----------------------------------
            # Botones play / stop
            # ----------------------------------

            play_button = ctk.CTkButton(
                row,
                text="▶",
                width=40,
                command=lambda s=sound_name:
                self.play_sound(s)
            )

            play_button.pack(
                side="left",
                padx=5
            )

            stop_button = ctk.CTkButton(
                row,
                text="■",
                width=40,
                command=self.stop_sound
            )

            stop_button.pack(
                side="left",
                padx=5
            )

            # ----------------------------------
            # Botón Manage Songs (solo si folders)
            # ----------------------------------

            if has_folders:

                manage_button = ctk.CTkButton(
                    row,
                    text=LANGUAGES[self.current_language]["manage_songs"],
                    width=140,
                    command=lambda name=sound_name:
                    self.open_song_manager(name)
                )

                manage_button.pack(
                    side="left",
                    padx=10
                )

                self.manage_buttons[sound_name] = manage_button

            # ----------------------------------
            # Estado / archivo
            # ----------------------------------

            file_label = ctk.CTkLabel(
                row,
                text=f"❌ {LANGUAGES[self.current_language]['status_missing']}",
                anchor="w"
            )

            file_label.pack(
                side="left",
                padx=15
            )

            self.select_buttons[sound_name] = select_button
            self.file_labels[sound_name] = file_label
            self.play_buttons[sound_name] = play_button
            self.stop_buttons[sound_name] = stop_button

            self.drag_drop.register_target(
                row,
                sound_name,
                self.handle_drop
            )

    # ==================================================
    # SELECCIÓN DE ARCHIVOS
    # ==================================================

    def select_file(
        self,
        sound_name
    ):

        filepath = filedialog.askopenfilename()

        if not filepath:
            return

        assign_file(
            self,
            sound_name,
            filepath
        )

    # ==================================================
    # SONG MANAGER
    # ==================================================

    def open_song_manager(
        self,
        sound_name
    ):

        lang = LANGUAGES[self.current_language]

        manager_window = ctk.CTkToplevel(self)

        manager_window.title(
            f"{lang['manage_songs']} — {sound_name}"
        )

        manager_window.geometry("600x450")

        manager_window.transient(self)

        manager_window.grab_set()

        # ----------------------------------
        # Lista de canciones
        # ----------------------------------

        list_frame = ctk.CTkScrollableFrame(
            manager_window
        )

        list_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(20, 10)
        )

        def refresh_list():

            for widget in list_frame.winfo_children():
                widget.destroy()

            extras = self.sound_files[sound_name].get(
                "extras",
                []
            )

            if not extras:

                ctk.CTkLabel(
                    list_frame,
                    text=lang["no_additional_songs"],
                    anchor="w"
                ).pack(
                    fill="x",
                    padx=10,
                    pady=10
                )

                return

            for index, extra in enumerate(extras):

                song_row = ctk.CTkFrame(list_frame)

                song_row.pack(
                    fill="x",
                    pady=3,
                    padx=5
                )

                ctk.CTkLabel(
                    song_row,
                    text=extra.get("name", ""),
                    anchor="w",
                    width=250
                ).pack(
                    side="left",
                    padx=10
                )

                ctk.CTkLabel(
                    song_row,
                    text=Path(
                        extra.get("path", "")
                    ).name,
                    anchor="w",
                    text_color="gray"
                ).pack(
                    side="left",
                    padx=5
                )

                ctk.CTkButton(
                    song_row,
                    text="✏️",
                    width=36,
                    command=lambda i=index: (
                        self.rename_extra_song(
                            sound_name,
                            i
                        ),
                        refresh_list()
                    )
                ).pack(
                    side="right",
                    padx=5
                )

                ctk.CTkButton(
                    song_row,
                    text="🗑️",
                    width=36,
                    command=lambda i=index: (
                        self.remove_extra_song(
                            sound_name,
                            i
                        ),
                        refresh_list()
                    )
                ).pack(
                    side="right",
                    padx=5
                )

        refresh_list()

        # ----------------------------------
        # Botón añadir
        # ----------------------------------

        button_frame = ctk.CTkFrame(
            manager_window,
            fg_color="transparent"
        )

        button_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 20)
        )

        ctk.CTkButton(
            button_frame,
            text=lang["add_song"],
            command=lambda: (
                self.add_extra_song(sound_name),
                refresh_list()
            )
        ).pack(
            side="left",
            padx=5
        )

    def add_extra_song(
        self,
        sound_name
    ):

        filepath = filedialog.askopenfilename()

        if not filepath:
            return

        name = Path(filepath).stem

        self.sound_files[sound_name]["extras"].append(
            {
                "name": name,
                "path": filepath
            }
        )

    def remove_extra_song(
        self,
        sound_name,
        index
    ):

        extras = self.sound_files[sound_name].get(
            "extras",
            []
        )

        if 0 <= index < len(extras):

            extras.pop(index)

    def rename_extra_song(
        self,
        sound_name,
        index
    ):

        extras = self.sound_files[sound_name].get(
            "extras",
            []
        )

        if not (0 <= index < len(extras)):
            return

        current_name = extras[index].get("name", "")

        new_name = simpledialog.askstring(
            LANGUAGES[self.current_language]["rename_song"],
            LANGUAGES[self.current_language]["rename_song_prompt"],
            initialvalue=current_name
        )

        if new_name and new_name.strip():

            extras[index]["name"] = new_name.strip()

    # ==================================================
    # EXPORTAR
    # ==================================================

    def create_soundpack(self):

        # ----------------------------------
        # Validar nombre
        # ----------------------------------

        soundpack_name = (
            self.pack_name_entry.get().strip()
        )

        if not soundpack_name:

            messagebox.showerror(
                LANGUAGES[self.current_language]["validation_error"],
                LANGUAGES[self.current_language]["empty_name"]
            )

            return

        # ----------------------------------
        # Validar archivos
        # ----------------------------------

        invalid_sounds = []

        for sound_name in self.sound_files:

            main_path = self._get_main_path(sound_name)

            if main_path is None:
                invalid_sounds.append(sound_name)
                continue

            if not Path(main_path).exists():
                invalid_sounds.append(sound_name)
                continue

            if not SoundValidator.is_supported_audio(main_path):
                invalid_sounds.append(sound_name)

        if invalid_sounds:

            messagebox.showerror(
                LANGUAGES[self.current_language]["validation_error"],
                LANGUAGES[self.current_language]["missing_files"]
            )

            return

        # ----------------------------------
        # Verificar FFmpeg
        # ----------------------------------

        if not FFmpegManager.ffmpeg_exists():

            messagebox.showerror(
                LANGUAGES[self.current_language]["conversion_error"],
                LANGUAGES[self.current_language]["ffmpeg_not_found"]
            )

            return

        # ----------------------------------
        # Elegir carpeta destino
        # ----------------------------------

        destination_folder = (
            filedialog.askdirectory()
        )

        if not destination_folder:
            return

        # ----------------------------------
        # Exportar
        # ----------------------------------

        try:

            soundpack_path = (
                SoundpackExporter.create_soundpack(
                    destination_folder,
                    soundpack_name,
                    self.sound_files,
                    self.formats
                )
            )

            SoundpackExporter.create_zip(
                soundpack_path
            )

            messagebox.showinfo(
                LANGUAGES[self.current_language]["success"],
                LANGUAGES[self.current_language]["export_success"]
            )

        except Exception as error:

            messagebox.showerror(
                LANGUAGES[self.current_language]["conversion_error"],
                LANGUAGES[self.current_language]["audio_conversion_failed"]
                + f"\n\n{error}"
            )

    # ==================================================
    # FOOTER
    # ==================================================

    def create_footer(self):

        self.footer_frame = ctk.CTkFrame(self.sound_tab)

        self.footer_frame.pack(
            fill="x",
            side="bottom",
            padx=20,
            pady=10
        )

        self.export_button = ctk.CTkButton(
            self.footer_frame,
            text=LANGUAGES[self.current_language]["create_pack"],
            height=40,
            command=self.create_soundpack
        )

        self.export_button.pack(
            pady=10
        )

    # ==================================================
    # ACCIONES
    # ==================================================

    def new_project(self):
        lang = LANGUAGES[self.current_language]

        # Preguntar si guardar antes de limpiar
        answer = messagebox.askyesnocancel(
            lang["new_project"],
            lang["new_project_confirm"]
        )

        # Cancelar — no hacer nada
        if answer is None:
            return

        # Sí — guardar primero
        if answer:
            self.save_project()

        # Limpiar estado
        self._cleanup_portable_tmp()
        self.is_portable_project = False

        self.pack_name_entry.delete(0, "end")

        for sound_name in self.sound_files:

            if self._has_folders(sound_name):

                self.sound_files[sound_name] = {
                    "main": None,
                    "extras": []
                }

            else:

                self.sound_files[sound_name] = None

            self.file_labels[sound_name].configure(
                text=f"❌ {lang['status_missing']}"
            )

            self.select_buttons[sound_name].configure(
                text=lang["select_file"]
            )

    def export_portable_project(self):

        project_name = self.pack_name_entry.get().strip()

        if not project_name:

            messagebox.showerror(
                LANGUAGES[self.current_language]["error"],
                LANGUAGES[self.current_language]["project_name"]
            )

            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".tsbz",
            filetypes=[("TSB Portable Project", "*.tsbz")],
            initialfile=project_name
        )

        if not filepath:
            return

        try:

            PortableProjectManager.export(
                filepath,
                project_name,
                self.sound_files
            )

            messagebox.showinfo(
                LANGUAGES[self.current_language]["success"],
                LANGUAGES[self.current_language]["portable_export_success"]
            )

        except Exception as error:

            messagebox.showerror(
                LANGUAGES[self.current_language]["error"],
                str(error)
            )

    def import_portable_project(self):

        filepath = filedialog.askopenfilename(
            filetypes=[("TSB Portable Project", "*.tsbz")]
        )

        if not filepath:
            return

        result = PortableProjectManager.import_project(filepath)

        if result is None:

            messagebox.showerror(
                LANGUAGES[self.current_language]["error"],
                LANGUAGES[self.current_language]["portable_project_error"]
            )

            return

        # Limpiar temp anterior si existía
        self._cleanup_portable_tmp()

        self._portable_tmp_dir = result["tmp_dir"]
        self.is_portable_project = True

        self.pack_name_entry.delete(0, "end")
        self.pack_name_entry.insert(0, result["project_name"])

        self.load_project_files(result["files"])

        messagebox.showinfo(
            LANGUAGES[self.current_language]["success"],
            LANGUAGES[self.current_language]["portable_import_success"]
        )

    def open_github(self):
        webbrowser.open(
            "https://github.com/Lizano1210/tico-soundpack-builder"
        )

    def show_install_guide(self):

        guide_window = ctk.CTkToplevel(self)

        guide_window.title(
            LANGUAGES[self.current_language]["install_guide_title"]
        )

        guide_window.geometry("650x450")

        guide_window.transient(self)

        guide_window.grab_set()

        content_frame = ctk.CTkFrame(
            guide_window
        )

        content_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=20
        )

        guide_label = ctk.CTkLabel(
            content_frame,
            text=LANGUAGES[self.current_language]["install_guide_text"],
            justify="left",
            anchor="nw"
        )

        guide_label.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        logo_label = ctk.CTkLabel(
            content_frame,
            text="",
            image=self.small_logo
        )

        logo_label.pack(
            anchor="se",
            padx=10,
            pady=10
        )

    def show_console_install_guide(self):
        lang = LANGUAGES[self.current_language]
        messagebox.showinfo(
            lang["console_install_guide_title"],
            lang["console_install_guide_text"],
            parent=self
        )

    def show_about(self):

        about_window = ctk.CTkToplevel(self)

        about_window.title(
            LANGUAGES[self.current_language]["about_title"]
        )

        about_window.geometry("650x400")

        about_window.transient(self)

        about_window.grab_set()

        content_frame = ctk.CTkFrame(
            about_window
        )

        content_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=20
        )

        about_text = LANGUAGES[
            self.current_language
        ]["about_text"].format(
            version=APP_VERSION
        )

        about_label = ctk.CTkLabel(
            content_frame,
            text=about_text,
            justify="left",
            anchor="nw"
        )

        about_label.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        logo_label = ctk.CTkLabel(
            content_frame,
            text="",
            image=self.small_logo
        )

        logo_label.pack(
            anchor="se",
            padx=10,
            pady=10
        )