import os
import sys
import subprocess
import re

def get_bin_dir():
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

def get_binary_path(name):
    bin_dir = get_bin_dir()
    bin_path = os.path.join(bin_dir, f"{name}.exe")
    if os.path.exists(bin_path):
        return bin_path
    return f"{name}.exe"

def get_media_duration(input_file):
    """Obtém a duração em segundos usando ffmpeg diretamente."""
    ffmpeg_exe = get_binary_path("ffmpeg")
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        cmd = [ffmpeg_exe, "-i", input_file]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            text=True,
            errors="replace"
        )
        match = re.search(r'Duration:\s*(\d{2}):(\d{2}):(\d{2}\.?\d*)', res.stderr)
        if match:
            h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
            return h * 3600 + m * 60 + s
        return None
    except Exception:
        return None

current_process = None

def cancel_current_task():
    global current_process
    if current_process:
        try:
            current_process.terminate()
        except Exception:
            pass

def convert_media(input_file, target_ext, output_dir, compression_mode="None", progress_callback=None, status_callback=None, cancel_event=None):
    """
    Converte um arquivo de mídia local usando ffmpeg.
    - Se compression_mode == 'None': mantém o tamanho original e qualidade máxima, apenas alterando a extensão/container.
    - Se compression_mode == 'Full': reduz para 80% do tamanho.
    - Se compression_mode == 'Half': reduz para 50% do tamanho.
    """
    global current_process
    ffmpeg_exe = get_binary_path("ffmpeg")
    target_ext = target_ext.lower().replace(".", "")
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_file = os.path.join(output_dir, f"{base_name}.{target_ext}")

    if os.path.abspath(input_file) == os.path.abspath(output_file):
        output_file = os.path.join(output_dir, f"{base_name}_converted.{target_ext}")

    os.makedirs(output_dir, exist_ok=True)

    if status_callback:
        status_callback(f"Analisando: {os.path.basename(input_file)}...")

    total_duration = get_media_duration(input_file)
    file_size_bytes = os.path.getsize(input_file) if os.path.exists(input_file) else 0

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", input_file,
        "-threads", "0",
        "-map_metadata", "0",
    ]

    audio_formats = ["mp3", "wav", "aac", "flac", "ogg", "m4a"]
    video_formats = ["mp4", "mkv", "avi", "webm", "mov", "gif"]

    if target_ext in audio_formats:
        cmd.extend(["-vn"])
        if target_ext == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
        elif target_ext == "flac":
            cmd.extend(["-c:a", "flac"])
        elif target_ext == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif target_ext == "aac":
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        elif target_ext == "ogg":
            cmd.extend(["-c:a", "libvorbis", "-q:a", "5"])
    elif target_ext in video_formats:
        if target_ext in ["mp4", "mkv", "avi", "mov"]:
            if compression_mode == "None":
                # Mantém o tamanho original com cópia de stream ou re-encode transparente sem perda de tamanho
                cmd.extend(["-c:v", "libx264", "-preset", "faster", "-crf", "18", "-c:a", "copy"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "faster"])
                ratio = 0.80 if compression_mode == "Full" else 0.50
                target_bytes = file_size_bytes * ratio

                if total_duration and total_duration > 0 and file_size_bytes > 0:
                    total_bitrate = int((target_bytes * 8 * 0.95) / total_duration)
                    audio_bitrate = 128000 if compression_mode == "Full" else 96000
                    video_bitrate = max(100000, total_bitrate - audio_bitrate)
                    cmd.extend([
                        "-b:v", f"{video_bitrate}",
                        "-maxrate", f"{int(video_bitrate * 1.3)}",
                        "-bufsize", f"{int(video_bitrate * 2)}",
                        "-c:a", "aac",
                        "-b:a", f"{audio_bitrate}"
                    ])
                else:
                    crf_fallback = "23" if compression_mode == "Full" else "29"
                    audio_bitrate = "128k" if compression_mode == "Full" else "96k"
                    cmd.extend(["-crf", crf_fallback, "-c:a", "aac", "-b:a", audio_bitrate])

        elif target_ext == "webm":
            cmd.extend(["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"])
        elif target_ext == "gif":
            cmd.extend(["-vf", "fps=12,scale=480:-1:flags=lanczos", "-c:v", "gif"])

    cmd.append(output_file)

    comp_info = f" [Compressão: {compression_mode}]" if (target_ext in video_formats and compression_mode != "None") else " [Mantendo tamanho original]"
    if status_callback:
        status_callback(f"Iniciando conversão para {target_ext.upper()}{comp_info} (Metadados preservados)...")

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
            if time_match and total_duration and total_duration > 0:
                h, m, s = float(time_match.group(1)), float(time_match.group(2)), float(time_match.group(3))
                current_secs = h * 3600 + m * 60 + s
                pct = min(100.0, (current_secs / total_duration) * 100)
                if progress_callback:
                    progress_callback(pct, f"Progresso: {pct:.1f}% ({int(current_secs)}s/{int(total_duration)}s)")
            elif status_callback and "fps=" in line:
                status_callback(line)

        process.wait()
        current_process = None

        if cancel_event and cancel_event.is_set():
            if status_callback:
                status_callback("[CANCELADO] Conversão cancelada pelo usuário.")
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass
            return False

        if process.returncode == 0:
            final_size_mb = os.path.getsize(output_file) / (1024 * 1024) if os.path.exists(output_file) else 0
            if progress_callback:
                progress_callback(100.0, "Conversão concluída com sucesso!")
            if status_callback:
                status_callback(f"[CONCLUÍDO COM SUCESSO] Arquivo salvo ({final_size_mb:.2f} MB): {output_file}")
            return True
        else:
            if status_callback:
                status_callback(f"[ERRO] Falha na conversão de {os.path.basename(input_file)}. FFmpeg retornou código de erro.")
            return False
    except Exception as e:
        current_process = None
        if cancel_event and cancel_event.is_set():
            if status_callback:
                status_callback("[CANCELADO] Conversão cancelada pelo usuário.")
            return False
        if status_callback:
            status_callback(f"[ERRO] Exceção durante a conversão: {str(e)}")
        return False
