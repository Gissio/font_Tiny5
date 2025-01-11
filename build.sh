#!/bin/bash
if [ ! -d env ] ; then
  python -m venv env
  source env/bin/activate
  pip install -r requirements.txt
else
  source env/bin/activate
fi

# Variables
COMMON=('-v' '--designer' 'Stefan Schmidt' '--designer-url' 'https://github.com/Gissio/font_tiny5' '--manufacturer' 'Stefan Schmidt Art' '--manufacturer-url' 'https://www.stefanschmidtart.com/' '--license' 'This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: https://openfontlicense.org' '--license-url' 'https://openfontlicense.org' '--strikeout-position' '2' '--strikeout-thickness' '1' '--underline-position' '-1' '--underline-thickness' '1' '--notdef-codepoint' '0x0' '--glyph-offset-x' '0.5' '--variable-axes' 'ESIZ,ROND,BLED' --variable-instance 'Solid,ESIZ=1,ROND=0,BLED=0' --variable-instance 'LCD,ESIZ=0.85,ROND=0,BLED=0' --variable-instance 'CRT,ESIZ=0.7,ROND=0.8,BLED=0.64' --variable-instance 'Matrix,ESIZ=0.85,ROND=0.8,BLED=0' '--static-axes' 'ROND=1')

# Build Tiny5 Regular
python scripts/bdf2ufo.py "${COMMON[@]}" sources/Tiny5-Regular.bdf build
gftools builder build/Tiny5-Regular-config.yaml

# Build Tiny5 Bold
python scripts/bdf2ufo.py "${COMMON[@]}" sources/Tiny5-Bold.bdf build
gftools builder build/Tiny5-Bold-config.yaml

mkdir -p fonts/bdf
cp sources/*.bdf fonts/bdf
