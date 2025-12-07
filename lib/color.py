__all__ = [
    "is_colorful", "enable_color", "disable_color", "detect_color",
    "autoset_color",
    "RGB", "Text", "MARK", "Mark", "plen",
    "Red", "Green", "Yellow", "Blue", "Magenta", "Purple", "Cyan",
    "White", "Black", "Gray", "Orange", "Pink", "Brown", "Violet",
    "Gold", "Silver", "Lime", "Navy", "Skyblue", "Tianyi",
    "RED", "GREEN", "YELLOW", "BLUE", "MAGENTA", "PURPLE", "CYAN",
    "WHITE", "BLACK", "GRAY", "ORANGE", "PINK", "BROWN", "VIOLET",
    "GOLD", "SILVER", "LIME", "NAVY", "SKYBLUE", "TIANYI",
    "BOLD", "ITALIC",
]

import io
import os
import sys
from typing import overload

from wcwidth import wcswidth

_COLOR_DISABLED = False
def is_colorful():
    return not _COLOR_DISABLED
def enable_color():
    global _COLOR_DISABLED
    _COLOR_DISABLED = False
def disable_color():
    global _COLOR_DISABLED
    _COLOR_DISABLED = True
# 更新此函数时需要同步更新 build.py 中的函数
def detect_color():
    if not sys.stdout.isatty():
        return False
    if "NO_COLOR" in os.environ:
        return False
    term = os.environ.get("TERM")
    if not term or term == "dumb":
        return False
    colorterm = os.environ.get("COLORTERM")
    if colorterm == "truecolor" or colorterm == "24bit":
        return True
    # term_prog = os.environ.get("TERM_PROGRAM")
    # term_prog_version = os.environ.get("TERM_PROGRAM_VERSION")
    vte = os.environ.get("VTE_VERSION", "")
    if vte.isdigit() and int(vte) >= 3600: # VTE 0.36.0 开始实验性支持真彩色
        return True
    return False
def autoset_color():
    if detect_color():
        enable_color()
    else:
        disable_color()

class Style:
    __slots__ = ("ansi", "ansi_rev")
    def __init__(self):
        self.ansi = ""
        self.ansi_rev = ""
    def __init_subclass__(cls):
        cls.__slots__ += ("ansi", "ansi_rev")
    def __copy__(self):
        return self
    def __deepcopy__(self, memo):
        return self
    def __mul__(self, other):
        if isinstance(other, Style):
            ret = Style()
            ret.ansi = self.ansi + ";" + other.ansi
            ret.ansi_rev = self.ansi_rev + ";" + other.ansi_rev
            return ret
        elif isinstance(other, Text):
            ret = other.copy()
            ret.tags.append(Span(0, len(other.s)-1, [self]))
            return ret
        elif isinstance(other, str):
            ret = Text(other)
            ret.tags.append(Span(0, len(other)-1, [self]))
            return ret
        return NotImplemented
    def __rmul__(self, other):
        if isinstance(other, Text):
            ret = other.copy()
            ret.tags.append(Span(0, len(other.s)-1, [self]))
            return ret
        elif isinstance(other, str):
            ret = Text(other)
            ret.tags.append(Span(0, len(other)-1, [self]))
            return ret
        return NotImplemented
class Bold(Style):
    def __init__(self):
        super().__init__()
        self.ansi = "1"
        self.ansi_rev = "22"
class Italic(Style):
    def __init__(self):
        super().__init__()
        self.ansi = "3"
        self.ansi_rev = "23"
_ansi_colors = {
    # https://www.w3school.com.cn/cssref/css_colors.asp
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "purple": "38;2;128;00;128",
    "cyan": "36",
    "white": "38;2;255;255;255",
    "black": "38;2;0;0;0",
    "grey": "38;2;128;128;128",
    "orange": "38;2;255;165;0",
    "pink": "38;2;255;192;203",
    "brown": "38;2;165;42;42",
    "violet": "38;2;238;130;238",
    "turquoise": "38;2;64;224;208",
    "gold": "38;2;255;215;0",
    "silver": "38;2;192;192;192",
    "lime": "38;2;0;255;0",
    "olive": "38;2;128;128;0",
    "teal": "38;2;0;128;128",
    "navy": "38;2;0;0;128",
    "maroon": "38;2;128;0;0",
    "coral": "38;2;255;127;80",
    "salmon": "38;2;250;128;114",
    "plum": "38;2;221;160;221",
    "orchid": "38;2;218;112;214",
    "skyblue": "38;2;135;206;235",
    # 扩展颜色
    "tianyi": "38;2;102;204;255",
    # 补充其它 CSS 颜色（AI 生成）
    "indigo": "38;2;75;0;130",
    "lavender": "38;2;230;230;250",
    "crimson": "38;2;220;20;60",
    "beige": "38;2;245;245;220",
    "khaki": "38;2;240;230;140",
    "azure": "38;2;240;255;255",
    "ivory": "38;2;255;255;240",
    "tan": "38;2;210;180;140",
    "chocolate": "38;2;210;105;30",
    "sienna": "38;2;160;82;45",
    "peru": "38;2;205;133;63",
    "darkred": "38;2;139;0;0",
    "darkgreen": "38;2;0;100;0",
    "darkblue": "38;2;0;0;139",
    "darkcyan": "38;2;0;139;139",
    "darkmagenta": "38;2;139;0;139",
    "darkorange": "38;2;255;140;0",
    "darkviolet": "38;2;148;0;211",
    "lightblue": "38;2;173;216;230",
    "lightgreen": "38;2;144;238;144",
    "lightgrey": "38;2;211;211;211",
    "lightpink": "38;2;255;182;193",
    "lightyellow": "38;2;255;255;224",
    "lightcyan": "38;2;224;255;255",
    "darkslategrey": "38;2;47;79;79",
    "dimgrey": "38;2;105;105;105",
    "slategrey": "38;2;112;128;144",
    "steelblue": "38;2;70;130;180",
    "royalblue": "38;2;65;105;225",
    "midnightblue": "38;2;25;25;112",
    "forestgreen": "38;2;34;139;34",
    "springgreen": "38;2;0;255;127",
    "seagreen": "38;2;46;139;87",
    "mediumseagreen": "38;2;60;179;113",
    "lawngreen": "38;2;124;252;0",
    "chartreuse": "38;2;127;255;0",
    "mediumspringgreen": "38;2;0;250;154",
    "tomato": "38;2;255;99;71",
    "orangered": "38;2;255;69;0",
    "deeppink": "38;2;255;20;147",
    "hotpink": "38;2;255;105;180",
    "palevioletred": "38;2;219;112;147",
    "mediumvioletred": "38;2;199;21;133",
    "mediumorchid": "38;2;186;85;211",
    "mediumpurple": "38;2;147;112;219",
    "rebeccapurple": "38;2;102;51;153",
    "darkorchid": "38;2;153;50;204",
    "darkgoldenrod": "38;2;184;134;11",
    "rosybrown": "38;2;188;143;143",
    "saddlebrown": "38;2;139;69;19",
    "sandybrown": "38;2;244;164;96",
    "darkkhaki": "38;2;189;183;107",
    "cornflowerblue": "38;2;100;149;237",
    "cadetblue": "38;2;95;158;160",
    "aquamarine": "38;2;127;255;212",
    "paleturquoise": "38;2;175;238;238",
    "lightsteelblue": "38;2;176;196;222",
    "powderblue": "38;2;176;224;230",
    "honeydew": "38;2;240;255;240",
    "mintcream": "38;2;245;255;250",
    "aliceblue": "38;2;240;248;255",
    "ghostwhite": "38;2;248;248;255",
    "whitesmoke": "38;2;245;245;245",
    "seashell": "38;2;255;245;238",
    "floralwhite": "38;2;255;250;240",
    "snow": "38;2;255;250;250",
    "linen": "38;2;250;240;230",
    "antiquewhite": "38;2;250;235;215",
    "papayawhip": "38;2;255;239;213",
    "blanchedalmond": "38;2;255;235;205",
    "bisque": "38;2;255;228;196",
    "moccasin": "38;2;255;228;181",
    "navajowhite": "38;2;255;222;173",
    "peachpuff": "38;2;255;218;185",
    "mistyrose": "38;2;255;228;225",
    "lavenderblush": "38;2;255;240;245",
    "oldlace": "38;2;253;245;230",
    "gainsboro": "38;2;220;220;220",
    "lightgray": "38;2;211;211;211",
    "darkgray": "38;2;169;169;169",
    "darkslategray": "38;2;47;79;79",
    "dimgray": "38;2;105;105;105",
    "slategray": "38;2;112;128;144",
}
class Color(Style):
    def __init__(self, c: str, /):
        super().__init__()
        self.ansi = _ansi_colors[c]
        self.ansi_rev = "39"
class RGB(Style):
    @overload
    def __init__(self, r: int, g: int, b: int, /): ...
    @overload
    def __init__(self, hex: str | int, /): ...
    def __init__(self, *args):
        super().__init__()
        if len(args) == 1:
            if isinstance(x := args[0], str):
                if x.startswith("#"):
                    x = x[1:]
                if len(x) == 3:
                    x = int(x, 16)
                    r = (x >> 8) & 0xf
                    g = (x >> 4) & 0xf
                    b = x & 0xf
                    r = r << 4 | r
                    g = g << 4 | g
                    b = b << 4 | b
                elif len(x) == 6:
                    x = int(x, 16)
                    r = (x >> 16) & 0xff
                    g = (x >> 8) & 0xff
                    b = x & 0xff
                else:
                    raise ValueError("不是合法的十六进制颜色字符串。")
            elif isinstance(x, int):
                r = (x >> 16) & 0xff
                g = (x >> 8) & 0xff
                b = x & 0xff
            else:
                raise ValueError(f"期望 int 或 str，而不是 {type(x)}")
        elif len(args) == 3:
            r, g, b = args
        else:
            raise TypeError(f"期望 1 或 3 个参数，而不是 {len(args)} 个。")
        self.ansi = f"38;2;{r};{g};{b}"
        self.ansi_rev = "39"
class Span():
    __slots__ = ("l", "r", "style")
    def __init__(self, l: int, r: int, style: list[Style] = None):
        self.l, self.r = l, r
        self.style = [] if style is None else style
    def copy(self):
        return Span(self.l, self.r, self.style.copy())
    def __copy__(self):
        return self.copy()
class Text():
    __slots__ = ("s", "cell_len", "tags")
    def __init__(self, s: str = "", tags: list[Span] = None, *, _cell_len: int = None):
        self.s = s
        self.cell_len = wcswidth(s) if _cell_len is None else _cell_len
        self.tags = [] if tags is None else sorted(tags, key=lambda x: x.l)
    def copy(self):
        return Text(self.s, self.tags.copy(), _cell_len=self.cell_len)
    def __copy__(self):
        return self.copy()
    def toansi(self):
        if _COLOR_DISABLED or not self.tags:
            return self.s
        tags: list[tuple[int, str]] = []
        for tag in self.tags:
            for x in tag.style:
                tags.append((tag.l, x.ansi))
                tags.append((tag.r+1, x.ansi_rev))
        tags.sort(key=lambda x: x[0])
        ret = io.StringIO()
        las = 0
        for x, style in tags:
            ret.write(self.s[las:x])
            las = x
            ret.write(f"\033[{style}m")
        ret.write(self.s[las:])
        return ret.getvalue()
    def __add__(self, other: "Text | str") -> "Text":
        if isinstance(other, str):
            return Text(self.s+other, self.tags.copy())
        elif isinstance(other, Text):
            offset = len(self.s)
            return Text(self.s+other.s, self.tags + [Span(tag.l+offset, tag.r+offset, tag.style.copy()) for tag in other.tags], _cell_len=self.cell_len+other.cell_len)
        return NotImplemented
    def __iadd__(self, other: "Text | str") -> "Text":
        if isinstance(other, str):
            self.s += other
            self.cell_len += wcswidth(other)
            return self
        elif isinstance(other, Text):
            offset = len(self.s)
            self.s += other.s
            self.cell_len += other.cell_len
            self.tags += [Span(tag.l+offset, tag.r+offset, tag.style.copy()) for tag in other.tags]
            return self
        return NotImplemented
    def __radd__(self, other: str) -> "Text":
        if isinstance(other, str):
            offset = len(other)
            return Text(other+self.s, [Span(tag.l+offset, tag.r+offset, tag.style.copy()) for tag in self.tags])
        return NotImplemented

_red = Color("red")
_green = Color("green")
_yellow = Color("yellow")
_blue = Color("blue")
_magenta = Color("magenta")
_purple = Color("purple")
_cyan = Color("cyan")
_white = Color("white")
_black = Color("black")
_grey = Color("grey")
_orange = Color("orange")
_pink = Color("pink")
_brown = Color("brown")
_violet = Color("violet")
_gold = Color("gold")
_silver = Color("silver")
_lime = Color("lime")
_navy = Color("navy")
_skyblue = Color("skyblue")
_tianyi = Color("tianyi")
_bold = Bold()
_italic = Italic()

def Red(s: Text | str) -> Text: return s * _red
def Green(s: Text | str) -> Text: return s * _green
def Yellow(s: Text | str) -> Text: return s * _yellow
def Blue(s: Text | str) -> Text: return s * _blue
def Magenta(s: Text | str) -> Text: return s * _magenta
def Purple(s: Text | str) -> Text: return s * _purple
def Cyan(s: Text | str) -> Text: return s * _cyan
def White(s: Text | str) -> Text: return s * _white
def Black(s: Text | str) -> Text: return s * _black
def Gray(s: Text | str) -> Text: return s * _grey
def Orange(s: Text | str) -> Text: return s * _orange
def Pink(s: Text | str) -> Text: return s * _pink
def Brown(s: Text | str) -> Text: return s * _brown
def Violet(s: Text | str) -> Text: return s * _violet
def Gold(s: Text | str) -> Text: return s * _gold
def Silver(s: Text | str) -> Text: return s * _silver
def Lime(s: Text | str) -> Text: return s * _lime
def Navy(s: Text | str) -> Text: return s * _navy
def Skyblue(s: Text | str) -> Text: return s * _skyblue
def Tianyi(s: Text | str) -> Text: return s * _tianyi
def Mark(s: Text | str, color: str) -> Text: return s * Color(color)

def RED(s: Text | str) -> Text: return s * _red * _bold
def GREEN(s: Text | str) -> Text: return s * _green * _bold
def YELLOW(s: Text | str) -> Text: return s * _yellow * _bold
def BLUE(s: Text | str) -> Text: return s * _blue * _bold
def MAGENTA(s: Text | str) -> Text: return s * _magenta * _bold
def PURPLE(s: Text | str) -> Text: return s * _purple * _bold
def CYAN(s: Text | str) -> Text: return s * _cyan * _bold
def WHITE(s: Text | str) -> Text: return s * _white * _bold
def BLACK(s: Text | str) -> Text: return s * _black * _bold
def GRAY(s: Text | str) -> Text: return s * _grey * _bold
def ORANGE(s: Text | str) -> Text: return s * _orange * _bold
def PINK(s: Text | str) -> Text: return s * _pink * _bold
def BROWN(s: Text | str) -> Text: return s * _brown * _bold
def VIOLET(s: Text | str) -> Text: return s * _violet * _bold
def GOLD(s: Text | str) -> Text: return s * _gold * _bold
def SILVER(s: Text | str) -> Text: return s * _silver * _bold
def LIME(s: Text | str) -> Text: return s * _lime * _bold
def NAVY(s: Text | str) -> Text: return s * _navy * _bold
def SKYBLUE(s: Text | str) -> Text: return s * _skyblue * _bold
def TIANYI(s: Text | str) -> Text: return s * _tianyi * _bold
def MARK(s: Text | str, color: str) -> Text: return s * Color(color) * _bold

def BOLD(s: Text | str) -> Text: return s  * _bold
def ITALIC(s: Text | str) -> Text: return s  * _italic

def plen(s: Text | str) -> Text:
    if isinstance(s, str):
        return wcswidth(s)
    return s.cell_len
