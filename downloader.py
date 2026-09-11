import os
import sys
import subprocess
import re
import shutil
import tempfile

def get_bin_dir():
    """Retorna o diretório onde os executáveis binários residem."""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        bin_dir = os.path.join(exe_dir, "bin")
        if os.path.exists(bin_dir):
            return bin_dir
        return exe_dir
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        bin_dir = os.path.join(base_dir, "bin")
        if os.path.exists(bin_dir):
            return bin_dir
        return base_dir

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_binary_path(name):
    bin_dir = get_bin_dir()
    bin_path = os.path.join(bin_dir, f"{name}.exe")
    if os.path.exists(bin_path):
        return bin_path
    return f"{name}.exe"

current_process = None

def cancel_current_task():
    global current_process
    if current_process:
        try:
            current_process.terminate()
        except Exception:
            pass

def get_media_duration(input_file):
    """Obtém a duração em segundos usando ffprobe."""
    ffprobe_exe = get_binary_path("ffprobe")
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        cmd = [
            ffprobe_exe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_file
        ]
        out = subprocess.check_output(cmd, startupinfo=startupinfo, encoding="utf-8", errors="replace")
        return float(out.strip())
    except Exception:
        return None

def get_cookies_file_path():
    """Retorna o caminho do arquivo cookies.txt buscando na raiz, downloads ou bin."""
    base_dir = get_base_dir()
    candidates = [
        os.path.join(base_dir, "cookies.txt"),
        os.path.join(base_dir, "downloads", "cookies.txt"),
        os.path.join(base_dir, "bin", "cookies.txt"),
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 50:
            return c
    return None

def clear_ytdlp_cache():
    """Executa yt-dlp --rm-cache-dir e limpa pastas de cache residuais."""
    ytdlp_exe = get_binary_path("yt-dlp")
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        cmd = [ytdlp_exe, "--rm-cache-dir"]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            timeout=10,
            encoding="utf-8",
            errors="replace"
        )
        return True, res.stdout.strip()
    except Exception as e:
        return False, str(e)

def compress_video_ffmpeg(input_path, output_path, quality_mode, progress_callback=None, status_callback=None, cancel_event=None):
    """
    Re-codifica vídeo usando H.264 (x264), preset faster:
    - None: sem compressão adicional
    - Full: reduz o tamanho para 80% do original
    - Half: reduz o tamanho para 50% do original
    """
    if quality_mode == "None":
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
        return True

    global current_process
    ffmpeg_exe = get_binary_path("ffmpeg")

    file_size_bytes = os.path.getsize(input_path) if os.path.exists(input_path) else 0
    duration = get_media_duration(input_path)

    ratio = 0.80 if quality_mode == "Full" else 0.50
    target_bytes = file_size_bytes * ratio

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "faster",
        "-threads", "0",
        "-map_metadata", "0",
    ]

    if duration and duration > 0 and file_size_bytes > 0:
        total_bitrate = int((target_bytes * 8 * 0.95) / duration)
        audio_bitrate = 128000 if quality_mode == "Full" else 96000
        video_bitrate = max(100000, total_bitrate - audio_bitrate)

        cmd.extend([
            "-b:v", f"{video_bitrate}",
            "-maxrate", f"{int(video_bitrate * 1.3)}",
            "-bufsize", f"{int(video_bitrate * 2)}",
            "-c:a", "aac",
            "-b:a", f"{audio_bitrate}"
        ])
    else:
        crf_fallback = "23" if quality_mode == "Full" else "29"
        audio_bitrate = "128k" if quality_mode == "Full" else "96k"
        cmd.extend(["-crf", crf_fallback, "-c:a", "aac", "-b:a", audio_bitrate])

    cmd.append(output_path)

    pct_str = "80%" if quality_mode == "Full" else "50%"
    if status_callback:
        status_callback(f"Comprimindo vídeo ({quality_mode}: ~{pct_str} do tamanho baixado, preset faster)...")

    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            startupinfo=startupinfo,
            encoding="utf-8",
            errors="replace"
        )
        current_process = process

        for line in process.stdout:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                break

            line = line.strip()
            if not line:
                continue

            time_match = re.search(r'time=([0-9]{2}):([0-9]{2}):([0-9]{2}\.[0-9]+)', line)
            if time_match and duration and duration > 0:
                h, m, s = float(time_match.group(1)), float(time_match.group(2)), float(time_match.group(3))
                current_secs = h * 3600 + m * 60 + s
                pct = min(100.0, (current_secs / duration) * 100)
                if progress_callback:
                    progress_callback(pct, f"Comprimindo [{quality_mode} - {pct_str}]: {pct:.1f}% ({int(current_secs)}s/{int(duration)}s)")
            elif status_callback and "fps=" in line:
                status_callback(line)

        process.wait()
        current_process = None

        if cancel_event and cancel_event.is_set():
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            return False

        return process.returncode == 0
    except Exception as e:
        current_process = None
        if status_callback:
            status_callback(f"[ERRO] Falha no encode H.264: {str(e)}")
        return False

def download_youtube_items(urls, format_choice, resolution_choice, compression_choice, output_dir, progress_callback=None, status_callback=None, cancel_event=None):
    """
    urls: lista de URLs de mídia
    format_choice: 'MP4 (Vídeo)' ou 'MP3 (Áudio)'
    resolution_choice: '1080p' ou '720p' (ou qualidade original se for menor)
    compression_choice: 'None', 'Full' (80%), 'Half' (50%)
    output_dir: diretório de destino
    """
    global current_process
    ytdlp_exe = get_binary_path("yt-dlp")
    ffmpeg_exe = get_binary_path("ffmpeg")
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)

    os.makedirs(output_dir, exist_ok=True)

    # Obter cookies.txt existente (raiz, downloads ou bin)
    cookie_file = get_cookies_file_path()
    if cookie_file and status_callback:
        status_callback(f"[Cookies] Usando cookies de: {os.path.basename(cookie_file)}")

    is_video = "MP4" in format_choice
    total = len(urls)

    for index, url in enumerate(urls, start=1):
        if cancel_event and cancel_event.is_set():
            if status_callback:
                status_callback("[CANCELADO] Operação interrompida pelo usuário.")
            break

        url = url.strip()
        if not url:
            continue

        if status_callback:
            status_callback(f"[{index}/{total}] Iniciando download de: {url}")

        needs_compression = is_video and compression_choice in ["Full", "Half"]
        temp_dir = None
        target_dl_dir = output_dir

        if needs_compression:
            temp_dir = tempfile.mkdtemp(prefix="ytdawn_")
            target_dl_dir = temp_dir

        cmd = [
            ytdlp_exe,
            "--newline",
            "--ffmpeg-location", ffmpeg_dir,
            "--embed-metadata",
            "--embed-thumbnail",
            "-o", os.path.join(target_dl_dir, "%(title)s.%(ext)s")
        ]

        # Injetar cookies salvos se existirem
        if cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 50:
            cmd.extend(["--cookies", cookie_file])

        if not is_video:
            # MP3 (Áudio)
            cmd.extend([
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0"
            ])
        else:
            # MP4 com limite de resolução selecionado: 1080p ou 720p (ou menor)
            max_height = "1080" if "1080" in resolution_choice else "720"
            video_format_filter = (
                f"bv*[height<={max_height}][ext=mp4]+ba[ext=m4a] / "
                f"bv*[height<={max_height}]+ba / "
                f"b[height<={max_height}][ext=mp4] / "
                f"b[height<={max_height}] / "
                f"bv*+ba / b"
            )
            cmd.extend([
                "-f", video_format_filter,
                "--merge-output-format", "mp4"
            ])

        cmd.append(url)

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                startupinfo=startupinfo,
                encoding="utf-8",
                errors="replace"
            )
            current_process = process

            last_error_line = ""
            for line in process.stdout:
                if cancel_event and cancel_event.is_set():
                    process.terminate()
                    break

                line = line.strip()
                if not line:
                    continue

                if "ERROR:" in line or "error" in line.lower() or "bot" in line.lower() or "sign in" in line.lower():
                    last_error_line = line

                percent_match = re.search(r'\[download\]\s+([0-9\.]+)%', line)
                if percent_match and progress_callback:
                    try:
                        pct = float(percent_match.group(1))
                        display_pct = pct * 0.6 if needs_compression else pct
                        progress_callback(display_pct, f"[{index}/{total}] {line}")
                    except ValueError:
                        pass
                elif status_callback:
                    status_callback(f"[{index}/{total}] {line}")

            process.wait()
            current_process = None

            if cancel_event and cancel_event.is_set():
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                if status_callback:
                    status_callback(f"[CANCELADO] Download de ({url}) interrompido.")
                break

            if process.returncode != 0:
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                err_detail = f": {last_error_line}" if last_error_line else ""
                if status_callback:
                    status_callback(f"[ERRO] Falha no download de ({url}){err_detail}")
                continue

            # Se compressão for Full ou Half, aplicar ffmpeg
            if needs_compression and temp_dir:
                downloaded_files = [
                    os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                    if os.path.isfile(os.path.join(temp_dir, f)) and f.lower().endswith(('.mp4', '.mkv', '.webm'))
                ]

                if downloaded_files:
                    raw_file = downloaded_files[0]
                    raw_size_mb = os.path.getsize(raw_file) / (1024 * 1024)
                    base_filename = os.path.splitext(os.path.basename(raw_file))[0]
                    final_output_file = os.path.join(output_dir, f"{base_filename}.mp4")

                    pct_label = "80%" if compression_choice == "Full" else "50%"
                    if status_callback:
                        status_callback(f"[{index}/{total}] Download ({raw_size_mb:.1f} MB, máx {max_height}p). Comprimindo para {pct_label}...")

                    def sub_progress(pct, txt):
                        overall_pct = 60.0 + (pct * 0.4)
                        if progress_callback:
                            progress_callback(overall_pct, f"[{index}/{total}] {txt}")

                    success = compress_video_ffmpeg(
                        input_path=raw_file,
                        output_path=final_output_file,
                        quality_mode=compression_choice,
                        progress_callback=sub_progress,
                        status_callback=lambda txt: status_callback(f"[{index}/{total}] {txt}") if status_callback else None,
                        cancel_event=cancel_event
                    )

                    shutil.rmtree(temp_dir, ignore_errors=True)

                    if cancel_event and cancel_event.is_set():
                        if status_callback:
                            status_callback(f"[CANCELADO] Compressão de ({url}) interrompida.")
                        break

                    if success:
                        final_size_mb = os.path.getsize(final_output_file) / (1024*1024) if os.path.exists(final_output_file) else 0
                        reduction_pct = (1.0 - (final_size_mb / max(0.001, raw_size_mb))) * 100
                        if progress_callback:
                            progress_callback(100.0, "Download e compressão concluídos!")
                        if status_callback:
                            status_callback(f"[CONCLUÍDO COM SUCESSO] Vídeo salvo: {final_size_mb:.2f} MB (-{reduction_pct:.0f}%): {final_output_file}")
                    else:
                        if status_callback:
                            status_callback(f"[ERRO] Falha ao processar compressão do vídeo {url}")
                else:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    if status_callback:
                        status_callback(f"[CONCLUÍDO COM SUCESSO] Download finalizado: {url}")
            else:
                # Caso None ou Áudio
                if progress_callback:
                    progress_callback(100.0, "Download concluído!")
                if status_callback:
                    msg = f"[CONCLUÍDO COM SUCESSO] Vídeo baixado: {url}" if is_video else f"[CONCLUÍDO COM SUCESSO] Áudio finalizado: {url}"
                    status_callback(msg)

        except Exception as e:
            current_process = None
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            if cancel_event and cancel_event.is_set():
                if status_callback:
                    status_callback("[CANCELADO] Operação interrompida pelo usuário.")
                break
            if status_callback:
                status_callback(f"[ERRO] Exceção ao processar ({url}): {str(e)}")

    if not (cancel_event and cancel_event.is_set()):
        if status_callback:
            status_callback("--- FIM DA FILA DE DOWNLOADS ---")
