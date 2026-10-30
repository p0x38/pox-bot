from __future__ import annotations

import colorsys
import math
import random as _random
import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Color3:
    """Python representation of Roblox Color3, with RGB components in [0, 1]."""

    r: float = 0.0
    g: float = 0.0
    b: float = 0.0

    def __post_init__(self) -> None:
        for channel_name, value in (('r', self.r), ('g', self.g), ('b', self.b)):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(
                    f'{channel_name} must be a finite number in [0, 1]; got {value!r}'
                )

    @classmethod
    def new(cls, red: float = 0.0, green: float = 0.0, blue: float = 0.0) -> Color3:
        return cls(red, green, blue)

    @classmethod
    def from_rgb(cls, red: int, green: int, blue: int) -> Color3:
        channels = (red, green, blue)
        if any(
            isinstance(channel, bool) or not isinstance(channel, (int, float))
            for channel in channels
        ):
            raise TypeError('RGB channels must be numbers')
        if any(
            not math.isfinite(channel) or not 0 <= channel <= 255
            for channel in channels
        ):
            raise ValueError('RGB channels must be finite numbers in [0, 255]')
        return cls(*(channel / 255.0 for channel in channels))

    @classmethod
    def from_hsv(cls, hue: float, saturation: float, value: float) -> Color3:
        if any(not math.isfinite(channel) for channel in (hue, saturation, value)):
            raise ValueError('HSV channels must be finite')
        if (
            not 0.0 <= hue <= 1.0
            or not 0.0 <= saturation <= 1.0
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError('HSV channels must be in [0, 1]')
        return cls(*colorsys.hsv_to_rgb(hue, saturation, value))

    @classmethod
    def from_hex(cls, value: str) -> Color3:
        if not isinstance(value, str):
            raise TypeError('Hex color must be a string')
        digits = value.strip().removeprefix('#')
        if re.fullmatch(r'[0-9a-fA-F]{3}', digits):
            digits = ''.join(character * 2 for character in digits)
        if not re.fullmatch(r'[0-9a-fA-F]{6}', digits):
            raise ValueError(
                "Hex color must have 3 or 6 hexadecimal digits, "
                "optionally prefixed with '#'"
            )
        return cls.from_rgb(
            *(int(digits[index : index + 2], 16) for index in (0, 2, 4))
        )

    @property
    def R(self) -> float:
        return self.r

    @property
    def G(self) -> float:
        return self.g

    @property
    def B(self) -> float:
        return self.b

    @property
    def rgb(self) -> tuple[int, int, int]:
        return tuple(round(channel * 255) for channel in (self.r, self.g, self.b))  # type: ignore[return-value]

    @property
    def hex(self) -> str:
        return self.to_hex()

    def to_hsv(self) -> tuple[float, float, float]:
        return colorsys.rgb_to_hsv(self.r, self.g, self.b)

    def to_hex(self, *, include_hash: bool = False) -> str:
        value = ''.join(f'{channel:02X}' for channel in self.rgb)
        return f'#{value}' if include_hash else value

    def lerp(self, color: Color3, alpha: float) -> Color3:
        if not isinstance(color, Color3):
            raise TypeError('color must be a Color3')
        if not math.isfinite(alpha):
            raise ValueError('alpha must be finite')
        channels = tuple(
            a + (b - a) * alpha
            for a, b in zip((self.r, self.g, self.b), (color.r, color.g, color.b))
        )
        
        return Color3(*(min(1.0, max(0.0, channel)) for channel in channels))

    def __iter__(self):
        return iter((self.r, self.g, self.b))


@dataclass(frozen=True, slots=True)
class BrickColorData:
    number: int
    name: str
    rgb: tuple[int, int, int]
    palette_index: int | None = None

    @property
    def hex(self) -> str:
        return ''.join(f'{channel:02X}' for channel in self.rgb)

    @property
    def color3(self) -> Color3:
        return Color3.from_rgb(*self.rgb)


PALETTE_INDEX_TO_BRICK_COLOR_ID: tuple[int, ...] = (
    141,
    301,
    107,
    26,
    1012,
    303,
    1011,
    304,
    28,
    1018,
    302,
    305,
    306,
    307,
    308,
    1021,
    309,
    310,
    1019,
    135,
    102,
    23,
    1010,
    312,
    313,
    37,
    1022,
    1020,
    1027,
    311,
    315,
    1023,
    1031,
    316,
    151,
    317,
    318,
    319,
    1024,
    314,
    1013,
    1006,
    321,
    322,
    104,
    1008,
    119,
    323,
    324,
    325,
    320,
    11,
    1026,
    1016,
    1032,
    1015,
    327,
    1005,
    1009,
    29,
    328,
    1028,
    208,
    45,
    329,
    330,
    331,
    1004,
    21,
    332,
    333,
    24,
    334,
    226,
    1029,
    335,
    336,
    342,
    343,
    338,
    1007,
    339,
    133,
    106,
    340,
    341,
    1001,
    1,
    9,
    1025,
    337,
    344,
    345,
    1014,
    105,
    346,
    347,
    348,
    349,
    1030,
    125,
    101,
    350,
    192,
    351,
    352,
    353,
    354,
    1002,
    5,
    18,
    217,
    355,
    356,
    153,
    357,
    358,
    359,
    360,
    38,
    361,
    362,
    199,
    194,
    363,
    364,
    365,
    1003,
)
BRICK_COLOR_ID_TO_PALETTE_INDEX: dict[int, int] = {
    color_id: palette_index
    for palette_index, color_id in enumerate(PALETTE_INDEX_TO_BRICK_COLOR_ID)
}


_BRICK_COLOR_ROWS = """
1|White|242|243|243
2|Grey|161|165|162
3|Light yellow|249|233|153
5|Brick yellow|215|197|154
6|Light green (Mint)|194|218|184
9|Light reddish violet|232|186|200
11|Pastel Blue|128|187|219
12|Light orange brown|203|132|66
18|Nougat|204|142|105
21|Bright red|196|40|28
22|Med. reddish violet|196|112|160
23|Bright blue|13|105|172
24|Bright yellow|245|205|48
25|Earth orange|98|71|50
26|Black|27|42|53
27|Dark grey|109|110|108
28|Dark green|40|127|71
29|Medium green|161|196|140
36|Lig. Yellowich orange|243|207|155
37|Bright green|75|151|75
38|Dark orange|160|95|53
39|Light bluish violet|193|202|222
40|Transparent|236|236|236
41|Tr. Red|205|84|75
42|Tr. Lg blue|193|223|240
43|Tr. Blue|123|182|232
44|Tr. Yellow|247|241|141
45|Light blue|180|210|228
47|Tr. Flu. Reddish orange|217|133|108
48|Tr. Green|132|182|141
49|Tr. Flu. Green|248|241|132
50|Phosph. White|236|232|222
100|Light red|238|196|182
101|Medium red|218|134|122
102|Medium blue|110|153|202
103|Light grey|199|193|183
104|Bright violet|107|50|124
105|Br. yellowish orange|226|155|64
106|Bright orange|218|133|65
107|Bright bluish green|0|143|156
108|Earth yellow|104|92|67
110|Bright bluish violet|67|84|147
111|Tr. Brown|191|183|177
112|Medium bluish violet|104|116|172
113|Tr. Medi. reddish violet|229|173|200
115|Med. yellowish green|199|210|60
116|Med. bluish green|85|165|175
118|Light bluish green|183|215|213
119|Br. yellowish green|164|189|71
120|Lig. yellowish green|217|228|167
121|Med. yellowish orange|231|172|88
123|Br. reddish orange|211|111|76
124|Bright reddish violet|146|57|120
125|Light orange|234|184|146
126|Tr. Bright bluish violet|165|165|203
127|Gold|220|188|129
128|Dark nougat|174|122|89
131|Silver|156|163|168
133|Neon orange|213|115|61
134|Neon green|216|221|86
135|Sand blue|116|134|157
136|Sand violet|135|124|144
137|Medium orange|224|152|100
138|Sand yellow|149|138|115
140|Earth blue|32|58|86
141|Earth green|39|70|45
143|Tr. Flu. Blue|207|226|247
145|Sand blue metallic|121|136|161
146|Sand violet metallic|149|142|163
147|Sand yellow metallic|147|135|103
148|Dark grey metallic|87|88|87
149|Black metallic|22|29|50
150|Light grey metallic|171|173|172
151|Sand green|120|144|130
153|Sand red|149|121|119
154|Dark red|123|46|47
157|Tr. Flu. Yellow|255|246|123
158|Tr. Flu. Red|225|164|194
168|Gun metallic|117|108|98
176|Red flip/flop|151|105|91
178|Yellow flip/flop|180|132|85
179|Silver flip/flop|137|135|136
180|Curry|215|169|75
190|Fire Yellow|249|214|46
191|Flame yellowish orange|232|171|45
192|Reddish brown|105|64|40
193|Flame reddish orange|207|96|36
194|Medium stone grey|163|162|165
195|Royal blue|70|103|164
196|Dark Royal blue|35|71|139
198|Bright reddish lilac|142|66|133
199|Dark stone grey|99|95|98
200|Lemon metalic|130|138|93
208|Light stone grey|229|228|223
209|Dark Curry|176|142|68
210|Faded green|112|149|120
211|Turquoise|121|181|181
212|Light Royal blue|159|195|233
213|Medium Royal blue|108|129|183
216|Rust|144|76|42
217|Brown|124|92|70
218|Reddish lilac|150|112|159
219|Lilac|107|98|155
220|Light lilac|167|169|206
221|Bright purple|205|98|152
222|Light purple|228|173|200
223|Light pink|220|144|149
224|Light brick yellow|240|213|160
225|Warm yellowish orange|235|184|127
226|Cool yellow|253|234|141
232|Dove blue|125|187|221
268|Medium lilac|52|43|117
301|Slime green|80|109|84
302|Smoky grey|91|93|105
303|Dark blue|0|16|176
304|Parsley green|44|101|29
305|Steel blue|82|124|174
306|Storm blue|51|88|130
307|Lapis|16|42|220
308|Dark indigo|61|21|133
309|Sea green|52|142|64
310|Shamrock|91|154|76
311|Fossil|159|161|172
312|Mulberry|89|34|89
313|Forest green|31|128|29
314|Cadet blue|159|173|192
315|Electric blue|9|137|207
316|Eggplant|123|0|123
317|Moss|124|156|107
318|Artichoke|138|171|133
319|Sage green|185|196|177
320|Ghost grey|202|203|209
321|Lilac|167|94|155
322|Plum|123|47|123
323|Olivine|148|190|129
324|Laurel green|168|189|153
325|Quill grey|223|223|222
327|Crimson|151|0|0
328|Mint|177|229|166
329|Baby blue|152|194|219
330|Carnation pink|255|152|220
331|Persimmon|255|89|89
332|Maroon|117|0|0
333|Gold|239|184|56
334|Daisy orange|248|217|109
335|Pearl|231|231|236
336|Fog|199|212|228
337|Salmon|255|148|148
338|Terra Cotta|190|104|98
339|Cocoa|86|36|36
340|Wheat|241|231|199
341|Buttermilk|254|243|187
342|Mauve|224|178|208
343|Sunrise|212|144|189
344|Tawny|150|85|85
345|Rust|143|76|42
346|Cashmere|211|190|150
347|Khaki|226|220|188
348|Lily white|237|234|234
349|Seashell|233|218|218
350|Burgundy|136|62|62
351|Cork|188|155|93
352|Burlap|199|172|120
353|Beige|202|191|163
354|Oyster|187|179|178
355|Pine Cone|108|88|75
356|Fawn brown|160|132|79
357|Hurricane grey|149|137|136
358|Cloudy grey|171|168|158
359|Linen|175|148|131
360|Copper|150|103|102
361|Medium brown|86|66|54
362|Bronze|126|104|63
363|Flint|105|102|92
364|Dark taupe|90|76|66
365|Burnt Sienna|106|57|9
1001|Institutional white|248|248|248
1002|Mid gray|205|205|205
1003|Really black|17|17|17
1004|Really red|255|0|0
1005|Deep orange|255|176|0
1006|Alder|180|128|255
1007|Dusty Rose|163|75|75
1008|Olive|193|190|66
1009|New Yeller|255|255|0
1010|Really blue|0|0|255
1011|Navy blue|0|32|96
1012|Deep blue|33|84|185
1013|Cyan|4|175|236
1014|CGA brown|170|85|0
1015|Magenta|170|0|170
1016|Pink|255|102|204
1017|Deep orange|255|175|0
1018|Teal|18|238|212
1019|Toothpaste|0|255|255
1020|Lime green|0|255|0
1021|Camo|58|125|21
1022|Grime|127|142|100
1023|Lavender|140|91|159
1024|Pastel light blue|175|221|255
1025|Pastel orange|255|201|201
1026|Pastel violet|177|167|255
1027|Pastel blue-green|159|243|233
1028|Pastel green|204|255|204
1029|Pastel yellow|255|255|204
1030|Pastel brown|255|204|153
1031|Royal purple|98|37|209
1032|Hot pink|255|0|191
""".strip()


def _load_catalog() -> dict[int, BrickColorData]:
    rows: dict[int, BrickColorData] = {}
    for line in _BRICK_COLOR_ROWS.splitlines():
        number_text, name, red_text, green_text, blue_text = line.split('|')
        number = int(number_text)
        rows[number] = BrickColorData(
            number=number,
            name=name,
            rgb=(int(red_text), int(green_text), int(blue_text)),
            palette_index=BRICK_COLOR_ID_TO_PALETTE_INDEX.get(number),
        )
    return rows


BRICK_COLOR_DATA: dict[int, BrickColorData] = _load_catalog()


BRICK_COLOR_ID_BY_NAME: dict[str, int] = {}
for _number, _entry in sorted(BRICK_COLOR_DATA.items()):
    BRICK_COLOR_ID_BY_NAME.setdefault(_entry.name, _number)


@dataclass(frozen=True, slots=True, init=False)
class BrickColor:
    """Python representation of Roblox BrickColor."""

    _number: int

    DEFAULT_NUMBER: ClassVar[int] = 194

    def __init__(self, number: int = DEFAULT_NUMBER) -> None:
        valid_number = number if number in BRICK_COLOR_DATA else self.DEFAULT_NUMBER
        object.__setattr__(self, '_number', valid_number)

    @classmethod
    def new(
        cls,
        value: int | float | str | Color3 = DEFAULT_NUMBER,
        green: float | None = None,
        blue: float | None = None,
    ) -> BrickColor:
        if green is not None or blue is not None:
            if green is None or blue is None:
                raise TypeError(
                    "BrickColor.new(r, g, b) requires all three channels"
                )

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    "BrickColor.new(r, g, b) requires numeric RGB components"
                )

            return cls.from_rgb(float(value), green, blue)
        if isinstance(value, Color3):
            return cls.from_color3(value)
        if isinstance(value, str):
            return cls(BRICK_COLOR_ID_BY_NAME.get(value, cls.DEFAULT_NUMBER))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = int(value)
            if number == value:
                return cls(number)
        raise TypeError(
            'BrickColor.new expects a number, name, Color3, or three RGB components'
        )

    @classmethod
    def from_rgb(cls, red: float, green: float, blue: float) -> BrickColor:
        return cls.from_color3(Color3(red, green, blue))

    @classmethod
    def from_color3(cls, color: Color3) -> BrickColor:
        if not isinstance(color, Color3):
            raise TypeError('color must be a Color3')
        target = (color.r * 255.0, color.g * 255.0, color.b * 255.0)
        nearest_number = min(
            BRICK_COLOR_DATA,
            key=lambda number: sum(
                (channel - target_channel) ** 2
                for channel, target_channel in zip(BRICK_COLOR_DATA[number].rgb, target)
            ),
        )
        return cls(nearest_number)

    @classmethod
    def palette(cls, palette_index: int) -> BrickColor:
        if isinstance(palette_index, bool) or not isinstance(palette_index, int):
            raise TypeError('palette index must be an integer')
        if not 0 <= palette_index < len(PALETTE_INDEX_TO_BRICK_COLOR_ID):
            raise ValueError('palette index must be in [0, 127]')
        return cls(PALETTE_INDEX_TO_BRICK_COLOR_ID[palette_index])

    @classmethod
    def random(cls) -> BrickColor:
        return cls.palette(_random.randrange(len(PALETTE_INDEX_TO_BRICK_COLOR_ID)))

    @classmethod
    def white(cls) -> BrickColor:
        return cls(1)

    @classmethod
    def gray(cls) -> BrickColor:
        return cls(194)

    @classmethod
    def dark_gray(cls) -> BrickColor:
        return cls(199)

    @classmethod
    def black(cls) -> BrickColor:
        return cls(26)

    @classmethod
    def red(cls) -> BrickColor:
        return cls(21)

    @classmethod
    def yellow(cls) -> BrickColor:
        return cls(24)

    @classmethod
    def green(cls) -> BrickColor:
        return cls(28)

    @classmethod
    def blue(cls) -> BrickColor:
        return cls(23)

    @property
    def data(self) -> BrickColorData:
        return BRICK_COLOR_DATA[self._number]

    @property
    def number(self) -> int:
        return self._number

    @property
    def Number(self) -> int:
        return self.number

    @property
    def name(self) -> str:
        return self.data.name

    @property
    def Name(self) -> str:
        return self.name

    @property
    def palette_index(self) -> int | None:
        return self.data.palette_index

    @property
    def palette_id(self) -> int | None:
        """Alias for palette_index; None means the color is not in Studio's palette."""
        return self.palette_index

    @property
    def r(self) -> float:
        return self.data.rgb[0] / 255.0

    @property
    def g(self) -> float:
        return self.data.rgb[1] / 255.0

    @property
    def b(self) -> float:
        return self.data.rgb[2] / 255.0

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.data.rgb

    @property
    def hex(self) -> str:
        return self.data.hex

    @property
    def color(self) -> Color3:
        return self.data.color3

    @property
    def Color(self) -> Color3:
        return self.color

    @classmethod
    def White(cls) -> BrickColor:
        return cls.white()

    @classmethod
    def Gray(cls) -> BrickColor:
        return cls.gray()

    @classmethod
    def DarkGray(cls) -> BrickColor:
        return cls.dark_gray()

    @classmethod
    def Black(cls) -> BrickColor:
        return cls.black()

    @classmethod
    def Red(cls) -> BrickColor:
        return cls.red()

    @classmethod
    def Yellow(cls) -> BrickColor:
        return cls.yellow()

    @classmethod
    def Green(cls) -> BrickColor:
        return cls.green()

    @classmethod
    def Blue(cls) -> BrickColor:
        return cls.blue()

    def __str__(self) -> str:
        return self.name


BRICK_COLORS: dict[int, BrickColor] = {
    number: BrickColor(number) for number in BRICK_COLOR_DATA
}
BRICK_COLORS_BY_NAME: dict[str, BrickColor] = {
    name: BRICK_COLORS[number] for name, number in BRICK_COLOR_ID_BY_NAME.items()
}
BRICK_COLOR_PALETTE: dict[int, BrickColor] = {
    palette_index: BRICK_COLORS[number]
    for palette_index, number in enumerate(PALETTE_INDEX_TO_BRICK_COLOR_ID)
}


def get_brick_color(color_id: int) -> BrickColor:
    """Look up by BrickColor number; raises KeyError if the ID is not in the catalog."""
    return BRICK_COLORS[color_id]


def get_brick_color_by_palette_id(palette_id: int) -> BrickColor:
    """Look up by zero-based Studio palette index (0 through 127)."""
    return BrickColor.palette(palette_id)


def find_brick_colors(name: str) -> list[BrickColor]:
    """Case-insensitive substring search across all BrickColor names."""
    normalized = name.casefold()
    return [
        BRICK_COLORS[number]
        for number, data in BRICK_COLOR_DATA.items()
        if normalized in data.name.casefold()
    ]


def find_brick_colors_by_rgb(red: int, green: int, blue: int) -> list[BrickColor]:
    """Return every BrickColor whose RGB value exactly matches the given channels."""
    rgb = (red, green, blue)
    return [
        BRICK_COLORS[number]
        for number, data in BRICK_COLOR_DATA.items()
        if data.rgb == rgb
    ]


if len(BRICK_COLOR_DATA) != 208:
    raise RuntimeError(f'Expected 208 BrickColors, loaded {len(BRICK_COLOR_DATA)}')
if len(PALETTE_INDEX_TO_BRICK_COLOR_ID) != 128:
    raise RuntimeError(
        f'Expected 128 palette entries, got {len(PALETTE_INDEX_TO_BRICK_COLOR_ID)}'
    )
if any(
    color_id not in BRICK_COLOR_DATA for color_id in PALETTE_INDEX_TO_BRICK_COLOR_ID
):
    raise RuntimeError('Palette refers to an unknown BrickColor number')
