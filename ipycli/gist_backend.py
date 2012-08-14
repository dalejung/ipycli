import github
import os.path

def get_notebook_gists(u):
    nb_gists = []
    gists = u.get_gists()
    for gist in gists:
        desc = gist.description
        words = desc.split(" ")
        if "#notebook" in words:
            nb_gists.append(gist)

    return nb_gists

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
        return [os.path.join(self.path,nb) for nb in self.get_notebooks()]

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
