import os
import sys
import threading
import subprocess
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

import downloader
import converter

# Estilo e Tema Aurora / Dawn
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
CONVERSIONS_DIR = os.path.join(BASE_DIR, "conversions")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(CONVERSIONS_DIR, exist_ok=True)

class YTDawnApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YTDawn — Portable Media Downloader & FFmpeg Converter")
        self.geometry("900x740")
        self.minsize(820, 660)
        self.configure(fg_color="#120e24")

        # Configurar Ícone da Janela
        ico_path = os.path.join(ASSETS_DIR, "icon.ico")
        png_path = os.path.join(ASSETS_DIR, "icon.png")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.is_busy = False
        self.current_mode = None  # 'download' ou 'convert'
        self.cancel_event = threading.Event()

        # Resolução máxima de download: 1080p (default) ou 720p
        self.dl_resolution_var = ctk.StringVar(value="1080p")

        # Compressão de download: None (default), Full ou Half
        self.dl_compression_var = ctk.StringVar(value="None")

        # Compressão na conversão: None (default - mantém tamanho original), Full ou Half
        self.conv_compression_var = ctk.StringVar(value="None")

        self.create_header(png_path)
        self.create_tabs()
        self.create_log_and_status_panel()

    def create_header(self, png_path):
        header_frame = ctk.CTkFrame(self, fg_color="#181332", corner_radius=12, height=96)
        header_frame.pack(fill="x", padx=16, pady=(12, 6))
        header_frame.pack_propagate(False)

        # Ícone Dawn
        if os.path.exists(png_path):
            try:
                pil_img = Image.open(png_path)
                dawn_icon = ctk.CTkImage(pil_img, size=(52, 52))
                icon_lbl = ctk.CTkLabel(header_frame, text="", image=dawn_icon)
                icon_lbl.pack(side="left", padx=(16, 12), pady=12)
            except Exception:
                pass

        # Textos de Título Aurora e Redes Suportadas
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True, pady=8)

        title_lbl = ctk.CTkLabel(
            title_box, 
            text="YTDawn", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#ff8c42"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box, 
            text="Portable Media Downloader & FFmpeg Converter", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#26d0ce"
        )
        subtitle_lbl.pack(anchor="w")

        # Badges das Redes Sociais Suportadas
        networks_frame = ctk.CTkFrame(title_box, fg_color="transparent")
        networks_frame.pack(anchor="w", pady=(2, 0))

        platforms = [
            ("YouTube", "#ff3333"),
            ("Instagram", "#e1306c"),
            ("TikTok", "#00f2fe"),
            ("Facebook", "#1877f2"),
            ("X / Twitter", "#1da1f2")
        ]

        for name, color in platforms:
            badge = ctk.CTkLabel(
                networks_frame,
                text=f" {name} ",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#ffffff",
                fg_color="#231a44",
                corner_radius=4
            )
            badge.pack(side="left", padx=(0, 4))

        # Botões do cabeçalho
        btn_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_box.pack(side="right", padx=16, pady=20)

        open_folder_btn = ctk.CTkButton(
            btn_box,
            text="📁 Abrir Pasta",
            width=105,
            height=32,
            corner_radius=8,
            fg_color="#2b204e",
            hover_color="#3e2e70",
            text_color="#26d0ce",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.open_base_folders
        )
        open_folder_btn.pack(side="right", padx=(6, 0))

        cookies_btn = ctk.CTkButton(
            btn_box,
            text="🍪 Cookies",
            width=85,
            height=32,
            corner_radius=8,
            fg_color="#2b204e",
            hover_color="#3e2e70",
            text_color="#ff8c42",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.import_cookies_file
        )
        cookies_btn.pack(side="right", padx=(6, 0))

        clear_cache_btn = ctk.CTkButton(
            btn_box,
            text="🧹 Limpar Cache",
            width=115,
            height=32,
            corner_radius=8,
            fg_color="#2b204e",
            hover_color="#3e2e70",
            text_color="#ffcc00",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.clean_app_cache
        )
        clear_cache_btn.pack(side="right")

    def create_tabs(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="#191436",
            segmented_button_fg_color="#100c22",
            segmented_button_selected_color="#ea3a8e",
            segmented_button_selected_hover_color="#c42872",
            segmented_button_unselected_color="#18132f",
            segmented_button_unselected_hover_color="#28204b",
            corner_radius=12
        )
        self.tabview.pack(fill="x", padx=16, pady=4)

        self.tab_download = self.tabview.add("Download")
        self.tab_convert = self.tabview.add("Conversão")

        self.setup_download_tab()
        self.setup_convert_tab()

    # ------------------ ABA 1: DOWNLOAD ------------------
    def setup_download_tab(self):
        frame = self.tab_download

        lbl = ctk.CTkLabel(
            frame, 
            text="Cole o link ou lista de links (YouTube, Instagram, TikTok, Facebook, X - um por linha):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7"
        )
        lbl.pack(anchor="w", padx=14, pady=(8, 2))

        self.txt_urls = ctk.CTkTextbox(
            frame, 
            height=85, 
            corner_radius=8, 
            fg_color="#100b21", 
            border_color="#342858", 
            border_width=1,
            text_color="#ffffff"
        )
        self.txt_urls.pack(fill="x", padx=14, pady=2)
        self.txt_urls.insert("1.0", "https://www.youtube.com/watch?v=...\n")

        # Linha 1: Formato + Resolução (1080p / 720p) + Compressão (None / Full / Half)
        opts_frame = ctk.CTkFrame(frame, fg_color="transparent")
        opts_frame.pack(fill="x", padx=14, pady=(6, 2))

        fmt_lbl = ctk.CTkLabel(opts_frame, text="Formato:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        fmt_lbl.pack(side="left", padx=(0, 6))

        self.combo_dl_format = ctk.CTkOptionMenu(
            opts_frame, 
            values=["MP4 (Vídeo)", "MP3 (Áudio)"],
            fg_color="#ea3a8e",
            button_color="#c42872",
            button_hover_color="#9e1857",
            dropdown_fg_color="#181332",
            corner_radius=8,
            width=115,
            command=self.on_dl_format_changed
        )
        self.combo_dl_format.set("MP4 (Vídeo)")
        self.combo_dl_format.pack(side="left", padx=(0, 14))

        # Check de Resolução: 1080p ou 720p
        self.lbl_dl_res = ctk.CTkLabel(opts_frame, text="Resolução:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        self.lbl_dl_res.pack(side="left", padx=(0, 6))

        self.radio_dl_1080 = ctk.CTkRadioButton(
            opts_frame,
            text="1080p",
            value="1080p",
            variable=self.dl_resolution_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#26d0ce",
            hover_color="#1eb5b3",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_dl_1080.pack(side="left", padx=(0, 8))

        self.radio_dl_720 = ctk.CTkRadioButton(
            opts_frame,
            text="720p",
            value="720p",
            variable=self.dl_resolution_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#26d0ce",
            hover_color="#1eb5b3",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_dl_720.pack(side="left", padx=(0, 16))

        # Check de Compressão: None, Full, Half
        self.lbl_dl_comp = ctk.CTkLabel(opts_frame, text="Compressão:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        self.lbl_dl_comp.pack(side="left", padx=(0, 6))

        self.radio_dl_comp_none = ctk.CTkRadioButton(
            opts_frame,
            text="None",
            value="None",
            variable=self.dl_compression_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#9d95c4",
            hover_color="#7b74a3",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_dl_comp_none.pack(side="left", padx=(0, 8))

        self.radio_dl_comp_full = ctk.CTkRadioButton(
            opts_frame,
            text="Full",
            value="Full",
            variable=self.dl_compression_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#ff8c42",
            hover_color="#e06e23",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_dl_comp_full.pack(side="left", padx=(0, 8))

        self.radio_dl_comp_half = ctk.CTkRadioButton(
            opts_frame,
            text="Half",
            value="Half",
            variable=self.dl_compression_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#ea3a8e",
            hover_color="#c42872",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_dl_comp_half.pack(side="left", padx=(0, 8))

        # Linha 2: Pasta de Saída
        dest_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dest_frame.pack(fill="x", padx=14, pady=(4, 6))

        self.dl_dir_var = ctk.StringVar(value=DOWNLOADS_DIR)
        dest_lbl = ctk.CTkLabel(dest_frame, text="Salvar em:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        dest_lbl.pack(side="left", padx=(0, 6))

        self.dl_dir_entry = ctk.CTkEntry(
            dest_frame, 
            textvariable=self.dl_dir_var, 
            fg_color="#100b21", 
            border_color="#342858",
            corner_radius=8
        )
        self.dl_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_dl = ctk.CTkButton(
            dest_frame, 
            text="Buscar", 
            width=65, 
            corner_radius=8,
            fg_color="#2b204e",
            hover_color="#3e2e70",
            command=self.browse_dl_folder
        )
        btn_browse_dl.pack(side="left")

        # Botão de Ação Download (Iniciar / Cancelar)
        self.btn_start_dl = ctk.CTkButton(
            frame,
            text="Iniciar download",
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#ff8c42",
            hover_color="#e06e23",
            corner_radius=8,
            command=self.toggle_download
        )
        self.btn_start_dl.pack(fill="x", padx=14, pady=(4, 8))

    def on_dl_format_changed(self, choice):
        state = "disabled" if "MP3" in choice else "normal"
        self.radio_dl_1080.configure(state=state)
        self.radio_dl_720.configure(state=state)
        self.radio_dl_comp_none.configure(state=state)
        self.radio_dl_comp_full.configure(state=state)
        self.radio_dl_comp_half.configure(state=state)

    # ------------------ ABA 2: CONVERSÃO ------------------
    def setup_convert_tab(self):
        frame = self.tab_convert

        lbl = ctk.CTkLabel(
            frame, 
            text="Selecione o arquivo de mídia local para conversão com FFmpeg:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7"
        )
        lbl.pack(anchor="w", padx=14, pady=(8, 2))

        # Seleção de Arquivo
        file_frame = ctk.CTkFrame(frame, fg_color="transparent")
        file_frame.pack(fill="x", padx=14, pady=2)

        self.convert_file_var = ctk.StringVar()
        self.entry_convert_file = ctk.CTkEntry(
            file_frame, 
            textvariable=self.convert_file_var, 
            placeholder_text="Nenhum arquivo selecionado...",
            fg_color="#100b21", 
            border_color="#342858",
            corner_radius=8
        )
        self.entry_convert_file.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_select_file = ctk.CTkButton(
            file_frame, 
            text="Selecionar Arquivo", 
            width=135, 
            corner_radius=8,
            fg_color="#26d0ce",
            hover_color="#1eb5b3",
            text_color="#0d1b2a",
            font=ctk.CTkFont(weight="bold"),
            command=self.select_convert_file
        )
        btn_select_file.pack(side="left")

        # Linha 1: Formato + Compressão na Conversão (None - tamanho original, Full, Half)
        opts_frame = ctk.CTkFrame(frame, fg_color="transparent")
        opts_frame.pack(fill="x", padx=14, pady=(6, 2))

        fmt_lbl = ctk.CTkLabel(opts_frame, text="Converter para:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        fmt_lbl.pack(side="left", padx=(0, 6))

        self.combo_conv_format = ctk.CTkOptionMenu(
            opts_frame, 
            values=["MP4", "MKV", "MP3", "WAV", "FLAC", "AAC", "OGG", "WEBM", "AVI", "GIF"],
            fg_color="#ea3a8e",
            button_color="#c42872",
            button_hover_color="#9e1857",
            dropdown_fg_color="#181332",
            corner_radius=8,
            width=100,
            command=self.on_conv_format_changed
        )
        self.combo_conv_format.set("MP4")
        self.combo_conv_format.pack(side="left", padx=(0, 16))

        # Check de Compressão na Conversão: None (default - mantém tamanho original), Full, Half
        self.lbl_conv_comp = ctk.CTkLabel(opts_frame, text="Compressão:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        self.lbl_conv_comp.pack(side="left", padx=(0, 8))

        self.radio_conv_comp_none = ctk.CTkRadioButton(
            opts_frame,
            text="None",
            value="None",
            variable=self.conv_compression_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#9d95c4",
            hover_color="#7b74a3",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_conv_comp_none.pack(side="left", padx=(0, 10))

        self.radio_conv_comp_full = ctk.CTkRadioButton(
            opts_frame,
            text="Full",
            value="Full",
            variable=self.conv_compression_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#ff8c42",
            hover_color="#e06e23",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_conv_comp_full.pack(side="left", padx=(0, 10))

        self.radio_conv_comp_half = ctk.CTkRadioButton(
            opts_frame,
            text="Half",
            value="Half",
            variable=self.conv_compression_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0daf7",
            fg_color="#ea3a8e",
            hover_color="#c42872",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_conv_comp_half.pack(side="left", padx=(0, 10))

        # Linha 2: Pasta de Saída Conversão
        dest_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dest_frame.pack(fill="x", padx=14, pady=(4, 6))

        self.conv_dir_var = ctk.StringVar(value=CONVERSIONS_DIR)
        dest_lbl = ctk.CTkLabel(dest_frame, text="Salvar em:", font=ctk.CTkFont(size=13), text_color="#c7bee6")
        dest_lbl.pack(side="left", padx=(0, 6))

        self.conv_dir_entry = ctk.CTkEntry(
            dest_frame, 
            textvariable=self.conv_dir_var, 
            fg_color="#100b21", 
            border_color="#342858",
            corner_radius=8
        )
        self.conv_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse_conv = ctk.CTkButton(
            dest_frame, 
            text="Buscar", 
            width=65, 
            corner_radius=8,
            fg_color="#2b204e",
            hover_color="#3e2e70",
            command=self.browse_conv_folder
        )
        btn_browse_conv.pack(side="left")

        # Botão de Ação Converter (Iniciar / Cancelar)
        self.btn_start_conv = ctk.CTkButton(
            frame,
            text="Iniciar conversão",
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#26d0ce",
            hover_color="#1eb5b3",
            text_color="#0d1b2a",
            corner_radius=8,
            command=self.toggle_convert
        )
        self.btn_start_conv.pack(fill="x", padx=14, pady=(4, 8))

    def on_conv_format_changed(self, choice):
        audio_formats = ["MP3", "WAV", "FLAC", "AAC", "OGG"]
        state = "disabled" if choice in audio_formats else "normal"
        self.radio_conv_comp_none.configure(state=state)
        self.radio_conv_comp_full.configure(state=state)
        self.radio_conv_comp_half.configure(state=state)

    # ------------------ PAINEL DE LOG E STATUS PERSISTENTE ------------------
    def create_log_and_status_panel(self):
        panel = ctk.CTkFrame(self, fg_color="#181332", corner_radius=12)
        panel.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(8, 2))

        lbl_log = ctk.CTkLabel(
            header,
            text="Log",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ff8c42"
        )
        lbl_log.pack(side="left")

        btn_clear = ctk.CTkButton(
            header,
            text="Limpar Log",
            width=80,
            height=24,
            corner_radius=6,
            fg_color="#2b204e",
            hover_color="#3e2e70",
            text_color="#e0daf7",
            font=ctk.CTkFont(size=11),
            command=self.clear_logs
        )
        btn_clear.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            panel,
            fg_color="#0f0b1f",
            text_color="#d6cefa",
            corner_radius=8,
            border_color="#342858",
            border_width=1,
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(2, 6))

        bottom_bar = ctk.CTkFrame(panel, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=14, pady=(2, 8))

        self.lbl_status = ctk.CTkLabel(
            bottom_bar, 
            text="Pronto para uso.", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#9d95c4",
            anchor="w"
        )
        self.lbl_status.pack(fill="x", pady=(0, 4))

        self.progressbar = ctk.CTkProgressBar(
            bottom_bar, 
            height=8, 
            corner_radius=4,
            progress_color="#ea3a8e",
            fg_color="#100b21"
        )
        self.progressbar.pack(fill="x")
        self.progressbar.set(0)

        self.append_log("YTDawn pronto. Escolha a aba 'Download' ou 'Conversão'.")

    # ------------------ EVENTOS E LOGS ------------------
    def append_log(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{now}] {text}\n"
        self.log_box.insert("end", formatted)
        self.log_box.see("end")

    def clear_logs(self):
        self.log_box.delete("1.0", "end")

    def set_status(self, text):
        self.lbl_status.configure(text=text)
        self.append_log(text)

        if "[CONCLUÍDO COM SUCESSO]" in text or "concluída com sucesso" in text:
            self.lbl_status.configure(text_color="#26d0ce")
        elif "[ERRO]" in text or "Falha" in text:
            self.lbl_status.configure(text_color="#ff5555")
        elif "[CANCELADO]" in text:
            self.lbl_status.configure(text_color="#ffbb33")
        else:
            self.lbl_status.configure(text_color="#9d95c4")

    def set_progress(self, pct, text=""):
        self.progressbar.set(pct / 100.0)
        if text:
            self.lbl_status.configure(text=text)

    def browse_dl_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dl_dir_var.get())
        if folder:
            self.dl_dir_var.set(folder)

    def browse_conv_folder(self):
        folder = filedialog.askdirectory(initialdir=self.conv_dir_var.get())
        if folder:
            self.conv_dir_var.set(folder)

    def select_convert_file(self):
        f = filedialog.askopenfilename(
            title="Escolha o arquivo de áudio ou vídeo",
            filetypes=[
                ("Arquivos de Mídia", "*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.ts *.wmv"),
                ("Todos os arquivos", "*.*")
            ]
        )
        if f:
            self.convert_file_var.set(f)
            self.append_log(f"Arquivo selecionado para conversão: {os.path.basename(f)}")

    def open_base_folders(self):
        try:
            os.startfile(BASE_DIR)
        except Exception:
            subprocess.Popen(["explorer", BASE_DIR])

    def import_cookies_file(self):
        dest_cookies = os.path.join(BASE_DIR, "cookies.txt")
        f = filedialog.askopenfilename(
            title="Selecionar arquivo cookies.txt",
            filetypes=[("Arquivos de Cookies", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        if f:
            try:
                import shutil
                shutil.copy2(f, dest_cookies)
                self.append_log(f"[Cookies] Arquivo cookies.txt importado com sucesso!")
                messagebox.showinfo("YTDawn", "Arquivo cookies.txt importado com sucesso para o programa!")
            except Exception as e:
                messagebox.showerror("YTDawn", f"Erro ao importar cookies: {str(e)}")

    def clean_app_cache(self):
        """Limpa o cache do yt-dlp e do programa."""
        self.append_log("[Cache] Limpando cache do yt-dlp e do aplicativo...")
        success, msg = downloader.clear_ytdlp_cache()
        if success:
            self.append_log(f"[Cache] Sucesso: {msg if msg else 'Cache limpo com sucesso!'}")
            messagebox.showinfo("YTDawn", "Cache limpo com sucesso!\nO aplicativo foi renovado para novos downloads.")
        else:
            self.append_log(f"[Cache] Erro ao limpar cache: {msg}")
            messagebox.showwarning("YTDawn", f"Não foi possível limpar todo o cache:\n{msg}")

    # ------------------ CONTROLE DE DOWNLOAD (INICIAR / CANCELAR) ------------------
    def toggle_download(self):
        if self.is_busy and self.current_mode == "download":
            self.cancel_event.set()
            downloader.cancel_current_task()
            self.set_status("Cancelando download...")
            self.btn_start_dl.configure(state="disabled")
            return

        if self.is_busy:
            messagebox.showwarning("YTDawn", "Uma conversão já está em andamento!")
            return

        raw_text = self.txt_urls.get("1.0", "end").strip()
        urls = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]

        if not urls:
            messagebox.showwarning("YTDawn", "Por favor, insira pelo menos um link de mídia!")
            return

        fmt = self.combo_dl_format.get()
        resolution = self.dl_resolution_var.get()
        compression = self.dl_compression_var.get()
        out_dir = self.dl_dir_var.get()

        self.clear_logs()
        self.append_log(f"=== INICIANDO DOWNLOAD ({len(urls)} link(s)) ===")
        if "MP4" in fmt:
            comp_txt = "Sem compressão extra (None)" if compression == "None" else f"Compressão {compression}"
            self.append_log(f"Formato: {fmt} | Resolução máx: {resolution} | {comp_txt}")
        else:
            self.append_log(f"Formato: {fmt} (Áudio alta fidelidade)")
        self.append_log(f"Destino: {out_dir}")
        self.append_log("Metadados e Thumbnail (capa) ativados.")

        self.is_busy = True
        self.current_mode = "download"
        self.cancel_event.clear()

        self.btn_start_dl.configure(
            text="Cancelar",
            fg_color="#e03131",
            hover_color="#c92a2a",
            state="normal"
        )
        self.btn_start_conv.configure(state="disabled")

        self.progressbar.set(0)
        self.set_status("Iniciando processo de download...")

        def run():
            downloader.download_youtube_items(
                urls=urls,
                format_choice=fmt,
                resolution_choice=resolution,
                compression_choice=compression,
                output_dir=out_dir,
                progress_callback=lambda pct, txt: self.after(0, self.set_progress, pct, txt),
                status_callback=lambda txt: self.after(0, self.set_status, txt),
                cancel_event=self.cancel_event
            )
            self.after(0, self.finish_task)

        threading.Thread(target=run, daemon=True).start()

    # ------------------ CONTROLE DE CONVERSÃO (INICIAR / CANCELAR) ------------------
    def toggle_convert(self):
        if self.is_busy and self.current_mode == "convert":
            self.cancel_event.set()
            converter.cancel_current_task()
            self.set_status("Cancelando conversão...")
            self.btn_start_conv.configure(state="disabled")
            return

        if self.is_busy:
            messagebox.showwarning("YTDawn", "Um download já está em andamento!")
            return

        in_file = self.convert_file_var.get().strip()
        if not in_file or not os.path.exists(in_file):
            messagebox.showwarning("YTDawn", "Por favor, selecione um arquivo válido para converter!")
            return

        target_ext = self.combo_conv_format.get()
        compression = self.conv_compression_var.get()
        out_dir = self.conv_dir_var.get()

        self.clear_logs()
        self.append_log(f"=== INICIANDO CONVERSÃO ===")
        self.append_log(f"Origem: {in_file}")
        comp_txt = "Mantendo tamanho original" if compression == "None" else f"Compressão: {compression}"
        self.append_log(f"Formato de Saída: {target_ext.upper()} | {comp_txt} | Metadados: Preservados")

        self.is_busy = True
        self.current_mode = "convert"
        self.cancel_event.clear()

        self.btn_start_conv.configure(
            text="Cancelar",
            fg_color="#e03131",
            hover_color="#c92a2a",
            text_color="#ffffff",
            state="normal"
        )
        self.btn_start_dl.configure(state="disabled")

        self.progressbar.set(0)
        self.set_status("Iniciando FFmpeg...")

        def run():
            converter.convert_media(
                input_file=in_file,
                target_ext=target_ext,
                output_dir=out_dir,
                compression_mode=compression,
                progress_callback=lambda pct, txt: self.after(0, self.set_progress, pct, txt),
                status_callback=lambda txt: self.after(0, self.set_status, txt),
                cancel_event=self.cancel_event
            )
            self.after(0, self.finish_task)

        threading.Thread(target=run, daemon=True).start()

    def finish_task(self):
        self.is_busy = False
        self.current_mode = None
        self.cancel_event.clear()

        self.btn_start_dl.configure(
            text="Iniciar download",
            fg_color="#ff8c42",
            hover_color="#e06e23",
            state="normal"
        )
        self.btn_start_conv.configure(
            text="Iniciar conversão",
            fg_color="#26d0ce",
            hover_color="#1eb5b3",
            text_color="#0d1b2a",
            state="normal"
        )

if __name__ == "__main__":
    app = YTDawnApp()
    app.mainloop()
