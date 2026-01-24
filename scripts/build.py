# This Python file uses the following encoding: utf-8
# This file is only for people who want to modify the UI

import os

def convert():
    files = ["ventana1","credits","config"]
    for i in files:
            os.system(f'"QtCreatorExes\\pyside6-uic.exe" --from-imports resources/ui/{i}.ui -o resources/compiled/ui_{i}.py')



    files = ["img"]
    for i in files:
        os.system(f'"QtCreatorExes\\pyside6-rcc.exe" resources/{i}.qrc -o resources/compiled/{i}_rc.py')
