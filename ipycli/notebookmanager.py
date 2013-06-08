"""A notebook manager that uses the local file system for storage.

Authors:

* Brian Granger
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
import cPickle as pickle

from tornado import web

from IPython.config.configurable import LoggingConfigurable
from IPython.nbformat import current
from IPython.utils.traitlets import Unicode, List, Dict, Bool, TraitError

from .folder_backend import *

def unique_everseen(iterable, key=None):
    from itertools import ifilterfalse
    "List unique elements, preserving order. Remember all elements ever seen."
    # unique_everseen('AAAABBBCCDAABBB') --> A B C D
    # unique_everseen('ABBCcAD', str.lower) --> A B C D
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in ifilterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element


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

        self.ghub = None
        self.notebook_dirs = {}
        self.gist_projects = []
        self.add_notebook_dir(self.notebook_dir)

    def add_notebook_dir(self, dir):
        dir = os.path.abspath(dir)
        project = self.notebook_dirs.get(dir, None)
        if project is None:
            project = DirectoryProject(dir, self.filename_ext)
            self.notebook_dirs[dir] = project
        return project

    @property
    def notebook_projects(self):
        return itertools.chain(self.notebook_dirs.values(), self.gist_projects)

    def tagged_notebooks(self, tag):
        """
            List all notebooks in a dict
        """
        self.refresh_notebooks()

        notebooks = []
        tag = '#' + tag
        for backend in self.gist_projects:
            if not hasattr(backend, 'tag'):
                continue
            if backend.tag == tag:
                notebooks = backend.notebooks()

        return self.output_notebooks(notebooks, sort=False)

    def dir_notebooks(self, dir):
        """
            List all notebooks in a dict
        """
        self.refresh_notebooks(skip_github=True)

        backend_matches = []
        for backend in self.notebook_dirs.values():
            # add all subdirs as well
            if backend.path.startswith(dir):
                backend_matches.append(backend)

        notebooks = itertools.chain(*[backend.notebooks() for backend in backend_matches])
        return self.output_notebooks(notebooks, sort=False)

    def list_notebooks(self):
        """
            List both inactive and active notebooks
        """
        self.refresh_notebooks()
        # regular listing doesn't show transients
        notebooks = []
        transients = []

        for backend, nbs in self.all_mapping.items():
            if hasattr(backend, 'tag') and backend.tag == '#transient':
                transients = nbs
            else:
                notebooks.append(nbs)

        notebooks = itertools.chain(*notebooks)
        notebooks = list(notebooks)

        pathed_notebooks = self.pathed_notebook_list()


        all_notebooks = itertools.chain(notebooks, pathed_notebooks)
        all_notebooks = sorted(all_notebooks, key=lambda nb: nb.name)

        all_notebooks = [notebook for notebook in all_notebooks if '#inactive' not in notebook.tags]
        transients = [notebook for notebook in transients if '#inactive' not in notebook.tags]

        # show the last 5 transients. Most recent on top
        all_notebooks = list(reversed(transients[-5:])) + all_notebooks

        return self.output_notebooks(all_notebooks)

    def all_notebooks(self):
        """
            List all notebooks in a dict
        """
        self.refresh_notebooks()
        # regular listing doesn't show transients
        notebooks = []

        for backend, nbs in self.all_mapping.items():
            notebooks.append(nbs)

        notebooks = itertools.chain(*notebooks)

        pathed_notebooks = self.pathed_notebook_list()

        all_notebooks = itertools.chain(notebooks, pathed_notebooks)
        all_notebooks = sorted(all_notebooks, key=lambda nb: nb.name)

        return self.output_notebooks(all_notebooks)

    def output_notebooks(self, notebooks, sort=True):
        data = []
        for nb in notebooks:
            if nb not in self.rev_mapping:
                notebook_id = self.new_notebook_id(nb)
            else:
                notebook_id = self.rev_mapping[nb]
            data.append(dict(notebook_id=notebook_id,path=nb.path, name=nb.name))

        return data

    def refresh_notebooks(self, skip_github=False):
        # HACK
        if self.ghub and not skip_github:
            projects = self.ghub.get_gist_projects()
            self.gist_projects = projects
        # ENDHACK

        for backend in self.notebook_projects:
            nbs = backend.notebooks()
            self.all_mapping[backend] = nbs

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


    def new_notebook_id(self, nb, backend=None, path=None):
        """Generate a new notebook_id for a name and store its mappings."""
        # TODO: the following will give stable urls for notebooks, but unless
        # the notebooks are immediately redirected to their new urls when their
        # filemname changes, nasty inconsistencies result.  So for now it's
        # disabled and instead we use a random uuid4() call.  But we leave the
        # logic here so that we can later reactivate it, whhen the necessary
        # url redirection code is written.
        
        name = str(nb)
        notebook_id = unicode(uuid.uuid5(uuid.NAMESPACE_URL,
                         'file://'+self.get_path_by_name(name).encode('utf-8')))

        if path:
            raise Exception("Need to support a pathed backend")
            ndir, name = os.path.split(path)

        try:
            path = nb.path
        except:
            pass

        if backend is None and path is None:
            raise Exception("ndir or path must be passed in")


        self.set_notebook_path(notebook_id, nb)
        
        return notebook_id

    def set_notebook_path(self, notebook_id, nb):
        filepath = nb.path
        self.path_mapping[notebook_id] = filepath
        self.mapping[notebook_id] = nb
        self.rev_mapping[filepath] = notebook_id

    def delete_notebook_id(self, notebook_id):
        """Delete a notebook's id only. This doesn't delete the actual notebook."""
        path = self.path_mapping[notebook_id]
        del self.mapping[notebook_id]
        del self.path_mapping[notebook_id]
        del self.rev_mapping[path]

    def notebook_exists(self, notebook_id):
        """Does a notebook exist?"""
        if notebook_id not in self.mapping:
            return False
        nb = self.mapping[notebook_id]
        return nb.backend.exists(notebook_id)

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
        nb = self.mapping[notebook_id]
        backend = nb.backend
        try:
            return backend.get_notebook_object(nb.path)
        except Exception as e:
            raise web.HTTPError(404, u'Notebook does not exist: %s, Err:%s' % (notebook_id, str(e)))

    def backend_by_path(self, path):
        """
            path is project path which is unique to each project
        """
        for p in self.notebook_projects:
            if p == path:
                return p

    def backend_by_notebook_id(self, notebook_id):
        nbo = self.mapping[notebook_id]
        backend = nbo.backend
        return backend

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
        backend = None
        print 'save_new_notebook'
        nbo = backend.new_notebook_object(path)
        notebook_id = self.new_notebook_id(nbo)
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

    def restore_notebook(self, notebook_id):
        pass

    def autosave_notebook(self, notebook_id, data, client_id, name=None, format=u'json'):
        """Save an existing notebook by notebook_id."""
        if format not in self.allowed_formats:
            raise web.HTTPError(415, u'Invalid notebook format: %s' % format)

        try:
            nb = current.reads(data.decode('utf-8'), format)
        except:
            raise web.HTTPError(400, u'Invalid JSON data')

        nbo = self.mapping[notebook_id]
        backend = nbo.backend
        backend.autosave_notebook(nb, nbo, client_id)

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
        nbo = self.mapping[notebook_id]
        backend = nbo.backend

        # shortcircuit
        if hasattr(backend, 'rename_notebook'):
            return backend.rename_notebook(nb, old_path)

        # This is where the folder stuff lives
        # it's not under Folder.rename_notebook because
        # it interacts so much with NB Manager
        # Gist on other hand has a stable ID and not a path that 
        # can change
        name = nb.metadata.name + self.filename_ext
        new_path = os.path.join(backend.dir, name)

        nbo.path = new_path

        self.set_notebook_path(notebook_id, nbo)

        # save new file
        self.save_notebook_object(notebook_id, nb)

        backend.delete_notebook(old_path)

    def save_notebook_object(self, notebook_id, nb, path=None):
        """Save an existing notebook object by notebook_id."""
        if notebook_id not in self.mapping:
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)

        # bah
        nbo = self.mapping[notebook_id]
        if path is None:
            path = self.find_path(notebook_id)

        backend = nbo.backend
        backend.save_notebook_object(nb, path)

    def delete_notebook(self, notebook_id):
        """Delete notebook by notebook_id."""
        try:
            nbo = self.mapping[notebook_id]
            nbo.backend.delete_notebook(nbo.path)
        except:
            raise web.HTTPError(404, u'Notebook does not exist: ')
        self.delete_notebook_id(notebook_id)

    def new_notebook_object(self, name):
        """
        """
        metadata = current.new_metadata(name=name)
        nb = current.new_notebook(metadata=metadata)
        return nb 

    def new_notebook(self, backend, name=None, public=False):
        """Create a new notebook and return its notebook_id."""
        if name is None:
            # create new file with default naming
            path, name = backend.increment_filename('Untitled')
        else:
            path, name = backend.increment_filename(name)

        nb = self.new_notebook_object(name)
        nbo = backend.new_notebook_object(path, public=public)
        backend.save_notebook_object(nb, path=path)
        notebook_id = self.new_notebook_id(nbo, backend=backend)

        return notebook_id

    def copy_notebook(self, notebook_id):
        """Copy an existing notebook and return its notebook_id."""
        last_mod, nb = self.get_notebook_object(notebook_id)
        nbo = self.mapping[notebook_id]
        backend = nbo.backend
        name = nb.metadata.name + '-Copy'
        path, name = backend.increment_filename(name)
        nb.metadata.name = name
        copy_nbo = backend.new_notebook_object(path)
        notebook_id = self.new_notebook_id(copy_nbo)
        self.save_notebook_object(notebook_id, nb)
        return notebook_id
