import os.path
import itertools
from StringIO import StringIO

import github
from IPython.nbformat import current
from ipycli.folder_backend import NBObject
from collections import OrderedDict

def get_notebook_project_gists(gists, show_all=False):
    """
        Get gists as project-dir
    """
    nb_gists = []
    for gist in gists:
        desc = gist.description
        tags = get_gist_tags(desc)
        if "#notebook-project" not in tags:
            continue
        active = "#inactive" not in tags
        if active or show_all:
            nb_gists.append(gist)

    return nb_gists

def get_notebook_single_gists(gists, show_all=False):
    """
        Get tagged gists
    """
    tagged = {}
    for gist in gists:
        desc = gist.description

        tags = get_gist_tags(desc)
        if "#notebook" not in tags:
            continue

        active = "#inactive" not in tags
        if not active and not show_all:
            continue

        for tag in tags:
            nb_list = tagged.setdefault(tag, [])
            nb_list.append(gist)

        # ignore system tag
        del tagged['#notebook']
    return tagged

def get_gist_tags(desc):
    tags = [tag for tag in desc.split(" ") if tag.startswith("#")]
    return tags

def get_gist_name(gist):
    words = [w for w in gist.description.split() if not w.startswith("#")]
    name = " ".join(words)
    return name

def change_gist_name(gist, name):
    desc = gist.description
    tags = [tag for tag in desc.split(" ") if tag.startswith("#")]
    new_name = name + " " + " ".join(tags)
    return new_name

def new_notebook_files(name='default.ipynb'):
    # make a new file  ugh    
    metadata = current.new_metadata(name=name)
    nb = current.new_notebook(metadata=metadata)
    content = current.writes(nb, format=u'json')
    file = github.InputFileContent(content)
    files = {name: file}
    return files

class GistObject(NBObject):
    def __init__(self, *args, **kwargs):
        tags = kwargs.pop('tags', [])
        super(GistObject, self).__init__(*args, **kwargs)
        self.tags = tags

    def get_wd(self):
        """ Get Working Directory """
        return None


class GistProject(object):

    filename_ext = '.ipynb'

    def __init__(self, gist, hub):
        words = [w for w in gist.description.split() if not w.startswith("#")]
        self._name = " ".join(words)
        self.hub = hub
        self.gists = {gist.id:gist}
        self.id = gist.id
        self.path = gist.html_url
        self.tags = get_gist_tags(gist.description)

    def __repr__(self):
        cn = self.__class__.__name__
        return "{0}: {1}".format(cn, self.name)

    @property
    def gist(self):
        return self.gists.values()[0]

    @property
    def name(self):
        return self._name + "        [{0}]".format(self.id)


    def refresh_gist(self, id=None):
        if id is None:
            id = self.gist.id

        try:
            gist = self.hub.get_gist(id)
        except:
            gist = None

        self.gists[id] = gist
        return gist

    def get_notebook(self, filename):
        gist = self.refresh_gist()
        file = gist.files[filename]
        return file.content

    def get_notebooks(self):
        files = self.gist.files
        notebooks = []
        for file in files:
            if file.endswith(".ipynb"):
                notebooks.append(file)

        return notebooks

    def notebooks(self):
        notebooks = [(os.path.join(self.path,nb), nb) for nb in self.get_notebooks()]
        notebooks = [GistObject(self, path, tags=self.tags) for path, name in notebooks]
        return notebooks

    def get_notebook_object(self, path):
        last_modified = self.gist.updated_at
        filename = os.path.basename(path)
        content = self.get_notebook(filename)
        try:
            # v1 and v2 and json in the .ipynb files.
            nb = current.reads(content, u'json')
        except:
            raise
        # Always use the filename as the notebook name.
        nb.metadata.name = filename
        return last_modified, nb

    def notebook_exists(self, path):
        """Does a notebook exist?"""
        filename = os.path.basename(path)
        return filename in self.gist.files

    def new_notebook_object(self, path):
        return GistObject(self, path)

    def increment_filename(self, basename):
        """
        Return a non-used filename of the form basename<int>.
        
        """
        i = 0
        while True:
            name = u'%s%i' % (basename,i)
            name = name + self.filename_ext
            path = os.path.join(self.path, name)
            if not self.notebook_exists(path):
                break
            else:
                i = i+1
        return path, name

    def save_notebook_object(self, nb, path):
        filename = os.path.basename(path)
        content = current.writes(nb, format=u'json')
        file = github.InputFileContent(content)
        files = {filename: file}
        self.edit_gist(self.gist, files=files)

    def autosave_notebook(self, nb, nbo, client_id):
        path = nbo.path
        self.save_notebook_object(nb, path=path)
        print 'autosave notebook {0}'.format(path)

    def delete_notebook(self, path):
        filename = os.path.basename(path)
        files = {filename: github.InputFileContent(None)}
        self.edit_gist(self.gist, files=files)

    def edit_gist(self, gist, desc=None, files=None):
        if desc is None:
            desc = gist.description
        gist.edit(desc, files)

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        """
            Makes backwards compatible to when ndir was just a string
        """
        if isinstance(other, basestring):
            return self.path == other
        if isinstance(other, GistProject):
            return self.path == other.path

    def __ne__(self, other):
        return not self.__eq__(other)

class TaggedGistProject(GistProject):
    def __init__(self, tag, gists, hub):
        self._name = tag
        self.hub = hub

        self.gists = {}
        for gist in gists:
            self.gists[gist.id] = gist

        self.path = "gisttag:/{0}".format(tag)
        # also match by gisttag:#tag/filename
        self.path_mapping = {}
        self.tag = tag


    @property
    def name(self):
        return self._name

    def _gist_name(self, gist):
        name =  get_gist_name(gist) 
        if gist.public and gist.id not in name.split():
            name = name + "   " + gist.id
        return name

    def get_notebooks(self):
        gists = sorted(self.gists.values(), key=lambda x: x.updated_at)
        return [(gist.html_url, self._gist_name(gist), gist) for gist in gists]

    def notebooks(self):
        notebooks = self.get_notebooks()
        notebooks = [GistObject(self, path, name, tags=get_gist_tags(gist.description)) for path, name, gist 
                     in notebooks]
        return notebooks

    def _get_gist_by_path(self, path):
        for gist in self.gists.values():
            if gist.html_url == path:
                return gist
        # this only exists on first creation. Afterwards path normalizes
        # to the gist html_url
        gist = self.path_mapping.setdefault(path, None)
        return gist

    def get_notebook_object(self, path):
        gist = self._get_gist_by_path(path)
        last_modified = gist.updated_at
        content = self.get_notebook(gist)
        try:
            # v1 and v2 and json in the .ipynb files.
            nb = current.reads(content, u'json')
        except:
            raise
        # Always use the filename as the notebook name.
        name = self._gist_name(gist)
        nb.metadata.name = name
        return last_modified, nb

    def get_notebook(self, gist):
        gist = self.refresh_gist(gist.id)
        file = self.get_gist_file(gist)
        if file:
            return file.content
        
        # make a new file  ugh    
        files = new_notebook_files()
        self.edit_gist(gist, files=files)
        # hold to your butts, recursion!
        return self.get_notebook(gist)

    def get_gist_file(self, gist):
        """
            Will return the first notebook in a gist
        """
        for file in gist.files.values():
            if file.filename.endswith(".ipynb"):
                return file

    def autosave_notebook(self, nb, nbo, client_id):
        path = nbo.path
        self.save_notebook_object(nb, path=path)
        print 'autosave notebook {0}'.format(path)

    def new_notebook_object(self, path):
        # we create gist here because we are using gist.html_url as path
        # this creates a redundancy with save_notebook_object
        _, tag, filename = path.split('/')
        files = new_notebook_files(filename)
        desc = "IPython Notebook #notebook {0}".format(tag)
        gist = self.hub.get_user().create_gist(False, files, desc)
        self.gists[gist.id] = gist
        self.path_mapping[path] = gist

        return GistObject(self, gist.html_url, filename)

    def save_notebook_object(self, nb, path):
        gist = self._get_gist_by_path(path)
        gfile = self.get_gist_file(gist)
        content = current.writes(nb, format=u'json')
        file = github.InputFileContent(content)
        files = {gfile.filename: file}
        # name and desc are synched for gist-notebooks
        desc = change_gist_name(gist, nb.metadata.name)
        self.edit_gist(gist, files=files, desc=desc)

    def rename_notebook(self, nb, old_path):
        # no need to delete, just change desc
        self.save_notebook_object(nb, old_path)

    def delete_notebook(self, path):
        gist = self._get_gist_by_path(path)
        desc = gist.description + " #inactive"
        self.edit_gist(gist, desc=desc, files={})

class GistHub(object):
    def __init__(self, hub):
        self.hub = hub
        self.user = hub.get_user()

    def get_gist_projects(self, show_all=True):
        gists = self.user.get_gists()

        project_gists = get_notebook_project_gists(gists, show_all=show_all)
        projects = [GistProject(gist, self.hub) for gist in project_gists]

        single_gists = get_notebook_single_gists(gists, show_all=show_all)
        singles = [TaggedGistProject(tag, tgists, self.hub) for tag, tgists 
                   in single_gists.items()]

        gprojects = list(itertools.chain(projects, singles))
        return gprojects

def gist_hub(user, password):
    g = github.Github(user, password)
    return GistHub(g)
