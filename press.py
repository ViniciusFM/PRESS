import argparse
import mimetypes
import os
import pypdf
import json
import re

# ------------ consts

APPNAME = 'PRESS'
VER     = '0.1'

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
    parser.add_argument('-v', action='store_true',
                        help='''Verbose. This option shows the page numbers 
                                that contains the search string.''')
    parser.add_argument('dirpath',
                        help='''Define a path to the directory where the PDF
                                 files are.''',
                        type=dirpath)
    parser.add_argument('string',
                        help='''A string regex for the search''',
                        type=str)
    return parser.parse_args()

ARGS = build_args()

# ------------ filepaths

PDF_FILE_PATHS = []

def fetch_pdfs():
    for (dpath, _, fnames) in os.walk(ARGS.dirpath):
        for fname in fnames:
            fpath = os.path.join(dpath, fname)
            if mimetypes.guess_type(fpath)[0] == 'application/pdf':
                PDF_FILE_PATHS.append(fpath)

# ------------ search
SEARCH_RESULTS = []

def pdf_search(fpath):
    flags = re.I if ARGS.ics else 0
    result = {
        'file': fpath,
        'page_numbers': []
    }
    try:
        reader = pypdf.PdfReader(fpath)
        for pn, page in enumerate(reader.pages):
            text = page.extract_text()
            match = re.search(ARGS.string, text, flags)
            if match:
                result['page_numbers'].append(pn+1)
    except pypdf.errors.PdfStreamError as e:
        print(f'> File error: skipping {fpath}')
    return result

def search_string():
    global SEARCH_RESULTS
    for fpath in PDF_FILE_PATHS:
        SEARCH_RESULTS.append(pdf_search(fpath))

def print_results():
    for r in SEARCH_RESULTS:
        if r['page_numbers']:
            print(f'File: {r['file']}')
            if ARGS.v:
                print('\tPages:')
                lc = 0
                print('\t- ', end='')
                for i in r['page_numbers']:
                    if lc < 15:
                        print(f'{i} ', end='')
                    else:
                        print('\n\t- ', end='')
                        lc = 0
                    lc += 1
                print('')

# ------------ main

def main():
    fetch_pdfs()
    search_string()
    print_results()

if __name__ == '__main__':
    main()
