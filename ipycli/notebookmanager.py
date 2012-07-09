"""A notebook manager that uses the local file system for storage.

Authors:

* Brian Granger
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2008-2011  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import datetime
import io
import os
import uuid
import glob
import itertools
import os.path

from tornado import web

from IPython.config.configurable import LoggingConfigurable
from IPython.nbformat import current
from IPython.utils.traitlets import Unicode, List, Dict, Bool, TraitError

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------

class NotebookManager(LoggingConfigurable):

    notebook_dir = Unicode(os.getcwdu(), config=True, help="""
        The directory to use for notebooks.
    """)
    def _notebook_dir_changed(self, name, old, new):
        """do a bit of validation of the notebook dir"""
        if os.path.exists(new) and not os.path.isdir(new):
            raise TraitError("notebook dir %r is not a directory" % new)
        if not os.path.exists(new):
            self.log.info("Creating notebook dir %s", new)
            try:
                os.mkdir(new)
            except:
                raise TraitError("Couldn't create notebook dir %r" % new)
    
    save_script = Bool(False, config=True,
        help="""Automatically create a Python script when saving the notebook.
        
        For easier use of import, %run and %load across notebooks, a
        <notebook-name>.py script will be created next to any
        <notebook-name>.ipynb on each save.  This can also be set with the
        short `--script` flag.
        """
    )
    
    filename_ext = Unicode(u'.ipynb')
    allowed_formats = List([u'json',u'py'])

    # Map notebook_ids to notebook names
    mapping = Dict()
    # Map notebook names to notebook_ids
    rev_mapping = Dict()
    # path mapping
    path_mapping = Dict()

    # all_mapping is a dict of lists. key being the dir
    all_mapping = Dict()
    # pathed notebooks
    pathed_notebooks = Dict()

    def __init__(self, *args, **kwargs):
        # Default to the normal notebook_dir
        super(NotebookManager, self).__init__(*args, **kwargs)

        self.notebook_dirs = [self.notebook_dir]

    def add_notebook_dir(self, dir):
        self.notebook_dirs.append(dir)

    def ndir_notebooks(self, ndir):
        """List all notebooks in the notebook dir.

        This returns a list of dicts of the form::

            dict(notebook_id=notebook,name=name)
        """
        names = glob.glob(os.path.join(ndir,
                                       '*' + self.filename_ext))
        return names

    def list_notebooks(self):
        """
            List all notebooks in a dict
        """
        for ndir in self.notebook_dirs:
            names = self.ndir_notebooks(ndir)
            self.all_mapping[ndir] = names

        names = itertools.chain(*self.all_mapping.values())
        pathed_notebooks = self.pathed_notebook_list()
        names = itertools.chain(names, pathed_notebooks)
        data = []
        for name in names:
            path = name
            if name not in self.rev_mapping:
                notebook_id = self.new_notebook_id(name, path=path)
            else:
                notebook_id = self.rev_mapping[name]
            data.append(dict(notebook_id=notebook_id,name=name))

        data = sorted(data, key=lambda item: item['name'])
        return data

    def pathed_notebook_list(self):
        self.verify_pathed_files()
        paths = self.pathed_notebooks.values()
        return paths


    def verify_pathed_files(self):
        """
            Verify files exist and remove missing files
        """
        for id,path in self.pathed_notebooks.items():
            if not os.path.isfile(path):
                print 'remove', path
                del self.pathed_notebooks[id]

    def file_exists(self, path):
        try:
            with open(path) as f: pass
            return True
        except:
            return False

    def get_pathed_notebook(self, path):
        file_exists = self.file_exists(path)
        if not file_exists:
            return False

        notebook_id = self.new_notebook_id(path, path=path)
        self.pathed_notebooks[notebook_id] = path
        return notebook_id


    def new_notebook_id(self, name, ndir=None, path=None):
        """Generate a new notebook_id for a name and store its mappings."""
        # TODO: the following will give stable urls for notebooks, but unless
        # the notebooks are immediately redirected to their new urls when their
        # filemname changes, nasty inconsistencies result.  So for now it's
        # disabled and instead we use a random uuid4() call.  But we leave the
        # logic here so that we can later reactivate it, whhen the necessary
        # url redirection code is written.
        #notebook_id = unicode(uuid.uuid5(uuid.NAMESPACE_URL,
        #                 'file://'+self.get_path_by_name(name).encode('utf-8')))
        
        notebook_id = unicode(uuid.uuid4())
        if ndir is None and path is None:
            raise Exception("ndir or path must be passed in")

        if path:
            ndir, name = os.path.split(path)

        self.set_notebook_path(notebook_id, ndir, name)
        
        return notebook_id

    def set_notebook_path(self, notebook_id, ndir, name):
        filepath= os.path.join(ndir, name)
        self.path_mapping[notebook_id] = filepath
        self.mapping[notebook_id] = name
        self.rev_mapping[filepath] = notebook_id

    def delete_notebook_id(self, notebook_id):
        """Delete a notebook's id only. This doesn't delete the actual notebook."""
        name = self.path_mapping[notebook_id]
        del self.mapping[notebook_id]
        del self.path_mapping[notebook_id]
        del self.rev_mapping[name]

    def notebook_exists(self, notebook_id):
        """Does a notebook exist?"""
        if notebook_id not in self.mapping:
            return False
        path = self.find_path(notebook_id)
        return os.path.isfile(path)

    def find_path(self, notebook_id):
        """Return a full path to a notebook given its notebook_id."""
        # first try path mapping
        try:
            path = self.path_mapping[notebook_id]
            return path
        except:
            pass

        try:
            name = self.mapping[notebook_id]
        except KeyError:
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)
        return self.get_path_by_name(name)

    def get_path_by_name(self, name):
        """Return a full path to a notebook given its name."""
        # check if we are already a full path
        if name in self.path_mapping.values():
            return name
        filename = name + self.filename_ext
        path = os.path.join(self.notebook_dir, filename)
        return path       

    def get_notebook(self, notebook_id, format=u'json'):
        """Get the representation of a notebook in format by notebook_id."""
        format = unicode(format)
        if format not in self.allowed_formats:
            raise web.HTTPError(415, u'Invalid notebook format: %s' % format)
        last_modified, nb = self.get_notebook_object(notebook_id)
        kwargs = {}
        if format == 'json':
            # don't split lines for sending over the wire, because it
            # should match the Python in-memory format.
            kwargs['split_lines'] = False
        data = current.writes(nb, format, **kwargs)
        name = nb.get('name','notebook')
        return last_modified, name, data

    def get_notebook_object(self, notebook_id):
        """Get the NotebookNode representation of a notebook by notebook_id."""
        path = self.find_path(notebook_id)
        if not os.path.isfile(path):
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)
        info = os.stat(path)
        last_modified = datetime.datetime.utcfromtimestamp(info.st_mtime)
        with open(path,'r') as f:
            s = f.read()
            try:
                # v1 and v2 and json in the .ipynb files.
                nb = current.reads(s, u'json')
            except:
                raise web.HTTPError(500, u'Unreadable JSON notebook.')
        # Always use the filename as the notebook name.
        nb.metadata.name = os.path.splitext(os.path.basename(path))[0]
        return last_modified, nb

    def save_new_notebook(self, data, name=None, format=u'json'):
        """Save a new notebook and return its notebook_id.

        If a name is passed in, it overrides any values in the notebook data
        and the value in the data is updated to use that value.
        """
        if format not in self.allowed_formats:
            raise web.HTTPError(415, u'Invalid notebook format: %s' % format)

        try:
            nb = current.reads(data.decode('utf-8'), format)
        except:
            raise web.HTTPError(400, u'Invalid JSON data')

        if name is None:
            try:
                name = nb.metadata.name
            except AttributeError:
                raise web.HTTPError(400, u'Missing notebook name')
        nb.metadata.name = name

        path = os.path.join(self.notebook_dir, name+self.filename_ext)
        notebook_id = self.new_notebook_id(name, path=path)
        self.save_notebook_object(notebook_id, nb)
        return notebook_id

    def save_notebook(self, notebook_id, data, name=None, format=u'json'):
        """Save an existing notebook by notebook_id."""
        if format not in self.allowed_formats:
            raise web.HTTPError(415, u'Invalid notebook format: %s' % format)

        try:
            nb = current.reads(data.decode('utf-8'), format)
        except:
            raise web.HTTPError(400, u'Invalid JSON data')

        if name is not None:
            nb.metadata.name = name
        self.save_notebook_object(notebook_id, nb)

    def rename_notebook(self, notebook_id, data, name=None, format=u'json'):
        """ Separate out rename """
        if format not in self.allowed_formats:
            raise web.HTTPError(415, u'Invalid notebook format: %s' % format)

        try:
            nb = current.reads(data.decode('utf-8'), format)
        except:
            raise web.HTTPError(400, u'Invalid JSON data')

        if name is not None:
            nb.metadata.name = name

        old_path = self.find_path(notebook_id)
        ndir, _ = os.path.split(old_path)
        name = nb.metadata.name + self.filename_ext
        self.set_notebook_path(notebook_id, ndir, name)

        # save new file
        self.save_notebook_object(notebook_id, nb)

        # Delete old file 
        if os.path.isfile(old_path):
            os.unlink(old_path)
        if self.save_script:
            old_pypath = os.path.splitext(old_path)[0] + '.py'
            if os.path.isfile(old_pypath):
                os.unlink(old_pypath)


    def save_notebook_object(self, notebook_id, nb):
        """Save an existing notebook object by notebook_id."""
        if notebook_id not in self.mapping:
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)

        # bah
        path = self.find_path(notebook_id)

        try:
            with open(path,'w') as f:
                current.write(nb, f, u'json')
        except Exception as e:
            raise web.HTTPError(400, u'Unexpected error while saving notebook: %s' % e)
        # save .py script as well
        if self.save_script:
            pypath = os.path.splitext(path)[0] + '.py'
            try:
                with io.open(pypath,'w', encoding='utf-8') as f:
                    current.write(nb, f, u'py')
            except Exception as e:
                raise web.HTTPError(400, u'Unexpected error while saving notebook as script: %s' % e)

    def delete_notebook(self, notebook_id):
        """Delete notebook by notebook_id."""
        path = self.find_path(notebook_id)
        if not os.path.isfile(path):
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)
        os.unlink(path)
        self.delete_notebook_id(notebook_id)

    def increment_filename(self, basename, ndir=None):
        """Return a non-used filename of the form basename<int>.
        
        This searches through the filenames (basename0, basename1, ...)
        until is find one that is not already being used. It is used to
        create Untitled and Copy names that are unique.
        """
        i = 0
        while True:
            name = u'%s%i' % (basename,i)
            name = name + self.filename_ext
            path = os.path.join(ndir, name)
            if not os.path.isfile(path):
                break
            else:
                i = i+1
        return path, name

    def new_notebook_object(self, name):
        """
        """
        metadata = current.new_metadata(name=name)
        nb = current.new_notebook(metadata=metadata)
        return nb 

    def new_notebook(self, ndir, name=None):
        """Create a new notebook and return its notebook_id."""
        if name is None:
            # create new file with default naming
            path, name = self.increment_filename('Untitled', ndir=ndir)
            notebook_id = self.new_notebook_id(name, ndir=ndir)
        else:
            # technically this is a pathed notebook
            # I actually don't like this
            notebook_id = self.new_notebook_id(name, ndir=ndir)
            path = os.path.join(ndir, name)
            self.pathed_notebooks[notebook_id] = path

        nb = self.new_notebook_object(name)

        with open(path,'w') as f:
            current.write(nb, f, u'json')
        return notebook_id

    def copy_notebook(self, notebook_id):
        """Copy an existing notebook and return its notebook_id."""
        last_mod, nb = self.get_notebook_object(notebook_id)
        ndir, _ = os.path.split(self.find_path(notebook_id))
        name = nb.metadata.name + '-Copy'
        path, name = self.increment_filename(name, ndir=ndir)
        nb.metadata.name = name
        notebook_id = self.new_notebook_id(name, path=path)
        self.save_notebook_object(notebook_id, nb)
        return notebook_id
