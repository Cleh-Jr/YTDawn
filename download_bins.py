import os
import sys
import zipfile
import urllib.request

BIN_DIR = os.path.join(os.path.dirname(__file__), "bin")
os.makedirs(BIN_DIR, exist_ok=True)

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
# Build estável e compacta do FFmpeg essentials para Windows
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

def download_file(url, dest_path):
    print(f"Baixando: {url} -> {dest_path}")
    def reporthook(blocknum, blocksize, totalsize):
        readsofar = blocknum * blocksize
        if totalsize > 0:
            percent = readsofar * 1e2 / totalsize
            s = f"\r[{percent:5.1f}%] {readsofar / (1024*1024):.1f}MB / {totalsize / (1024*1024):.1f}MB"
            sys.stdout.write(s)
            sys.stdout.flush()
    urllib.request.urlretrieve(url, dest_path, reporthook)
    print("\nDownload concluído!")

def setup_ytdlp():
    ytdlp_path = os.path.join(BIN_DIR, "yt-dlp.exe")
    if not os.path.exists(ytdlp_path):
        download_file(YTDLP_URL, ytdlp_path)
    else:
        print("yt-dlp.exe já existe.")

def setup_ffmpeg():
    ffmpeg_path = os.path.join(BIN_DIR, "ffmpeg.exe")
    ffprobe_path = os.path.join(BIN_DIR, "ffprobe.exe")
    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        print("ffmpeg.exe e ffprobe.exe já existem.")
        return

    zip_tmp = os.path.join(BIN_DIR, "ffmpeg.zip")
    download_file(FFMPEG_ZIP_URL, zip_tmp)

    print("Extraindo ffmpeg.exe e ffprobe.exe...")
    with zipfile.ZipFile(zip_tmp, 'r') as zip_ref:
        for member in zip_ref.namelist():
            if member.endswith("bin/ffmpeg.exe"):
                with zip_ref.open(member) as source, open(ffmpeg_path, "wb") as target:
                    target.write(source.read())
            elif member.endswith("bin/ffprobe.exe"):
                with zip_ref.open(member) as source, open(ffprobe_path, "wb") as target:
                    target.write(source.read())

    if os.path.exists(zip_tmp):
        os.remove(zip_tmp)
    print("FFmpeg configurado com sucesso!")

if __name__ == "__main__":
    setup_ytdlp()
    setup_ffmpeg()
