"""VA Request：職務上請求書の用紙に、字を正しい位置に刷る（仕様は 仕様.md）。"""

# 版はここの1か所に持つ（標準 02「版」）。9 の次は A（"2.A.0"）。表示は VERSION_LABEL（Ver201）を使う
__version__ = "2.0.1"
VERSION_LABEL = "Ver" + __version__.replace(".", "")

APP_NAME = "VA Request"                          # ツールの名前（題名・メッセージ・「について」はここから作る）
FILE_STEM = "VA_Request"                         # exe・zip・マニュアルの名前に使う形
ABOUT_LINE = "職務上請求書の用紙に、字を正しい位置に刷る"   # 「について」の1行の説明（統合版・記事の説明と同じにする）
