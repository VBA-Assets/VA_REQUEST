"""VA Request の実行ファイル・ウィンドウ用のアイコン（assets\\VA_Request.ico）を作る。

VA mints・VA FAX・VA Document・VA Case シリーズと同じ作り（VA Case の scripts\\generate_icons.py を写したもの）：
角丸の四角に白い太字。1行目に「VA」を小さく、2行目にツールの名前を大きく。2行目は「Req」（Request の略。小さい
アイコンでも読めるよう。VA Receipt の「Rcpt」と同じ考え方）。背景は、ほかのツール（VA mints の青 #0078D4、VA FAX の
緑 #107C41、VA Document の紫 #5C2D91、VA Case の濃いオレンジ #C55A11、VA Filing の青緑 #00827F、VA Receipt の茶
#8E562E、VA Call の赤 #C42B1C）と見分けられる濃い紺 #1F3864。字は Segoe UI Bold。

実行のしかた：
    python scripts\\generate_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "VA_Request.ico"
MAIN_TEXT, BACKGROUND = "Req", "#1F3864"
TEXT_COLOR = "#ffffff"
CANVAS = 256            # 元の画像の一辺（ここから各大きさへ縮める）
CORNER_RADIUS = 28      # ほかのツールと同じ
SIDE_PADDING = 30       # 同じ
TOP_TEXT, TOP_SIZE = "VA", 56          # 1行目（小さく）
MAIN_MAX = 128          # 2行目（この大きさから、余白に収まるまで小さくする）
LINE_GAP = 14
SEGOE = r"C:\Windows\Fonts\segoeuib.ttf"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def font(path, size):
    if not Path(path).is_file():
        raise FileNotFoundError(f"書体が見つかりません：{path}")
    return ImageFont.truetype(path, size)


def build_image(main_text, background):
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, CANVAS - 1, CANVAS - 1), radius=CORNER_RADIUS, fill=background)
    width = CANVAS - SIDE_PADDING * 2
    top = font(SEGOE, TOP_SIZE)
    size = MAIN_MAX
    while size > 10:
        main = font(SEGOE, size)
        box = main.getbbox(main_text, anchor="ls")
        if box[2] - box[0] <= width:
            break
        size -= 2
    top_box = top.getbbox(TOP_TEXT, anchor="ls")
    ascent1, descent1 = -top_box[1], top_box[3]
    ascent2 = -box[1]
    y = (CANVAS - (ascent1 + descent1 + LINE_GAP + ascent2)) / 2
    base1 = y + ascent1
    base2 = base1 + descent1 + LINE_GAP + ascent2
    draw.text(((CANVAS - (top_box[2] - top_box[0])) / 2 - top_box[0], base1), TOP_TEXT, font=top,
              fill=TEXT_COLOR, anchor="ls")
    draw.text(((CANVAS - (box[2] - box[0])) / 2 - box[0], base2), main_text, font=main, fill=TEXT_COLOR, anchor="ls")
    return image


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    build_image(MAIN_TEXT, BACKGROUND).save(OUTPUT, format="ICO", sizes=ICO_SIZES)
    print(f"作りました：{OUTPUT}")
