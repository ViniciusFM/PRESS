import argparse
import mimetypes
import os, sys, subprocess
import tkinter.scrolledtext
import tkinter.simpledialog
import tkinter.ttk
import pypdf
import json
import re
import threading
import tkinter

# ------------ consts

APPNAME = 'PRESS'
VER     = '0.1'
WIN_W   = 1024
WIN_H   = 768

#pypdf.errors.PdfStreamError

'''reader = PdfReader("./fakerepo-ignore/chen2021.pdf")
np = len(reader.pages)
page = reader.pages[0]
text = page.extract_text()'''


# ------------ program arguments

def dirpath(dpath):
    if os.path.isdir(dpath):
        return dpath
    else:
        raise argparse.ArgumentTypeError(f"{dpath} should be a directory path.")

def build_args():
    parser = argparse.ArgumentParser(
        description=f'''{APPNAME} v{VER} - Pdf REpository String Search is
                     a tool for mapping pdf files based in a string search'''
    )
    parser.add_argument('--ics', action='store_true',
                        help='Ignore Case Sensitive search')
    parser.add_argument('--surc', 
                        help='''Surround context. The number of characteres surrounding
                        the matching area. Shown on GUI when right button is pressed
                        on the result.''', type=int, default=100)
    parser.add_argument('-v', action='store_true',
                        help='''Verbose. This option shows the program
                        status in text mode.''')
    parser.add_argument('dirpath',
                        help='''Define a path to the directory where the PDF
                                 files are.''',
                        type=dirpath)
    parser.add_argument('string',
                        help='''A string regex for the search''',
                        type=str)
    return parser.parse_args()

ARGS = build_args()

# ------------ util

# verbose print
def v_print(*args, **kwargs):
    if ARGS.v:
        print(*args, **kwargs)

# solution from
# https://stackoverflow.com/a/17317468/3213015
def open_file(filename):
    if sys.platform == "win32":
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])

# ------------ filepaths

PDF_FILE_PATHS = []

def fetch_pdfs():
    v_print(f'Fetching all PDFs from: {ARGS.dirpath}')
    for (dpath, _, fnames) in os.walk(ARGS.dirpath):
        for fname in fnames:
            fpath = os.path.join(dpath, fname)
            if mimetypes.guess_type(fpath)[0] == 'application/pdf':
                PDF_FILE_PATHS.append(fpath)
    v_print('Fetch done.', end='\n')

# ------------ GUI

class Result():
    def __init__(self, filePath, failed:bool=False, 
                 pageNumbers:list=[], surroundContext:list=[]):
        self.filePath = filePath
        self.pageNumbers = pageNumbers
        self.surroundContext = surroundContext
        self.failed = failed
    def __str__(self) -> str:
        totext  = f'File: {self.filePath}\n'
        totext += f'Search: {ARGS.string}\n'
        totext += '<><><><><><><><><><><><><>\n\n'
        for i, pn in enumerate(self.pageNumbers):
            totext += f'Page: {pn}\n'
            totext +=  '======================\n'
            for i, content in enumerate(self.surroundContext[i]):
                totext += f'  Context {i}:\n'
                totext +=  '--------------------\n'
                totext += f'{content}\n'
                totext +=  '--------------------\n'
            totext +='\n'
        return totext

class ResultDetailsDialog(tkinter.simpledialog.Dialog):
    def __init__(self, parent, resultObj:Result):
        self.resultObj = resultObj
        super().__init__(parent, 'PDF Result Details')
    def body(self, master):
        self.textWidget = tkinter.scrolledtext.ScrolledText(master)
        self.textWidget.insert(tkinter.INSERT, self.resultObj)
        self.textWidget.config(state=tkinter.DISABLED)
        self.textWidget.pack(fill='x')
        return self.textWidget
    def buttonbox(self):
        box = tkinter.Frame(self)
        self.okButton = tkinter.Button(box, text="OK", width=10, command=self.ok)
        self.okButton.pack()
        box.pack()

class ResultGUI(tkinter.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'{APPNAME} v{VER}')
        self.geometry(f'{WIN_W}x{WIN_H}')
        
        self.__results = []
        self.__insertResultLock = threading.Lock()
        self.__scannedFiles = 0

        self.progressf = tkinter.ttk.Frame(self)
        self.progressf.pack(fill='x')
        
        self.labelProgressStatus = tkinter.Label(self, text='Initializing...')
        self.labelFoundStatus = tkinter.Label(self, text='Found 0')
        self.progressb = tkinter.ttk.Progressbar(self.progressf, 
                                                 orient='horizontal')
        self.progressb.pack(padx=50, fill='x')
        self.labelProgressStatus.pack(fill='x', before=self.progressb)
        self.labelFoundStatus.pack(fill='x', after=self.progressb)
        self.progressb['maximum'] = 100
        self.progressb['value'] = 0
        
        self.listbox = tkinter.Listbox(self, width=100, height=100)
        self.listbox.pack(fill='both', padx=10, pady=10)
        self.listbox.bind('<Double-Button>', self.onDoubleClickItemFromList)
        self.listbox.bind('<Button-3>', self.onRightClickItemFromList)
    def onRightClickItemFromList(self, _):
        sel = self.listbox.curselection()
        if sel:
            result = self.__results[sel[0]]
            if not result.failed:
                ResultDetailsDialog(self, result)
    def onDoubleClickItemFromList(self, _):
        sel = self.listbox.curselection()
        if sel:
            result = self.__results[sel[0]]
            if not result.failed:
                open_file(result.filePath)
    def __incScannedFilesStatus(self):
        self.__scannedFiles += 1
        status = f'Reading PDF #{self.__scannedFiles} out of {len(PDF_FILE_PATHS)}.'
        v_print(status)
        self.labelProgressStatus.config(text=status)
        self.progressb['value'] = (self.__scannedFiles/len(PDF_FILE_PATHS))*100     
    def insertResult(self, result: Result):
        ''' Thread safe '''
        with self.__insertResultLock:
            self.__incScannedFilesStatus()
            if len(result.pageNumbers) > 0:
                v_print(result.filePath, result.pageNumbers)
                self.__results.append(result)
                self.labelFoundStatus.config(text=f'Found {len(self.__results)}')
                self.listbox.insert(tkinter.END, f'{result.filePath}\
                                    {" (Failed) " if result.failed else ""}')

RESULT_GUI = ResultGUI()

# ------------ search

def find_match(pattern, text, flags=0):
    matches = re.finditer(pattern, text, flags=flags)
    surtexts = []
    for match in matches:
        start = match.start()
        end = match.end()
        before_start = max(0, start - ARGS.surc)
        after_end = min(len(text), end + ARGS.surc)

        surrounding_text = text[before_start:end] + text[end:after_end]
        surtexts.append(surrounding_text)
    return surtexts

def pdf_search(fpath):
    flags = re.I if ARGS.ics else 0
    result = {
        'filePath': fpath,
        'failed': False,
        'pageNumbers': [],
        'surroundContext': []
    }
    try:
        reader = pypdf.PdfReader(fpath)
        for pn, page in enumerate(reader.pages):
            text = page.extract_text()
            contexts = find_match(ARGS.string, text, flags)
            if contexts:
                result['pageNumbers'].append(pn)
                result['surroundContext'].append(contexts)
    except pypdf.errors.PdfStreamError as e:
        result['failed'] = True
        print(f'> File error: skipping {fpath}')
    RESULT_GUI.insertResult(Result(**result))

def search_string():
    v_print('Dispatch search...')
    for fpath in PDF_FILE_PATHS:
        pdf_search(fpath)

# ------------ main

def main():
    fetch_pdfs()
    threading.Thread(target=search_string).start()
    print('lols')
    RESULT_GUI.mainloop()

if __name__ == '__main__':
    main()
