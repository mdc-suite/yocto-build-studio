import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
import subprocess
import threading
import queue
import zipfile
import shutil
import re
import os
import sys

# ============================================================
# Yocto Build Studio — Modern Developer Studio
# Responsive CustomTkinter UI for Ubuntu 22.04 / Xilinx Yocto
# ============================================================

# Palette
BG = "#17191F"
SIDEBAR = "#1D2028"
PANEL = "#222630"
PANEL_ALT = "#292E3A"
INPUT = "#151820"
BORDER = "#353B49"
ORANGE = "#F06432"
ORANGE_HOVER = "#D94F20"
GREEN = "#2EAD72"
GREEN_HOVER = "#23885A"
RED = "#F16D75"
TEXT = "#F1F3F8"
MUTED = "#A0A8B8"
TERMINAL_BG = "#101217"
BLUE = "#6EA8FE"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

def require_sudo():
    # Check if the current User ID is 0 (which means 'root')
    if os.getuid() != 0:
        print("This script requires root privileges. Restarting with sudo...")
        # Replace the current process by relaunching the script with sudo
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)
            
            
class YoctoBuilderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Yocto Build Studio | UniCA")
        self.geometry("1180x860")
        self.minsize(760, 620)
        self.configure(fg_color=BG)

        self.is_building = False
        self.busy_tasks = set()
        self.detected_layers = {}  # path -> BooleanVar
        self.available_boards = {"Zynq Ultrascale+": [], "Zynq 7000": []}
        self.ui_queue = queue.Queue()
        self.current_page = "setup"
        self._last_responsive_mode = None

        script_dir = Path(__file__).resolve().parent
        self.yocto_dir = str(script_dir / "yocto")

        self.font_title = ctk.CTkFont(family="Ubuntu", size=22, weight="bold")
        self.font_heading = ctk.CTkFont(family="Ubuntu", size=15, weight="bold")
        self.font_body = ctk.CTkFont(family="Ubuntu", size=13)
        self.font_bold = ctk.CTkFont(family="Ubuntu", size=13, weight="bold")
        self.font_small = ctk.CTkFont(family="Ubuntu", size=11)
        self.font_mono = ctk.CTkFont(family="Ubuntu Mono", size=12)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=3, minsize=300)
        self.grid_rowconfigure(1, weight=2, minsize=170)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._build_sidebar()
        self._build_main_area()
        self._build_terminal()
        self._show_page("setup")
        self.scan_and_update_boards()
        self.after(80, self._poll_ui_queue)
        self.bind("<Configure>", self._on_window_resize)

    # ------------------------- Shell / layout -------------------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=225, corner_radius=0, fg_color=SIDEBAR)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(7, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=(24, 26), sticky="ew")
        ctk.CTkFrame(brand, width=5, height=38, corner_radius=3, fg_color=ORANGE).pack(
            side="left", padx=(0, 11)
        )
        title_box = ctk.CTkFrame(brand, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(title_box, text="YOCTO", font=ctk.CTkFont(family="Ubuntu", size=19, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(title_box, text="BUILD STUDIO", font=ctk.CTkFont(family="Ubuntu", size=10, weight="bold"),
                     text_color=ORANGE).pack(anchor="w", pady=(0, 1))

        ctk.CTkLabel(self.sidebar, text="WORKSPACE", font=self.font_small,
                     text_color=MUTED).grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")
        self.nav_setup = self._nav_button("01", "Environment Setup", lambda: self._show_page("setup"))
        self.nav_setup.grid(row=2, column=0, padx=10, pady=3, sticky="ew")
        self.nav_build = self._nav_button("02", "Configuration & Build", lambda: self._show_page("build"))
        self.nav_build.grid(row=3, column=0, padx=10, pady=3, sticky="ew")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).grid(
            row=4, column=0, padx=18, pady=20, sticky="ew"
        )
        ctk.CTkLabel(self.sidebar, text="QUICK INFO", font=self.font_small,
                     text_color=MUTED).grid(row=5, column=0, padx=20, pady=(0, 8), sticky="w")
        info = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=10)
        info.grid(row=6, column=0, padx=14, pady=0, sticky="ew")
        ctk.CTkLabel(info, text="Target release", font=self.font_small, text_color=MUTED).pack(
            anchor="w", padx=12, pady=(11, 2)
        )
        ctk.CTkLabel(info, text="Xilinx 2023.2", font=self.font_bold, text_color=TEXT).pack(
            anchor="w", padx=12, pady=(0, 10)
        )
        ctk.CTkLabel(self.sidebar, text="UniCA • Embedded Linux", font=self.font_small,
                     text_color="#727B8D").grid(row=8, column=0, padx=18, pady=18, sticky="sw")

    def _nav_button(self, number, label, command):
        btn = ctk.CTkButton(
            self.sidebar, text=f"  {number}    {label}", anchor="w", height=42,
            corner_radius=8, font=self.font_body, fg_color="transparent",
            hover_color=PANEL_ALT, text_color=MUTED, command=command
        )
        return btn

    def _build_main_area(self):
        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self.main, fg_color=BG, corner_radius=0)
        self.topbar.grid(row=0, column=0, padx=24, pady=(20, 10), sticky="ew")
        self.topbar.grid_columnconfigure(0, weight=1)
        title_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")
        self.page_title = ctk.CTkLabel(title_frame, text="Environment Setup", font=self.font_title, text_color=TEXT)
        self.page_title.pack(anchor="w")
        self.page_subtitle = ctk.CTkLabel(
            title_frame, text="Prepare the host, sync Xilinx sources and manage Yocto layers.",
            font=self.font_body, text_color=MUTED
        )
        self.page_subtitle.pack(anchor="w", pady=(3, 0))

        self.status_pill = ctk.CTkLabel(
            self.topbar, text="●  READY", font=self.font_small, text_color=GREEN,
            fg_color=PANEL, corner_radius=8, width=118, height=34
        )
        self.status_pill.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.page_host = ctk.CTkFrame(self.main, fg_color="transparent", corner_radius=0)
        self.page_host.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="nsew")
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)

        self.setup_page = ctk.CTkScrollableFrame(
            self.page_host, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=ORANGE
        )
        self.setup_page.grid_columnconfigure(0, weight=1)

        self.build_page = ctk.CTkScrollableFrame(
            self.page_host, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=ORANGE
        )
        self.build_page.grid_columnconfigure((0, 1), weight=1, uniform="buildcols")

        self._build_setup_page()
        self._build_build_page()

    def _build_terminal(self):
        self.terminal_card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12,
                                          border_width=1, border_color=BORDER)
        self.terminal_card.grid(row=1, column=1, padx=20, pady=(0, 18), sticky="nsew")
        self.terminal_card.grid_columnconfigure(0, weight=1)
        self.terminal_card.grid_rowconfigure(1, weight=1)
        self.terminal_header = ctk.CTkFrame(self.terminal_card, fg_color="transparent")
        self.terminal_header.grid(row=0, column=0, padx=14, pady=(9, 5), sticky="ew")
        self.terminal_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.terminal_header, text="TERMINAL OUTPUT",
                     font=self.font_small, text_color=MUTED).grid(row=0, column=0, sticky="w")
        self.terminal_status = ctk.CTkLabel(self.terminal_header, text="● IDLE",
                                             font=self.font_small, text_color=GREEN)
        self.terminal_status.grid(row=0, column=1, padx=(8, 14), sticky="e")
        ctk.CTkButton(self.terminal_header, text="Clear", width=64, height=26,
                      font=self.font_small, fg_color=PANEL_ALT, hover_color=BORDER,
                      command=self.clear_console).grid(row=0, column=2, sticky="e")
        self.console = ctk.CTkTextbox(
            self.terminal_card, font=self.font_mono, fg_color=TERMINAL_BG,
            text_color="#DCE2EE", corner_radius=8, border_width=1, border_color="#272C36",
            wrap="word"
        )
        self.console.grid(row=1, column=0, padx=12, pady=(2, 12), sticky="nsew")

        # Allow dragging the separator between main content and terminal.
        self._split_drag_start = None
        self.terminal_card.bind("<ButtonPress-1>", self._start_split_drag)
        self.terminal_card.bind("<B1-Motion>", self._drag_split)
        self.terminal_header.bind("<ButtonPress-1>", self._start_split_drag)
        self.terminal_header.bind("<B1-Motion>", self._drag_split)

    def _start_split_drag(self, event):
        self._split_drag_start = event.y_root

    def _drag_split(self, event):
        if self._split_drag_start is None:
            return
        delta = self._split_drag_start - event.y_root
        current = self.terminal_card.winfo_height()
        new_height = max(130, min(420, current + delta))
        self.grid_rowconfigure(0, weight=1, minsize=300)
        self.grid_rowconfigure(1, weight=0, minsize=new_height)
        self._split_drag_start = event.y_root

    def _on_window_resize(self, event):
        if event.widget is not self:
            return
        width = event.width
        mode = "compact" if width < 1050 else "wide"
        if mode != self._last_responsive_mode:
            self._last_responsive_mode = mode
            if hasattr(self, "build_page"):
                self._apply_responsive_layout(mode)

    def _apply_responsive_layout(self, mode):
        # Re-grid build cards in one column on narrow windows.
        if not hasattr(self, "hw_card"):
            return
        if mode == "compact":
            self.build_page.grid_columnconfigure((0, 1), weight=1, uniform="")
            self.hw_card.grid_configure(row=0, column=0, columnspan=2, padx=4, pady=5, sticky="ew")
            self.stack_card.grid_configure(row=1, column=0, columnspan=2, padx=4, pady=5, sticky="ew")
            self.summary_card.grid_configure(row=2, column=0, columnspan=2, padx=4, pady=5, sticky="ew")
        else:
            self.build_page.grid_columnconfigure((0, 1), weight=1, uniform="buildcols")
            self.hw_card.grid_configure(row=0, column=0, columnspan=1, padx=(4, 6), pady=6, sticky="nsew")
            self.stack_card.grid_configure(row=0, column=1, columnspan=1, padx=(6, 4), pady=6, sticky="nsew")
            self.summary_card.grid_configure(row=1, column=0, columnspan=2, padx=4, pady=(6, 4), sticky="ew")

    # ------------------------- Page: setup -------------------------
    def _build_setup_page(self):
        self.setup_page.grid_columnconfigure(0, weight=1)

        ws = self._card(self.setup_page)
        ws.grid(row=0, column=0, padx=2, pady=(2, 8), sticky="ew")
        ws.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ws, text="Workspace directory", font=self.font_heading, text_color=TEXT).grid(
            row=0, column=0, padx=16, pady=(13, 4), sticky="w"
        )
        ctk.CTkLabel(ws, text="Root directory for the Xilinx Yocto sources",
                     font=self.font_small, text_color=MUTED).grid(
            row=1, column=0, padx=16, pady=(0, 12), sticky="w"
        )
        self.dir_entry = ctk.CTkEntry(ws, font=self.font_body, fg_color=INPUT,
                                      border_color=BORDER, height=36)
        self.dir_entry.insert(0, self.yocto_dir)
        self.dir_entry.grid(row=0, column=1, rowspan=2, padx=(12, 8), pady=12, sticky="ew")
        ctk.CTkButton(ws, text="Browse", width=86, height=36, font=self.font_body,
                      fg_color=PANEL_ALT, hover_color=BORDER, command=self.browse_workspace_dir).grid(
            row=0, column=2, rowspan=2, padx=(0, 14), pady=12
        )

        self.btn_deps = self._step_card(
            self.setup_page, 1, "01", "Host dependencies",
            "Install the packages required to build Yocto Langdale on Ubuntu 22.04.",
            "Install system libraries", self.start_install_deps
        )
        self.btn_repo = self._step_card(
            self.setup_page, 2, "02", "Xilinx BSP & manifest sync",
            "Initialize the workspace and fetch official Xilinx layers from rel-v2023.2.",
            "Initialize workspace & sync", self.start_repo_setup
        )

        layer_card = self._card(self.setup_page)
        layer_card.grid(row=3, column=0, padx=2, pady=6, sticky="ew")
        layer_card.grid_columnconfigure(0, weight=1)
        self._section_heading(layer_card, "03", "Custom layers manager",
                              "Import a ZIP archive or Git repository, then select layers to register.")
        import_row = ctk.CTkFrame(layer_card, fg_color="transparent")
        import_row.grid(row=2, column=0, padx=16, pady=(8, 10), sticky="ew")
        import_row.grid_columnconfigure(0, weight=1)
        self.custom_layer_entry = ctk.CTkEntry(
            import_row, placeholder_text="Path to .zip archive or Git URL",
            font=self.font_body, fg_color=INPUT, border_color=BORDER, height=36
        )
        self.custom_layer_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(import_row, text="Browse ZIP", width=94, height=36, font=self.font_body,
                      fg_color=PANEL_ALT, hover_color=BORDER, command=self.browse_zip_file).grid(
            row=0, column=1, padx=(0, 8)
        )
        self.btn_import_layer = ctk.CTkButton(
            import_row, text="Import", width=78, height=36, font=self.font_bold,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.start_layer_import
        )
        self.btn_import_layer.grid(row=0, column=2)

        self.layers_scroll_frame = ctk.CTkScrollableFrame(
            layer_card, height=135, label_text="Detected layers",
            label_font=self.font_small, fg_color=TERMINAL_BG,
            border_width=1, border_color=BORDER
        )
        self.layers_scroll_frame.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.btn_apply_bblayers = ctk.CTkButton(
            layer_card, text="Apply selected layers to bblayers.conf", height=38,
            font=self.font_bold, fg_color=GREEN, hover_color=GREEN_HOVER,
            command=self.start_apply_bblayers
        )
        self.btn_apply_bblayers.grid(row=4, column=0, padx=16, pady=(0, 15), sticky="ew")

    def _step_card(self, parent, row, number, title, description, button_text, command):
        card = self._card(parent)
        card.grid(row=row, column=0, padx=2, pady=6, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._section_heading(card, number, title, description)
        btn = ctk.CTkButton(
            card, text=button_text, height=38, font=self.font_bold,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=command
        )
        btn.grid(row=2, column=0, padx=16, pady=(6, 14), sticky="ew")
        return btn

    # ------------------------- Page: build -------------------------
    def _build_build_page(self):
        self.build_page.grid_columnconfigure((0, 1), weight=1, uniform="buildcols")

        self.hw_card = self._card(self.build_page)
        self.hw_card.grid(row=0, column=0, padx=(2, 6), pady=5, sticky="nsew")
        self.hw_card.grid_columnconfigure(0, weight=1)
        self._section_heading(self.hw_card, "01", "Hardware target",
                              "Choose the architecture and machine configuration.")
        ctk.CTkLabel(self.hw_card, text="Architecture family", font=self.font_bold,
                     text_color=TEXT).grid(row=2, column=0, padx=16, pady=(8, 5), sticky="w")
        self.family_var = ctk.StringVar(value="Zynq Ultrascale+")
        self.rb_ultra = ctk.CTkRadioButton(
            self.hw_card, text="Zynq UltraScale+ · 64-bit ARM Cortex-A53",
            variable=self.family_var, value="Zynq Ultrascale+", font=self.font_body,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.on_family_change
        )
        self.rb_ultra.grid(row=3, column=0, padx=18, pady=5, sticky="w")
        self.rb_zynq7 = ctk.CTkRadioButton(
            self.hw_card, text="Zynq-7000 · 32-bit ARM Cortex-A9",
            variable=self.family_var, value="Zynq 7000", font=self.font_body,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.on_family_change
        )
        self.rb_zynq7.grid(row=4, column=0, padx=18, pady=5, sticky="w")
        ctk.CTkFrame(self.hw_card, height=1, fg_color=BORDER).grid(
            row=5, column=0, padx=16, pady=12, sticky="ew"
        )
        ctk.CTkLabel(self.hw_card, text="Target machine", font=self.font_bold,
                     text_color=TEXT).grid(row=6, column=0, padx=16, pady=(0, 5), sticky="w")
        board_row = ctk.CTkFrame(self.hw_card, fg_color="transparent")
        board_row.grid(row=7, column=0, padx=16, pady=(0, 15), sticky="ew")
        board_row.grid_columnconfigure(0, weight=1)
        self.board_var = ctk.StringVar(value="No boards found")
        self.board_dropdown = ctk.CTkOptionMenu(
            board_row, variable=self.board_var, font=self.font_body,
            fg_color=PANEL_ALT, button_color=ORANGE, button_hover_color=ORANGE_HOVER,
            height=36, command=self.on_board_change
        )
        self.board_dropdown.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(board_row, text="↻", width=40, height=36, font=self.font_bold,
                      fg_color=PANEL_ALT, hover_color=BORDER,
                      command=self.scan_and_update_boards).grid(row=0, column=1)

        self.stack_card = self._card(self.build_page)
        self.stack_card.grid(row=0, column=1, padx=(6, 2), pady=5, sticky="nsew")
        self.stack_card.grid_columnconfigure(0, weight=1)
        self._section_heading(self.stack_card, "02", "UniCA custom stack",
                              "Choose the image stack and optional Kubernetes runtime.")
        self.chk_unica_stack_var = ctk.BooleanVar(value=True)
        self.chk_unica_stack = ctk.CTkCheckBox(
            self.stack_card, text="Enable custom UniCA stack",
            variable=self.chk_unica_stack_var, font=self.font_bold,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.update_stack_ui_state
        )
        self.chk_unica_stack.grid(row=2, column=0, padx=16, pady=(8, 3), sticky="w")
        self.lbl_stack_hint = ctk.CTkLabel(
            self.stack_card, text="Custom image stack enabled.",
            font=self.font_small, text_color=MUTED, wraplength=330, justify="left"
        )
        self.lbl_stack_hint.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="w")
        ctk.CTkFrame(self.stack_card, height=1, fg_color=BORDER).grid(
            row=4, column=0, padx=16, pady=4, sticky="ew"
        )
        self.stack_var = ctk.StringVar(value="AXIDMA")
        self.rb_axidma = ctk.CTkRadioButton(
            self.stack_card, text="AXIDMA driver & FPGA bitstream",
            variable=self.stack_var, value="AXIDMA", font=self.font_body,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.update_build_summary
        )
        self.rb_axidma.grid(row=5, column=0, padx=18, pady=6, sticky="w")
        self.rb_vitis = ctk.CTkRadioButton(
            self.stack_card, text="Vitis AI runtime & DPU libraries",
            variable=self.stack_var, value="Vitis AI", font=self.font_body,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.update_build_summary
        )
        self.rb_vitis.grid(row=6, column=0, padx=18, pady=6, sticky="w")
        self.chk_k3s_var = ctk.BooleanVar(value=False)
        self.chk_k3s = ctk.CTkCheckBox(
            self.stack_card, text="Include K3s (lightweight Kubernetes)",
            variable=self.chk_k3s_var, font=self.font_body,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, command=self.update_build_summary
        )
        self.chk_k3s.grid(row=7, column=0, padx=18, pady=(12, 16), sticky="w")

        self.summary_card = self._card(self.build_page)
        self.summary_card.grid(row=1, column=0, columnspan=2, padx=2, pady=(7, 3), sticky="ew")
        self.summary_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.summary_card, text="BUILD TARGET SUMMARY",
                     font=self.font_small, text_color=MUTED).grid(
            row=0, column=0, padx=16, pady=(13, 4), sticky="w"
        )
        self.lbl_summary_value = ctk.CTkLabel(
            self.summary_card, text="MACHINE: —  |  IMAGE: —",
            font=self.font_mono, text_color=TEXT, wraplength=680, justify="left"
        )
        self.lbl_summary_value.grid(row=1, column=0, padx=16, pady=(0, 13), sticky="w")
        self.build_btn = ctk.CTkButton(
            self.summary_card, text="▶  START BITBAKE BUILD", width=230, height=42,
            font=self.font_bold, fg_color=GREEN, hover_color=GREEN_HOVER,
            command=self.start_build_thread
        )
        self.build_btn.grid(row=0, column=1, rowspan=2, padx=16, pady=12, sticky="e")

    # ------------------------- UI helpers -------------------------
    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=12,
                            border_width=1, border_color=BORDER)

    def _section_heading(self, parent, number, title, description):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(13, 0), sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text=number, font=ctk.CTkFont(family="Ubuntu", size=11, weight="bold"),
                     text_color=ORANGE, fg_color="#3A2927", corner_radius=6,
                     width=32, height=28).grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky="nw")
        ctk.CTkLabel(top, text=title, font=self.font_heading, text_color=TEXT).grid(
            row=0, column=1, sticky="w"
        )
        ctk.CTkLabel(top, text=description, font=self.font_small, text_color=MUTED,
                     wraplength=650, justify="left").grid(row=1, column=1, pady=(3, 0), sticky="w")

    def _show_page(self, page):
        self.current_page = page
        self.setup_page.grid_remove()
        self.build_page.grid_remove()
        if page == "setup":
            self.setup_page.grid(row=0, column=0, sticky="nsew")
            self.page_title.configure(text="Environment Setup")
            self.page_subtitle.configure(text="Prepare the host, sync Xilinx sources and manage Yocto layers.")
            self.nav_setup.configure(fg_color="#34303A", text_color=TEXT)
            self.nav_build.configure(fg_color="transparent", text_color=MUTED)
        else:
            self.build_page.grid(row=0, column=0, sticky="nsew")
            self.page_title.configure(text="Configuration & Build")
            self.page_subtitle.configure(text="Select your hardware target, image stack and build configuration.")
            self.nav_setup.configure(fg_color="transparent", text_color=MUTED)
            self.nav_build.configure(fg_color="#34303A", text_color=TEXT)
            self.scan_and_update_boards()
        self._apply_responsive_layout(self._last_responsive_mode or ("compact" if self.winfo_width() < 1050 else "wide"))

    def set_status(self, text, color=GREEN):
        self.status_pill.configure(text=f"●  {text}", text_color=color)

    def clear_console(self):
        self.console.delete("1.0", "end")

    def log_to_console(self, text):
        # Thread-safe: workers enqueue messages; Tk updates happen in main thread.
        self.ui_queue.put(("log", str(text)))

    def _poll_ui_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self.console.insert("end", item[1])
                    self.console.see("end")
                elif kind == "call":
                    item[1]()
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(80, self._poll_ui_queue)

    def ui_call(self, callback):
        self.ui_queue.put(("call", callback))

    def run_task(self, name, button, busy_text, worker):
        if name in self.busy_tasks:
            return
        self.busy_tasks.add(name)
        button.configure(state="disabled", text=busy_text)
        self.set_status("WORKING", ORANGE)

        def runner():
            try:
                worker()
            except Exception as exc:
                self.log_to_console(f"\n[ERROR] {name}: {exc}\n")
            finally:
                self.busy_tasks.discard(name)
                self.ui_call(lambda: self._task_finished(name, button))
        threading.Thread(target=runner, daemon=True).start()

    def _task_finished(self, name, button):
        defaults = {
            "dependencies": (self.btn_deps, "Install system libraries"),
            "repo": (self.btn_repo, "Initialize workspace & sync"),
            "import": (self.btn_import_layer, "Import"),
            "layers": (self.btn_apply_bblayers, "Apply selected layers to bblayers.conf"),
        }
        if name in defaults:
            target, text = defaults[name]
            if name not in self.busy_tasks:
                target.configure(state="normal", text=text)
        if not self.is_building and not self.busy_tasks:
            self.set_status("READY", GREEN)

    # ------------------------- File pickers -------------------------
    def browse_workspace_dir(self):
        selected = filedialog.askdirectory(title="Select Yocto workspace directory")
        if selected:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, selected)
            self.yocto_dir = os.path.expanduser(selected)
            self.scan_and_update_boards()

    def browse_zip_file(self):
        selected = filedialog.askopenfilename(
            title="Select custom layer ZIP archive",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")]
        )
        if selected:
            self.custom_layer_entry.delete(0, "end")
            self.custom_layer_entry.insert(0, selected)

    def on_closing(self):
        if self.is_building or self.busy_tasks:
            if not messagebox.askokcancel(
                "Quit", "A task is running. Closing the window may interrupt it. Exit anyway?"
            ):
                return
        self.destroy()

    # ------------------------- Board detection and image selection -------------------------
    def scan_and_update_boards(self):
        if not hasattr(self, "dir_entry"):
            return
        self.yocto_dir = os.path.expanduser(self.dir_entry.get().strip() or self.yocto_dir)
        boards = {"Zynq Ultrascale+": [], "Zynq 7000": []}
        search_path = os.path.join(self.yocto_dir, "sources")
        if os.path.isdir(search_path):
            dyn_zynqmp, dyn_zynq7 = set(), set()
            for root, dirs, files in os.walk(search_path):
                if os.path.basename(root) == "machine" and os.path.basename(os.path.dirname(root)) == "conf":
                    for filename in files:
                        if not filename.endswith(".conf"):
                            continue
                        machine = filename[:-5]
                        if any(key in machine.lower() for key in ("zynqmp", "k26", "kr260", "kv260", "zcu", "ultra")):
                            dyn_zynqmp.add(machine)
                        elif any(key in machine.lower() for key in ("zynq7", "zc7", "pynq", "zed", "microzed")):
                            dyn_zynq7.add(machine)
            boards["Zynq Ultrascale+"] = sorted(dyn_zynqmp)
            boards["Zynq 7000"] = sorted(dyn_zynq7)
        self.available_boards = boards
        self.on_family_change()

    def on_family_change(self):
        family = self.family_var.get()
        board_list = self.available_boards.get(family, [])
        if board_list:
            self.board_dropdown.configure(values=board_list)
            preferred = "k26-smk-kv" if family == "Zynq Ultrascale+" else "zedboard-zynq7"
            self.board_var.set(preferred if preferred in board_list else board_list[0])
        else:
            self.board_dropdown.configure(values=["No boards found"])
            self.board_var.set("No boards found")
        self.on_board_change(self.board_var.get())

    def on_board_change(self, selected_board=None):
        if selected_board is None:
            selected_board = self.board_var.get()
        family = self.family_var.get()
        if selected_board == "No boards found":
            self.chk_unica_stack_var.set(False)
            self.chk_unica_stack.configure(state="disabled")
            self.lbl_stack_hint.configure(text="No machines detected in workspace/sources.")
        elif family == "Zynq 7000":
            if selected_board == "zedboard-zynq7":
                self.chk_unica_stack.configure(state="normal")
                self.chk_unica_stack_var.set(True)
                self.lbl_stack_hint.configure(text="Custom stack enabled for Zedboard. Uncheck for the standard image.")
            else:
                self.chk_unica_stack_var.set(False)
                self.chk_unica_stack.configure(state="disabled")
                self.lbl_stack_hint.configure(text=f"Custom stack is not enabled for '{selected_board}'. Using standard image.")
        else:
            self.chk_unica_stack.configure(state="normal")
            self.chk_unica_stack_var.set(True)
            self.lbl_stack_hint.configure(text="Custom stack enabled. Uncheck to use petalinux-image-minimal.")
        self.update_stack_ui_state()

    def update_stack_ui_state(self):
        use_custom = self.chk_unica_stack_var.get()
        family = self.family_var.get()
        if use_custom:
            self.rb_axidma.configure(state="normal")
            self.rb_vitis.configure(state="normal" if family == "Zynq Ultrascale+" else "disabled")
            if family == "Zynq 7000":
                self.stack_var.set("AXIDMA")
            self.chk_k3s.configure(state="normal")
        else:
            self.rb_axidma.configure(state="disabled")
            self.rb_vitis.configure(state="disabled")
            self.chk_k3s.configure(state="disabled")
        self.update_build_summary()

    def determine_image_and_machine(self):
        machine = self.board_var.get()
        family = self.family_var.get()
        if not self.chk_unica_stack_var.get():
            return machine, "petalinux-image-minimal"
        stack = self.stack_var.get()
        k3s = self.chk_k3s_var.get()
        if family == "Zynq Ultrascale+":
            if stack == "Vitis AI":
                image = "k3s-vitis-ai-image" if k3s else "vitis-ai-image"
            else:
                image = "k3s-axi-dma-image" if k3s else "axi-dma-image"
        else:
            image = "k3s-axi-dma-image-zynq7" if k3s else "axi-dma-image-zynq7"
        return machine, image

    def update_build_summary(self):
        if not hasattr(self, "lbl_summary_value"):
            return
        machine, image = self.determine_image_and_machine()
        if machine == "No boards found":
            self.lbl_summary_value.configure(
                text="MACHINE: None (sync/import layers first)  |  IMAGE: —", text_color=RED
            )
            self.build_btn.configure(state="disabled")
        else:
            mode = "Custom stack" if self.chk_unica_stack_var.get() else "Standard image"
            self.lbl_summary_value.configure(
                text=f"MACHINE: {machine}   |   IMAGE: {image}   |   {mode}", text_color=TEXT
            )
            if not self.is_building:
                self.build_btn.configure(state="normal")

    # ------------------------- Step 1: dependencies -------------------------
    def start_install_deps(self):
        self.run_task("dependencies", self.btn_deps, "Installing…", self.run_install_deps)

    def run_install_deps(self):
        self.log_to_console("\n=== STEP 1: UBUNTU SYSTEM DEPENDENCIES ===\n")
        packages = (
            "gawk wget git diffstat unzip texinfo gcc build-essential chrpath socat cpio "
            "python3 python3-pip python3-pexpect xz-utils debianutils iputils-ping "
            "python3-git python3-jinja2 libegl1-mesa libsdl1.2-dev python3-subunit "
            "zstd libssl-dev locales"
        )
        # Interactive sudo is intentional: apt may request the user's password.
        code = self.run_process(["bash", "-lc", f"sudo apt update && sudo apt install -y {packages}"])
        if code == 0:
            self.log_to_console("\n[SUCCESS] System dependencies installed.\n")
            self.ui_call(lambda: self.btn_deps.configure(text="Dependencies installed ✓", fg_color=GREEN))
        else:
            self.log_to_console(f"\n[ERROR] Dependency installation failed (exit {code}).\n")

    # ------------------------- Step 2: repo sync -------------------------
    def start_repo_setup(self):
        self.yocto_dir = os.path.expanduser(self.dir_entry.get().strip() or self.yocto_dir)
        self.run_task("repo", self.btn_repo, "Syncing repositories…", self.run_repo_setup)

    def run_repo_setup(self):
        self.log_to_console("\n=== STEP 2: WORKSPACE INITIALIZATION & REPO SYNC ===\n")
        os.makedirs(self.yocto_dir, exist_ok=True)
        bin_dir = os.path.expanduser("~/.local/bin")
        os.makedirs(bin_dir, exist_ok=True)
        repo_path = os.path.join(bin_dir, "repo")
        if not os.path.isfile(repo_path):
            self.log_to_console("Downloading Google repo tool…\n")
            code = self.run_process([
                "bash", "-lc",
                f"curl -fL https://storage.googleapis.com/git-repo-downloads/repo -o {self._quote(repo_path)} "
                f"&& chmod a+x {self._quote(repo_path)}"
            ])
            if code != 0:
                self.log_to_console("[ERROR] Could not download repo tool.\n")
                return
        release = "rel-v2023.2"
        commands = [
            os.path.join(bin_dir, "repo"), "init",
            "-u", "https://github.com/Xilinx/yocto-manifests.git", "-b", release
        ]
        code = self.run_process(commands, cwd=self.yocto_dir, extra_env={"PATH": bin_dir + os.pathsep + os.environ.get("PATH", "")})
        if code == 0:
            code = self.run_process(
                [os.path.join(bin_dir, "repo"), "sync"],
                cwd=self.yocto_dir,
                extra_env={"PATH": bin_dir + os.pathsep + os.environ.get("PATH", "")}
            )
        if code == 0:
            code = self.run_process(
                [os.path.join(bin_dir, "repo"), "start", release, "--all"],
                cwd=self.yocto_dir,
                extra_env={"PATH": bin_dir + os.pathsep + os.environ.get("PATH", "")}
            )
        if code == 0:
            self.log_to_console("\n[SUCCESS] Workspace initialized and Xilinx layers fetched.\n")
            self.ui_call(self.scan_and_update_boards)
            self.ui_call(lambda: self.btn_repo.configure(text="Workspace ready ✓", fg_color=GREEN))
        else:
            self.log_to_console(f"\n[ERROR] Repo sync failed (exit {code}).\n")

    # ------------------------- Step 3: import layers -------------------------
    def start_layer_import(self):
        self.yocto_dir = os.path.expanduser(self.dir_entry.get().strip() or self.yocto_dir)
        self._pending_layer_source = self.custom_layer_entry.get().strip()
        self.run_task("import", self.btn_import_layer, "Importing…", self.run_layer_import)

    def run_layer_import(self):
        self.log_to_console("\n=== STEP 3: IMPORTING CUSTOM LAYER ===\n")
        sources_dir = os.path.join(self.yocto_dir, "sources")
        os.makedirs(sources_dir, exist_ok=True)
        layer_source = self._pending_layer_source
        if not layer_source:
            self.log_to_console("[ERROR] Enter a ZIP path or Git URL first.\n")
            return

        is_url = layer_source.startswith(("https://", "http://", "git@"))
        if is_url:
            repo_name = layer_source.rstrip("/").split("/")[-1]
            folder_name = repo_name[:-4] if repo_name.endswith(".git") else repo_name
        else:
            folder_name = os.path.basename(layer_source)
            if folder_name.lower().endswith(".zip"):
                folder_name = folder_name[:-4]
        folder_name = re.sub(r"[^A-Za-z0-9._-]", "_", folder_name)
        if not folder_name or folder_name in (".", ".."):
            self.log_to_console("[ERROR] Could not determine a safe layer directory name.\n")
            return
        target = os.path.abspath(os.path.join(sources_dir, folder_name))
        if os.path.commonpath([os.path.abspath(sources_dir), target]) != os.path.abspath(sources_dir):
            self.log_to_console("[ERROR] Invalid layer destination.\n")
            return

        if not is_url and os.path.isfile(layer_source) and layer_source.lower().endswith(".zip"):
            temp_dir = os.path.join(sources_dir, "_temp_layer_extract")
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                os.makedirs(temp_dir)
                self.log_to_console(f"Extracting {layer_source}…\n")
                with zipfile.ZipFile(layer_source, "r") as archive:
                    # Prevent ZIP path traversal (Zip Slip).
                    base = os.path.abspath(temp_dir)
                    for member in archive.infolist():
                        dest = os.path.abspath(os.path.join(base, member.filename))
                        if os.path.commonpath([base, dest]) != base:
                            raise ValueError(f"Unsafe path in ZIP: {member.filename}")
                    archive.extractall(temp_dir)
                entries = [p for p in os.listdir(temp_dir) if not p.startswith(".")]
                source_dir = os.path.join(temp_dir, entries[0]) if len(entries) == 1 and os.path.isdir(os.path.join(temp_dir, entries[0])) else temp_dir
                if os.path.exists(target):
                    shutil.rmtree(target)
                if source_dir == temp_dir:
                    shutil.move(temp_dir, target)
                else:
                    shutil.move(source_dir, target)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                self.log_to_console(f"[SUCCESS] Extracted layer into {target}\n")
            except Exception as exc:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.log_to_console(f"[ERROR] ZIP extraction failed: {exc}\n")
                return
        elif is_url:
            if os.path.exists(target):
                self.log_to_console(f"Replacing existing directory {target}…\n")
                shutil.rmtree(target)
            self.log_to_console(f"Cloning {layer_source}…\n")
            code = self.run_process(["git", "clone", layer_source, target], cwd=sources_dir)
            if code != 0:
                self.log_to_console("[ERROR] Git clone failed.\n")
                return
        else:
            self.log_to_console(f"[ERROR] Invalid ZIP path or Git URL: {layer_source}\n")
            return

        self.scan_and_add_layers_to_ui(target)
        self.ui_call(lambda: self.custom_layer_entry.delete(0, "end"))
        self.ui_call(self.scan_and_update_boards)

    def scan_and_add_layers_to_ui(self, base_dir):
        self.log_to_console("Scanning for conf/layer.conf…\n")
        found = []
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
            if "layer.conf" in files and os.path.basename(root) == "conf":
                found.append(os.path.abspath(os.path.dirname(root)))
        if not found:
            self.log_to_console("[WARNING] No valid Yocto layer found in the imported source.\n")
            return
        for path in found:
            if path not in self.detected_layers:
                self.ui_call(lambda p=path: self._add_layer_checkbox(p))
        self.log_to_console(f"[SUCCESS] Found {len(found)} layer(s). Select the layers to register.\n")

    def _add_layer_checkbox(self, layer_path):
        if layer_path in self.detected_layers:
            return
        var = ctk.BooleanVar(value=True)
        self.detected_layers[layer_path] = var
        name = os.path.basename(layer_path)
        chk = ctk.CTkCheckBox(
            self.layers_scroll_frame, text=f"{name}  ·  {layer_path}",
            variable=var, font=self.font_small, text_color=TEXT,
            fg_color=ORANGE, hover_color=ORANGE_HOVER
        )
        chk.pack(anchor="w", padx=8, pady=5)

    def start_apply_bblayers(self):
        self.yocto_dir = os.path.expanduser(self.dir_entry.get().strip() or self.yocto_dir)
        self._pending_layers_to_add = [path for path, var in self.detected_layers.items() if var.get()]
        self._pending_layers_to_remove = [path for path, var in self.detected_layers.items() if not var.get()]
        self.run_task("layers", self.btn_apply_bblayers, "Applying layers…", self.run_apply_bblayers)

    def run_apply_bblayers(self):
        self.log_to_console("\n=== CONFIGURING BBLAYERS.CONF ===\n")
        setup_script = os.path.join(self.yocto_dir, "setupsdk")
        if not os.path.isfile(setup_script):
            self.log_to_console(f"[ERROR] Setup script not found: {setup_script}\n")
            return
        selected = self._pending_layers_to_add
        # Ensure BitBake environment is sourced in a single shell. Quote every path.
        layer_commands = []
        for path in selected:
            layer_commands.append(f"bitbake-layers add-layer {self._quote(path)}")
        for path in self._pending_layers_to_remove:
            layer_commands.append(f"bitbake-layers remove-layer {self._quote(path)} || true")
        script = " && ".join(layer_commands) if layer_commands else "true"
        command = f"source ./setupsdk && {script}"
        code = self.run_process(["bash", "-lc", command], cwd=self.yocto_dir)
        if code == 0:
            self.log_to_console("\n[SUCCESS] Selected layers applied to bblayers.conf.\n")
        else:
            self.log_to_console(f"\n[ERROR] Could not update bblayers.conf (exit {code}).\n")

    # ------------------------- BitBake build -------------------------
    def start_build_thread(self):
        machine, image = self.determine_image_and_machine()
        if machine == "No boards found":
            self.log_to_console("[ERROR] Cannot build: no machines found in workspace/sources.\n")
            return
        if self.is_building:
            return
        self.yocto_dir = os.path.expanduser(self.dir_entry.get().strip() or self.yocto_dir)
        if not os.path.isfile(os.path.join(self.yocto_dir, "setupsdk")):
            messagebox.showerror("Build unavailable", "The setup script 'setupsdk' was not found in the workspace.")
            return
        self.is_building = True
        self.build_btn.configure(state="disabled", text="⏳  BUILDING IMAGE…")
        self.set_status("BUILDING", ORANGE)
        self.terminal_status.configure(text="● BUILDING", text_color=ORANGE)
        self.log_to_console("\n" + "=" * 58 + "\n")
        self.log_to_console("STARTING BITBAKE BUILD\n")
        self.log_to_console(f"Workspace : {self.yocto_dir}\n")
        self.log_to_console(f"Family    : {self.family_var.get()}\n")
        self.log_to_console(f"MACHINE   : {machine}\n")
        self.log_to_console(f"Target    : {image}\n")
        self.log_to_console("=" * 58 + "\n\n")
        threading.Thread(target=self.run_bitbake, args=(machine, image), daemon=True).start()

    def run_bitbake(self, machine, image):
        try:
            command = f"source ./setupsdk && export MACHINE={self._quote(machine)} && bitbake {self._quote(image)}"
            code = self.run_process(["bash", "-lc", command], cwd=self.yocto_dir)
            if code == 0:
                self.log_to_console("\n" + "=" * 58 + "\n[SUCCESS] BUILD COMPLETED SUCCESSFULLY\n" + "=" * 58 + "\n")
            else:
                self.log_to_console(f"\n[ERROR] BUILD FAILED (exit code {code})\n")
        finally:
            self.is_building = False
            self.ui_call(self._build_finished)

    def _build_finished(self):
        self.build_btn.configure(state="normal", text="▶  START BITBAKE BUILD")
        self.terminal_status.configure(text="● IDLE", text_color=GREEN)
        self.set_status("READY", GREEN)
        self.update_build_summary()

    # ------------------------- Process helpers -------------------------
    @staticmethod
    def _quote(value):
        # POSIX shell quoting for values used inside bash -lc command strings.
        return "'" + str(value).replace("'", "'\\''") + "'"

    def run_process(self, args, cwd=None, extra_env=None):
        try:
            env = os.environ.copy()
            if extra_env:
                env.update(extra_env)
            self.log_to_console("$ " + " ".join(self._quote(a) for a in args) + "\n")
            process = subprocess.Popen(
                args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            if process.stdout:
                for line in process.stdout:
                    self.log_to_console(line)
            return process.wait()
        except Exception as exc:
            self.log_to_console(f"\n[SYSTEM ERROR] {exc}\n")
            return -1
            

if __name__ == "__main__":
    require_sudo()
    app = YoctoBuilderApp()
    app.mainloop()

