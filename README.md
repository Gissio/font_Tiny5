![Presentation](documentation/img/tiny5-presentation.jpg)

# Tiny5

**Tiny5** is a compact 5-pixel font inspired by the graphing calculators and digital gadgets of the 1980s-90s, where the constraints of limited pixel space demanded efficient and minimalist design.

It features three variable axes—element size, roundness and bleed—allowing to mimic the visual qualities of LCD screens, CRT monitors and dot-matrix printouts.

Tiny5 is perfect at evoking retro-futurism, minimalism or contrained tech nostalgia. It's effective for pixel-art & lo-fi games, Terminal-style interfaces and branding with 8/16-bit vibe.

It covers the Google Fonts Latin Kernel, Latin Core, Latin Plus, Latin Beyond, Latin African, Latin PriAfrican, Latin Vietnamese, Greek Core, Greek Plus, Greek Pro, Cyrillic Core and Cyrillic Plus character set.

For crisp pixel-perfect results, use font sizes that are **multiples of 6 points**.

The font is also available in [BDF](https://en.wikipedia.org/wiki/Glyph_Bitmap_Distribution_Format) format for easy integration with the [mcu-renderer](https://github.com/Gissio/mcu-renderer), [u8g2](https://github.com/olikraus/u8g2) and [TFT_eSPI](https://github.com/Bodmer/TFT_eSPI) libraries.

![Tiny5 speciment](documentation/img/tiny5-sample1.jpg)

![Tiny5 Duo speciment](documentation/img/tiny5-sample2.jpg)

![Font features](documentation/img/tiny5-sample3.jpg)

![Font samples](documentation/img/tiny5-sample4.jpg)

## About

Stefan Schmidt is an electrical engineer with graduate studies in signal processing, combined artistic languages and sociology. Fascinated by the interplay between the virtual and the real, his work probes the boundaries between perception and technology.

Learn more at [http://www.stefanschmidtart.com](http://www.stefanschmidtart.com).

## Building

Fonts are built automatically by GitHub Actions - take a look in the "Actions" tab for the latest build.

If you want to build fonts manually on your own computer:

- `make build` will produce font files.
- `make test` will run [Fontspector](https://fonttools.github.io/fontspector/)'s quality assurance tests.
- `make proof` will generate HTML proof files.

## Changelog

### 2.003

- Fixes: latin uppercase Q, latin lowercase x, comma, semicolon, double angle quotation marks, double acute, double grave, latin small sharp s, greek capital delta, greek apital xi, greek lowercase epsilon, greek lowercase phi, greek lowercase psi, greek descenders, various diacritics.

### 2.002

- Fixes: percent sign, latin lowercase j, cyrillic, hooks and descenders.

### 2.001

- Minor fixes.

### 2.000

- Added variable font support with axes for: element size, roundness and bleed.
- Added bold weight.
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
