![Presentation](documentation/img/tiny5-presentation.jpg)

# Tiny5

**Tiny5** is a compact 5-pixel variable font that captures the essence of 1980s–90s digital minimalism. Inspired by the graphing calculators and digital gadgets of the era, it distills letterforms to their absolute essentials—proving that even with just five pixels of height, clarity, charm, and character can coexist.

It features three variable axes—**weight, roundness, and bleed**—that let you fine-tune the appearance: from crisp geometric forms and clean LCD edges to the warm glow of CRT monitors and the slight ink spread of dot-matrix printouts. A **Tiny5 Duo** variant has also been added for stronger emphasis while preserving the pixel-perfect aesthetic.

Tiny5 excels at evoking retro-futurism, minimalism, and constrained-tech nostalgia. It’s especially effective for:

- Pixel art & lo-fi games
- Terminal-style interfaces and embedded displays
- Micro-typography in UI/UX
- Branding with a distinct 8/16-bit or vintage digital vibe

Tiny5 provides broad language support including:

- **Latin**: Google Fonts Latin Kernel + Core + Plus + Beyond + African + PriAfrican + Vietnamese
- **Greek**: Core + Plus + Pro
- **Cyrillic**: Core + Plus

For pixel-perfect rendering, use font sizes that are **multiples of 6 points**.

The font is also available in [BDF](https://en.wikipedia.org/wiki/Glyph_Bitmap_Distribution_Format) format for easy integration with the [mcu-renderer](https://github.com/Gissio/mcu-renderer), [u8g2](https://github.com/olikraus/u8g2) and [TFT_eSPI](https://github.com/Bodmer/TFT_eSPI) libraries.

![Tiny5 speciment](documentation/img/tiny5-sample1.jpg)

![Tiny5 Duo speciment](documentation/img/tiny5-sample2.jpg)

![Font features](documentation/img/tiny5-sample3.jpg)

![Font samples](documentation/img/tiny5-sample4.jpg)

## About

Stefan Schmidt is an electrical engineer with graduate studies in signal processing, multimodal artistic languages and sociology. Fascinated by the interplay between the virtual and the real, his work probes the boundaries between perception and technology.

Learn more at [http://www.stefanschmidtart.com](http://www.stefanschmidtart.com).

## Building

Fonts are built automatically by GitHub Actions - take a look in the "Actions" tab for the latest build.

If you want to build fonts manually on your own computer:

- `make build` will produce font files.
- `make test` will run [Fontspector](https://fonttools.github.io/fontspector/)'s quality assurance tests.
- `make proof` will generate HTML proof files.

## Changelog

### 2.003

- Fixes: latin uppercase q, latin lowercase x, comma, semicolon, double angle quotation marks, double acute, double grave, latin small sharp s, greek capital delta, greek capital xi, greek lowercase epsilon, greek lowercase phi, greek lowercase psi, greek descenders, various diacritics.

### 2.002

- Fixes: percent sign, latin lowercase j, cyrillic, hooks and descenders.

### 2.001

- Minor fixes.

### 2.000

- Added variable font support with axes for: element size, roundness and bleed.
- Added Duo weight.
- Added vietnamese support (Google Fonts Latin Vietnamese character set).
- Added Google Fonts Latin Beyond, Latin PriAfrican, Greek Plus and Greek Pro character sets.
- Improved build workflow with [bdf2ufo](https://github.com/Gissio/bdf2ufo).
- Major corrections to the greek and cyrillic character sets.
- Updated presentation image and samples.

### 1.002

- Added Google Fonts Greek Core, Cyrillic Core and Cyrillic Plus character sets.

### 1.001

- Added Google Fonts Latin Plus and Latin African character sets.
- Major corrections.

### 1.000

- First release.

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at https://openfontlicense.org
