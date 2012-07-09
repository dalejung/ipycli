import os.path
from unittest import TestCase

import numpy as np
import pandas as pd

from ipycli.notebookmanager import NotebookManager
from IPython.utils.tempdir import TemporaryDirectory

class TestCLI(TestCase):

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)

    def runTest(self):
        pass

    def setUp(self):
        pass

    def test_new_notebook(self):
        with TemporaryDirectory() as td:
            km = NotebookManager(notebook_dir=td)
            filename = 'Untitled0.ipynb'
            filepath = os.path.join(td, filename)
            notebook_id = km.new_notebook(ndir=td)
            assert os.path.isfile(filepath)

            # Now make sure path mapping works
            assert km.path_mapping[notebook_id] == filepath
            assert km.find_path(notebook_id) == filepath

    def test_new_notebook_name(self):
        with TemporaryDirectory() as td:
            km = NotebookManager(notebook_dir=td)
            filename = 'new_test.ipynb'
            filepath = os.path.join(td, filename)
            notebook_id = km.new_notebook(ndir=td, name=filename)
            assert os.path.isfile(filepath)

            # Now make sure path mapping works
            assert km.path_mapping[notebook_id] == filepath
            assert km.find_path(notebook_id) == filepath
            assert filepath in km.pathed_notebooks.values()

    def test_notebook_list(self):
        with TemporaryDirectory() as td:
            km = NotebookManager(notebook_dir=td)
            filename = 'new_test.ipynb'
            filepath = os.path.join(td, filename)
            notebook_id = km.new_notebook(ndir=td, name=filename)
            n = {'name':filepath, 'notebook_id':notebook_id}

            correct = []
            correct.append(n)

            nlist = km.list_notebooks()
            assert nlist[0]['name'] == correct[0]['name']
            assert nlist[0]['notebook_id'] == correct[0]['notebook_id']

    def test_delete_notebook(self):
        with TemporaryDirectory() as td:
            km = NotebookManager(notebook_dir=td)
            filename = 'new_test.ipynb'
            filepath = os.path.join(td, filename)
            notebook_id = km.new_notebook(ndir=td, name=filename)
            assert os.path.isfile(filepath)

            # Now make sure path mapping works
            assert km.path_mapping[notebook_id] == filepath
            assert km.find_path(notebook_id) == filepath

            assert notebook_id in km.mapping
            assert notebook_id in km.path_mapping
            assert notebook_id in km.rev_mapping.values()
            km.delete_notebook(notebook_id)
            assert notebook_id not in km.mapping
            assert notebook_id not in km.path_mapping
            assert notebook_id not in km.rev_mapping.values()
            assert not os.path.isfile(filepath)

    def test_existing_notebook(self):
        # Create a dir with notebooks
        td = TemporaryDirectory()
        ndir = td.__enter__()
        km = NotebookManager(notebook_dir=ndir)
        filename = 'new_test.ipynb'
        filepath = os.path.join(ndir, filename)
        notebook_id = km.new_notebook(ndir=ndir, name=filename)


        td2 = TemporaryDirectory()
        ndir2 = td2.__enter__()
        nbm = NotebookManager(notebook_dir=ndir2)

        assert nbm.notebook_dir != km.notebook_dir
        assert filepath not in nbm.path_mapping.values()
        assert filepath not in nbm.pathed_notebooks.values()
        nbm.get_pathed_notebook(filepath)
        assert nbm.path_mapping.values()[0] == filepath
        assert filepath in nbm.pathed_notebooks.values()

if __name__ == '__main__':                                                                                          
    import nose                                                                      
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                  exit=False)   
