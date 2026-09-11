import os
import math
from PIL import Image, ImageDraw

def create_aurora_icon():
    os.makedirs("assets", exist_ok=True)
    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Cores inspiradas em Aurora / Dawn (Alvorada Boreal)
    margin = 24
    draw.ellipse([margin, margin, 512 - margin, 512 - margin], fill=(16, 12, 34, 255))

    # Desenhar ondas de aurora no céu noturno
    for i in range(120, 280):
        alpha = int(90 * math.sin((i - 120) / 160 * math.pi))
        y_offset = int(25 * math.sin(i * 0.035))
        draw.arc([60, 100 + y_offset, 452, 360 + y_offset], start=170, end=370, fill=(38, 208, 206, alpha), width=3)

    for i in range(180, 360):
        alpha = int(120 * math.sin((i - 180) / 180 * math.pi))
        y_offset = int(30 * math.cos(i * 0.03))
        draw.arc([70, 130 + y_offset, 442, 390 + y_offset], start=180, end=360, fill=(234, 58, 142, alpha), width=4)

    # Sol nascente / Aurora glow central
    sun_box = [176, 200, 336, 360]
    for r in range(40, 0, -2):
        alpha = int(140 * (1 - r / 40.0))
        draw.ellipse([sun_box[0] - r, sun_box[1] - r + 30, sun_box[2] + r, sun_box[3] + r + 30], fill=(255, 140, 66, alpha))

    draw.ellipse([186, 210, 326, 350], fill=(255, 215, 0, 240))
    draw.ellipse([196, 220, 316, 340], fill=(255, 245, 210, 255))

    # Montanhas minimalistas
    mountains1 = [(40, 400), (180, 280), (280, 370), (390, 260), (472, 400), (472, 472), (40, 472)]
    draw.polygon(mountains1, fill=(26, 18, 48, 255))

    mountains2 = [(70, 430), (160, 340), (250, 410), (360, 320), (450, 430), (450, 480), (70, 480)]
    draw.polygon(mountains2, fill=(12, 9, 24, 255))

    # Seta elegante de download
    arrow_pts = [(256, 390), (256, 430)]
    draw.line(arrow_pts, fill=(255, 230, 180, 240), width=6)
    head_pts = [(242, 420), (256, 436), (270, 420)]
    draw.line(head_pts, fill=(255, 230, 180, 240), width=6)

    # Borda sutil aurora
    draw.ellipse([margin, margin, 512 - margin, 512 - margin], outline=(255, 110, 160, 180), width=4)

    # Salvar PNG
    png_path = os.path.join("assets", "icon.png")
    img.save(png_path, "PNG")

    # Salvar ICO com múltiplos tamanhos
    ico_path = os.path.join("assets", "icon.ico")
    img.save(ico_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icons generated: {png_path}, {ico_path}")

if __name__ == "__main__":
    create_aurora_icon()
