import os.path

import github
from IPython.nbformat import current
from .folder_backend import NBObject

def get_notebook_gists(u):
    nb_gists = []
    gists = u.get_gists()
    for gist in gists:
        desc = gist.description
        words = desc.split(" ")
        if "#notebook" in words:
            nb_gists.append(gist)

    return nb_gists

class GistObject(NBObject):
    def get_wd(self):
        """ Get Working Directory """
        return None

class GistProject(object):
    def __init__(self, gist, hub):
        words = [w for w in gist.description.split() if not w.startswith("#")]
        self.name = " ".join(words)
        self.hub = hub
        self.gist = gist
        self.id = gist.id
        self.path = gist.html_url

    def get_notebooks(self):
        files = self.gist.files
        notebooks = []
        for file in files:
            if file.endswith(".ipynb"):
                notebooks.append(file)

        return notebooks

    def get_notebook(self, filename):
        gist = self.hub.get_gist(self.gist.id)
        file = gist.files[filename]
        return file.content

    def notebooks(self):
        notebooks = [os.path.join(self.path,nb) for nb in self.get_notebooks()]
        notebooks = [GistObject(self, path) for path in notebooks]
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
        pass

    def new_notebook_object(self, path):
        pass

    def save_notebook_object(self, nb, path):
        pass


    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        """
            Makes backwards compatible to when ndir was just a string
        """
        if isinstance(other, basestring):
            return self.path == other
        if isinstance(other, GistHub):
            return self.path == self.path

class GistHub(object):
    def __init__(self, hub):
        self.hub = hub
        self.user = hub.get_user()

    def get_gist_projects(self):
        gists = get_notebook_gists(self.user)
        projects = [GistProject(gist, self.hub) for gist in gists]
        return projects


def gist_hub(user, password):
    g = github.Github(user, password)
    return GistHub(g)
