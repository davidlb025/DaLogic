# This Python file uses the following encoding: utf-8
# This file is only for people who want to modify the UI

import os

PATH = ""

def convert():
    files = ["ventana1","credits"]
    for i in files:
            os.system(f'"{PATH}/pyside6-uic.exe" --from-imports ui/{i}.ui -o compiled/ui_{i}.py')



    files = ["img"]
    for i in files:
        os.system(f'"{PATH}/pyside6-rcc.exe" resources/{i}.qrc -o compiled/{i}_rc.py')
