"""
bdf2ufo

Data definitions and constants for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

# Definitions

WIDTH_CLASSES = {
    "UltraCondensed": 1,
    "ExtraCondensed": 2,
    "Condensed": 3,
    "SemiCondensed": 4,
    "Normal": 5,
    "SemiExpanded": 6,
    "Expanded": 7,
    "ExtraExpanded": 8,
    "UltraExpanded": 9,
}

# Maps the "wdth" axis value to the width class name, as defined by the
# OpenType OS/2 usWidthClass specification.
WIDTH_NAME_FROM_WDTH = {
    50: "UltraCondensed",
    62.5: "ExtraCondensed",
    75: "Condensed",
    87.5: "SemiCondensed",
    100: "Normal",
    112.5: "SemiExpanded",
    125: "Expanded",
    150: "ExtraExpanded",
    200: "UltraExpanded",
}

WIDTH_CLASS_FROM_WDTH = {
    wdth_value: WIDTH_CLASSES[width_name]
    for wdth_value, width_name in WIDTH_NAME_FROM_WDTH.items()
}

WEIGHT_CLASSES = {
    "Thin": 100,
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
    "Black": 900,
}

WEIGHT_NAME_FROM_WGHT = {
    weight_class: weight_name for weight_name, weight_class in WEIGHT_CLASSES.items()
}

# The style names Google Fonts accepts in a font's style name. Any other style
# name component becomes part of the family name instead.
STATIC_STYLES = set(WEIGHT_CLASSES) | {"Italic"}

# The italic angle, in degrees, of a fully italic ("ital" = 1) master.
DEFAULT_ITALIC_ANGLE = 12.0

SLOPE_FROM_SLANT = {
    "I": "Italic",
    "RI": "Italic",
    "O": "Oblique",
    "RO": "Oblique",
}

# Maps a representative character to the OpenType script tag and the BCP 47
# script subtag of the script it belongs to. The former is used for the
# "languagesystem" statements of the feature file, the latter for the
# "dlng"/"slng" fields of the OpenType meta table. Both tags are listed
# explicitly because they do not match for every script (Lao, for instance,
# is "lao " and "Laoo").
SCRIPTS = {
    "\u0041": ("latn", "Latn"),  # Latin capital letter a
    "\u0391": ("grek", "Grek"),  # Greek capital letter alpha
    "\u0410": ("cyrl", "Cyrl"),  # Cyrillic capital letter a
    "\u0531": ("armn", "Armn"),  # Armenian capital letter ayb
    "\u4e2d": ("hani", "Hani"),  # CJK unified ideograph 4e2d
    "\uac00": ("hang", "Hang"),  # Hangul syllable ga
}

CUSTOM_DECOMPOSITIONS = {
    "\u0069": "0131 0307",  # Dotless i with dot above
    "\u006a": "0237 0307",  # Dotless j with dot above
    "\u00ec": "0131 0300",  # Dotless i with grave
    "\u00ed": "0131 0301",  # Dotless i with acute
    "\u00ee": "0131 0302",  # Dotless i with circumflex
    "\u00ef": "0131 0308",  # Dotless i with diaeresis
    "\u010f": "0064 0313",  # d with apostrophe for Czech, Slovak
    "\u0122": "0047 0326",  # G with comma below for Latvian
    "\u0123": "0067 0312",  # g with comma above for Latvian
    "\u0129": "0131 0303",  # Dotless i with tilde
    "\u012b": "0131 0304",  # Dotless i with macron
    "\u012d": "0131 0306",  # Dotless i with breve
    "\u0135": "0237 0302",  # Dotless j with circumflex
    "\u0136": "004B 0326",  # K with comma below for Latvian
    "\u0137": "006B 0326",  # k with comma below for Latvian
    "\u013b": "004C 0326",  # L with comma below for Latvian
    "\u013c": "006C 0326",  # l with comma below for Latvian
    "\u013d": "004C 0313",  # L with apostrophe for Slovak
    "\u013e": "006C 0313",  # l with apostrophe for Slovak
    "\u0145": "004E 0326",  # N with comma below for Latvian
    "\u0146": "006E 0326",  # n with comma below for Latvian
    "\u0156": "0052 0326",  # R with comma below for Latvian
    "\u0157": "0072 0326",  # r with comma below for Latvian
    "\u0165": "0074 0313",  # t with apostrophe for Czech, Slovak
    "\u017f": "",  # Long s
    "\u01d0": "0131 030c",  # Dotless i with caron
    "\u01f0": "0237 030c",  # Dotless j with caron
    "\u0209": "0131 030f",  # Dotless i with double grave
    "\u020b": "0131 0311",  # Dotless i with inverted grave
    "\u03d0": "",           # Greek beta symbol
    "\u03d1": "",           # Greek theta symbol
    "\u03d2": "",           # Greek upsilon with hook symbol
    "\u03d5": "",           # Greek phi symbol
    "\u03d6": "",           # Greek pi symbol
    "\u03f0": "",           # Greek kappa symbol
    "\u03f1": "",           # Greek rho symbol
    "\u03f2": "",           # Greek lunate sigma symbol
    "\u03f4": "",           # Greek capital theta symbol
    "\u03f5": "",           # Greek lunate epsilon symbol
    "\u03f9": "",           # Greek capital lunate sigma symbol
    "\u0457": "0131 0308",  # Dotless i with diaeresis for Ukrainian
    "\u1ec9": "0131 0309",  # Dotless i with hook above
    "\u1f02": "03b1 1fcd",  # Small alpha with psili and varia
    "\u1f03": "03b1 1fdd",  # Small alpha with dasia and varia
    "\u1f04": "03b1 1fce",  # Small alpha with psili and oxia
    "\u1f05": "03b1 1fde",  # Small alpha with dasia and oxia
    "\u1f0a": "0391 1fcd",  # Capital alpha with psili and varia
    "\u1f0b": "0391 1fdd",  # Capital alpha with dasia and varia
    "\u1f0c": "0391 1fce",  # Capital alpha with psili and oxia
    "\u1f0d": "0391 1fde",  # Capital alpha with dasia and oxia
    "\u1f12": "03b5 1fcd",  # Small epsilon with psili and varia
    "\u1f13": "03b5 1fdd",  # Small epsilon with dasia and varia
    "\u1f14": "03b5 1fce",  # Small epsilon with psili and oxia
    "\u1f15": "03b5 1fde",  # Small epsilon with dasia and oxia
    "\u1f1a": "0395 1fcd",  # Capital epsilon with psili and varia
    "\u1f1b": "0395 1fdd",  # Capital epsilon with dasia and varia
    "\u1f1c": "0395 1fce",  # Capital epsilon with psili and oxia
    "\u1f1d": "0395 1fde",  # Capital epsilon with dasia and oxia
    "\u1f22": "03b7 1fcd",  # Small eta with psili and varia
    "\u1f23": "03b7 1fdd",  # Small eta with dasia and varia
    "\u1f24": "03b7 1fce",  # Small eta with psili and oxia
    "\u1f25": "03b7 1fde",  # Small eta with dasia and oxia
    "\u1f2a": "0397 1fcd",  # Capital eta with psili and varia
    "\u1f2b": "0397 1fdd",  # Capital eta with dasia and varia
    "\u1f2c": "0397 1fce",  # Capital eta with psili and oxia
    "\u1f2d": "0397 1fde",  # Capital eta with dasia and oxia
    "\u1f32": "03b9 1fcd",  # Small iota with psili and varia
    "\u1f33": "03b9 1fdd",  # Small iota with dasia and varia
    "\u1f34": "03b9 1fce",  # Small iota with psili and oxia
    "\u1f35": "03b9 1fde",  # Small iota with dasia and oxia
    "\u1f3a": "0399 1fcd",  # Capital iota with psili and varia
    "\u1f3b": "0399 1fdd",  # Capital iota with dasia and varia
    "\u1f3c": "0399 1fce",  # Capital iota with psili and oxia
    "\u1f3d": "0399 1fde",  # Capital iota with dasia and oxia
    "\u1f42": "03bf 1fcd",  # Small omicron with psili and varia
    "\u1f43": "03bf 1fdd",  # Small omicron with dasia and varia
    "\u1f44": "03bf 1fce",  # Small omicron with psili and oxia
    "\u1f45": "03bf 1fde",  # Small omicron with dasia and oxia
    "\u1f4a": "039f 1fcd",  # Capital omicron with psili and varia
    "\u1f4b": "039f 1fdd",  # Capital omicron with dasia and varia
    "\u1f4c": "039f 1fce",  # Capital omicron with psili and oxia
    "\u1f4d": "039f 1fde",  # Capital omicron with dasia and oxia
    "\u1f52": "03c5 1fcd",  # Small upsilon with psili and varia
    "\u1f53": "03c5 1fdd",  # Small upsilon with dasia and varia
    "\u1f54": "03c5 1fce",  # Small upsilon with psili and oxia
    "\u1f55": "03c5 1fde",  # Small upsilon with dasia and oxia
    "\u1f5b": "03a5 1fdd",  # Capital upsilon with dasia and varia
    "\u1f5d": "03a5 1fde",  # Capital upsilon with dasia and oxia
    "\u1f62": "03c9 1fcd",  # Small omega with psili and varia
    "\u1f63": "03c9 1fdd",  # Small omega with dasia and varia
    "\u1f64": "03c9 1fce",  # Small omega with psili and oxia
    "\u1f65": "03c9 1fde",  # Small omega with dasia and oxia
    "\u1f6a": "03a9 1fcd",  # Capital omega with psili and varia
    "\u1f6b": "03a9 1fdd",  # Capital omega with dasia and varia
    "\u1f6c": "03a9 1fce",  # Capital omega with psili and oxia
    "\u1f6d": "03a9 1fde",  # Capital omega with dasia and oxia
    "\u1fbe": "037a",  # Greek prosgegrammeni
    "\u2116": "004e 00ba",  # Numero sign with N and masculine ordinal indicator
}

MARKS = {
    "\u0300": ("top", 2),  # Grave
    "\u0301": ("top", 1),  # Acute
    "\u0302": ("top", 0),  # Circumflex
    "\u0303": ("top", 2),  # Tilde
    "\u0304": ("top", 0),  # Macron
    "\u0305": ("top", 0),  # Overline
    "\u0306": ("top", 0),  # Breve
    "\u0307": ("top", 0),  # Dot above
    "\u0308": ("top", 0),  # Diaeresis
    "\u0309": ("top", 2),  # Hook above
    "\u030a": ("top", 0),  # Ring above
    "\u030b": ("top", 1),  # Double acute
    "\u030c": ("top", 0),  # Caron
    "\u030d": ("top", 0),  # Vertical line above
    "\u030e": ("top", 0),  # Double vertical line above
    "\u030f": ("top", 2),  # Double grave above
    "\u0310": ("top", 0),  # Candrabindu
    "\u0311": ("top", 0),  # Inverted breve
    "\u0312": ("top", 0),  # Turned comma above
    "\u0313": ("top", 0),  # Comma above
    "\u0314": ("top", 0),  # Reversed comma above
    "\u0315": ("topRight", 0),  # Comma above right
    "\u031b": ("horn", 0),  # Horn for Vietnamese
    "\u0320": ("bottom", 0),  # Minus sign below
    "\u0323": ("bottom", 0),  # Dot below
    "\u0324": ("bottom", 0),  # Diaeresis below
    "\u0325": ("bottom", 0),  # Ring below
    "\u0326": ("bottom", 0),  # Comma below
    "\u0327": ("bottom", 2),  # Cedilla
    "\u0328": ("ogonek", 0),  # Ogonek
    "\u0329": ("bottom", 0),  # Vertical line below
    "\u032d": ("bottom", 0),  # Circumflex below
    "\u032e": ("bottom", 0),  # Breve below
    "\u032f": ("bottom", 0),  # Inverted breve below
    "\u0330": ("bottom", 2),  # Tilde below
    "\u0331": ("bottom", 0),  # Macron below
    "\u0332": ("top", 0),  # Low line
    "\u0334": ("center", 0),  # Tilde overlay
    "\u0335": ("center", 0),  # Short stroke overlay
    "\u0337": ("center", 0),  # Short solidus overlay
    "\u0338": ("center", 0),  # Long solidus overlay
    "\u0342": ("top", 2),  # Perispomeni for Greek
    "\u0343": ("top", 0),  # Koronis for Greek
    "\u0344": ("top", 0),  # Dialytika tonos for Greek
    "\u0345": ("bottom", 0),  # Ypogegrammeni for Greek
    "\u0358": ("topRight", 0),  # Dot above right
    "\u0359": ("bottom", 0),  # Asterisk below
    "\u035c": ("bottom", 2),  # Double breve below
    "\u035f": ("bottom", 2),  # Double macron below
    "\u0361": ("top", 2),  # Double inverted breve
    "\u1dc4": ("top", 0),  # Macron acute
    "\u1dc5": ("top", 0),  # Grave macron
    "\u1dc6": ("top", 0),  # Macron grave
    "\u1dc7": ("top", 0),  # Acute macron
    "\u1dca": ("bottom", 0),  # Small r below
}

BASE_ANCHORS_EXCEPTIONS = [
    "\u0386",  # Greek capital alpha with tonos
    "\u0388",  # Greek capital epsilon with tonos
    "\u0389",  # Greek capital eta with tonos
    "\u038a",  # Greek capital iota with tonos
    "\u038c",  # Greek capital omicron with tonos
    "\u038e",  # Greek capital upsilon with tonos
    "\u038f",  # Greek capital omega with tonos
    "\u1f02",  # Greek small alpha with psili and varia
    "\u1f03",  # Greek small alpha with dasia and varia
    "\u1f04",  # Greek small alpha with psili and oxia
    "\u1f05",  # Greek small alpha with dasia and oxia
    "\u1f08",  # Greek capital alpha with psili
    "\u1f09",  # Greek capital alpha with dasia
    "\u1f0a",  # Greek capital alpha with psili and varia
    "\u1f0b",  # Greek capital alpha with dasia and varia
    "\u1f0c",  # Greek capital alpha with psili and oxia
    "\u1f0d",  # Greek capital alpha with dasia and oxia
    "\u1f12",  # Greek small epsilon with psili and varia
    "\u1f13",  # Greek small epsilon with dasia and varia
    "\u1f14",  # Greek small epsilon with psili and oxia
    "\u1f15",  # Greek small epsilon with dasia and oxia
    "\u1f18",  # Greek capital epsilon with psili
    "\u1f19",  # Greek capital epsilon with dasia
    "\u1f1a",  # Greek capital epsilon with psili and varia
    "\u1f1b",  # Greek capital epsilon with dasia and varia
    "\u1f1c",  # Greek capital epsilon with psili and oxia
    "\u1f1d",  # Greek capital epsilon with dasia and oxia
    "\u1f22",  # Greek small eta with psili and varia
    "\u1f23",  # Greek small eta with dasia and varia
    "\u1f24",  # Greek small eta with psili and oxia
    "\u1f25",  # Greek small eta with dasia and oxia
    "\u1f28",  # Greek capital eta with psili
    "\u1f29",  # Greek capital eta with dasia
    "\u1f2a",  # Greek capital eta with psili and varia
    "\u1f2b",  # Greek capital eta with dasia and varia
    "\u1f2c",  # Greek capital eta with psili and oxia
    "\u1f2d",  # Greek capital eta with dasia and oxia
    "\u1f32",  # Greek small iota with psili and varia
    "\u1f33",  # Greek small iota with dasia and varia
    "\u1f34",  # Greek small iota with psili and oxia
    "\u1f35",  # Greek small iota with dasia and oxia
    "\u1f38",  # Greek capital iota with psili
    "\u1f39",  # Greek capital iota with dasia
    "\u1f3a",  # Greek capital iota with psili and varia
    "\u1f3b",  # Greek capital iota with dasia and varia
    "\u1f3c",  # Greek capital iota with psili and oxia
    "\u1f3d",  # Greek capital iota with dasia and oxia
    "\u1f42",  # Greek small omicron with psili and varia
    "\u1f43",  # Greek small omicron with dasia and varia
    "\u1f44",  # Greek small omicron with psili and oxia
    "\u1f45",  # Greek small omicron with dasia and oxia
    "\u1f48",  # Greek capital omicron with psili
    "\u1f49",  # Greek capital omicron with dasia
    "\u1f4a",  # Greek capital omicron with psili and varia
    "\u1f4b",  # Greek capital omicron with dasia and varia
    "\u1f4c",  # Greek capital omicron with psili and oxia
    "\u1f4d",  # Greek capital omicron with dasia and oxia
    "\u1f52",  # Greek small upsilon with psili and varia
    "\u1f53",  # Greek small upsilon with dasia and varia
    "\u1f54",  # Greek small upsilon with psili and oxia
    "\u1f55",  # Greek small upsilon with dasia and oxia
    "\u1f59",  # Greek capital upsilon with dasia
    "\u1f5b",  # Greek capital upsilon with dasia and varia
    "\u1f5d",  # Greek capital upsilon with dasia and oxia
    "\u1f62",  # Greek small omega with psili and varia
    "\u1f63",  # Greek small omega with dasia and varia
    "\u1f64",  # Greek small omega with psili and oxia
    "\u1f65",  # Greek small omega with dasia and oxia
    "\u1f68",  # Greek capital omega with psili
    "\u1f69",  # Greek capital omega with dasia
    "\u1f6a",  # Greek capital omega with psili and varia
    "\u1f6b",  # Greek capital omega with dasia and varia
    "\u1f6c",  # Greek capital omega with psili and oxia
    "\u1f6d",  # Greek capital omega with dasia and oxia
]

CCMP_SOFTDOT_DECOMPOSITION = {
    "\u012f": ("i", "\u0328"),  # i with ogonek
    "\u0456": ("i"),  # Cyrillic i
    "\u1e2d": ("i", "\u0330"),  # i with tilde below
    "\u1ecb": ("i", "\u0323"),  # i with dot below
}

CCMP_SOFTDOT_COMPOSITION = {
    "i": "\u0131",
    "j": "\u0237",
    "\u0268": "\u1d7b",
}

# Maps the first word of a Unicode character name to the OpenType script tag
# of the smcp and c2sc lookups built for that script, and to its basic
# lowercase alphabet. The lookups of a script are only built when every letter
# of its alphabet in the font has a small cap, so that small caps text never
# mixes in lowercase.
SMALL_CAPS_SCRIPTS = {
    "LATIN": ("latn", "abcdefghijklmnopqrstuvwxyz"),
    "CYRILLIC": (
        "cyrl",
        "".join(chr(code_point) for code_point in range(0x0430, 0x0450)),
    ),
}

# Lowercase letters that are drawn as small capitals: most Cyrillic lowercase
# letters, and the Latin ones that are smaller forms of their capitals. They
# serve as their own small caps, with their accented forms, unless the font has
# a ".sc" glyph for them.
SMALL_CAPS_LOWERCASE = (
    "\u0432\u0433\u0434\u0436\u0437\u0438\u043a\u043b"  # в г д ж з и к л
    "\u043c\u043d\u043e\u043f\u0441\u0442\u0445\u0446"  # м н о п с т х ц
    "\u0447\u0448\u0449\u044a\u044b\u044c\u044d\u044e"  # ч ш щ ъ ы ь э ю
    "\u044f\u0454\u0455\u0459\u045a\u045f\u046b\u0473"  # я є ѕ љ њ џ ѫ ѳ
    "\u0475\u048b\u0491\u0493\u0495\u0497\u0499\u049b"  # ѵ ҋ ґ ғ ҕ җ ҙ қ
    "\u049d\u04a1\u04a3\u04a5\u04a7\u04a9\u04ab\u04ad"  # ҝ ҡ ң ҥ ҧ ҩ ҫ ҭ
    "\u04b3\u04b5\u04b7\u04b9\u04bd\u04bf\u04c4\u04c6"  # ҳ ҵ ҷ ҹ ҽ ҿ ӄ ӆ
    "\u04c8\u04ca\u04cc\u04ce\u04d9\u04e9\u04f7\u04fb"  # ӈ ӊ ӌ ӎ ә ө ӷ ӻ
    "\u04fd\u04ff\u0511\u0513\u051d\u0525\u0529\u052f"  # ӽ ӿ ԑ ԓ ԝ ԥ ԩ ԯ
    "\u00f8\u0149\u014b\u0188\u019e\u01b6\u023c\u0242"  # ø ŉ ŋ ƈ ƞ ƶ ȼ ɂ
    "\u024b\u0251\u0254\u0259\u0263\u026f\u0275\u028a"  # ɋ ɑ ɔ ə ɣ ɯ ɵ ʊ
    "\u028b\u028c\u2184\u2c73\ua793\ua7a9\ua7cd\uab53"  # ʋ ʌ ↄ ⱳ ꞓ ꞩ ꟍ ꭓ
)
# Lowercase letters without a small capital of their own, which take the small
# capital of another letter.
SMALL_CAPS_ALIASES = {
    "\u0131": "i",  # Dotless i
    "\u017f": "s",  # Long s
    "\u0237": "j",  # Dotless j
    "\u0138": "k",  # Kra, drawn like small capital k
    "\u0111": "\u00f0",  # D with stroke, drawn like eth
    "\u0256": "\u00f0",  # D with tail, drawn like eth
    "\u048d": "\u0463",  # Cyrillic semisoft sign, drawn like yat
    "\u04cf": "\u0456",  # Cyrillic palochka, drawn like dotless i
    "\u04e1": "\u0437",  # Cyrillic Abkhasian dze, drawn like ze
}

AXES_INFO = {
    "wght": {"name": "Weight", "min": 100, "max": 700, "default": 400},
    "wdth": {"name": "Width", "min": 50, "max": 200, "default": 100},
    "ital": {"name": "Italic", "min": 0, "max": 1, "default": 0},
    "ROND": {"name": "Roundness", "min": 0, "max": 100, "default": 0},
    "BLED": {"name": "Bleed", "min": 0, "max": 100, "default": 0},
    "JITT": {"name": "Jitter", "min": 0, "max": 100, "default": 0},
}
