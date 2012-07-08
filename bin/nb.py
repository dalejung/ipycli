#!/usr/bin/env python

import urllib2
import urllib

PORT = 8888

def open_url(nbpath, port=PORT):
    nbpath = urllib.quote_plus(nbpath)
    url = "http://127.0.0.1:%d/n/%s" % (port, nbpath)
    urllib2.urlopen(url)

def new_url(nbpath, port=PORT):
    nbpath = urllib.quote_plus(nbpath)
    url = "http://127.0.0.1:%d/new/%s" % (port, nbpath)
    urllib2.urlopen(url)

def open_notebook(fullpath):
    if os.path.isfile(fullpath):
        print 'found file'
        open_url(fullpath)
        return

    path, file = os.path.split(fullpath)
    if not file.endswith('ipynb'):
        file = file + '.ipynb'

    print 'opening new notebook'
    fullpath = os.path.join(path, file)
    new_url(fullpath)

if __name__ == '__main__':
    import argparse
    import os
    parser = argparse.ArgumentParser(description="Start a notebook");

    parser.add_argument('filepath', action="store")

    args = parser.parse_args()

    filepath = args.filepath
    cwd = os.getcwd()

    fullpath = os.path.join(cwd, filepath)
    open_notebook(fullpath)