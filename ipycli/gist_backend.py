import os.path
import itertools
from StringIO import StringIO

import github
from IPython.nbformat import current
from ipycli.folder_backend import NBObject

def get_notebook_project_gists(gists):
    nb_gists = []
    for gist in gists:
        desc = gist.description
        words = desc.split(" ")
        if "#notebook-project" in words and "#inactive" not in words:
            nb_gists.append(gist)

    return nb_gists

def get_notebook_single_gists(gists):
    tagged = {}
    for gist in gists:
        desc = gist.description

        tags = get_gist_tags(desc)
        if "#notebook" not in tags or "#inactive" in tags:
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

class GistObject(NBObject):
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

    @property
    def gist(self):
        return self.gists.values()[0]

    @property
    def name(self):
        return self._name + "        [{0}]".format(self.id)

    def get_notebooks(self):
        self.refresh_gist()
        files = self.gist.files
        notebooks = []
        for file in files:
            if file.endswith(".ipynb"):
                notebooks.append(file)

        return notebooks

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

    def notebooks(self):
        notebooks = [(os.path.join(self.path,nb), nb) for nb in self.get_notebooks()]
        notebooks = [GistObject(self, path) for path, name in notebooks]
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
        path = self.path
        i = 0
        while True:
            name = u'%s%i' % (basename,i)
            name = name + self.filename_ext
            path = os.path.join(path, name)
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

        self.path = "gisttag:{0}/{1}".format(tag, tag)

    @property
    def name(self):
        return self._name

    def get_notebooks(self):
        return [(gist.html_url, get_gist_name(gist) + "   " + gist.id) for gist in self.gists.values()]

    def notebooks(self):
        notebooks = self.get_notebooks()
        notebooks = [GistObject(self, path, name) for path, name in notebooks]
        return notebooks

    def _get_gist_by_path(self, path):
        for gist in self.gists.values():
            if gist.html_url == path:
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
        nb.metadata.name = path
        return last_modified, nb

    def get_notebook(self, gist):
        gist = self.refresh_gist(gist.id)
        file = self.get_gist_file(gist)
        if file:
            return file.content
        
        # make a new file  ugh    
        metadata = current.new_metadata(name="default.ipynb")
        nb = current.new_notebook(metadata=metadata)
        content = current.writes(nb, format=u'json')
        file = github.InputFileContent(content)
        files = {'default.ipynb': file}
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

    def save_notebook_object(self, nb, path):
        gist = self._get_gist_by_path(path)
        gfile = self.get_gist_file(gist)
        content = current.writes(nb, format=u'json')
        file = github.InputFileContent(content)
        files = {gfile.filename: file}
        self.edit_gist(gist, files=files)

    def delete_notebook(self, path):
        gist = self._get_gist_by_path(path)
        desc = gist.description + " #inactive"
        self.edit_gist(gist, desc=desc, files={})

class GistHub(object):
    def __init__(self, hub):
        self.hub = hub
        self.user = hub.get_user()

    def get_gist_projects(self):
        gists = self.user.get_gists()

        project_gists = get_notebook_project_gists(gists)
        projects = [GistProject(gist, self.hub) for gist in project_gists]

        single_gists = get_notebook_single_gists(gists)
        singles = [TaggedGistProject(tag, tgists, self.hub) for tag, tgists 
                   in single_gists.items()]

        gprojects = list(itertools.chain(projects, singles))
        return gprojects

def gist_hub(user, password):
    g = github.Github(user, password)
    return GistHub(g)
