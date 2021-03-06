import glob
import io
import os.path
import datetime

from tornado import web

from IPython.nbformat import current

def getmtime(file):
    timestamp = os.path.getmtime(file)
    return datetime.datetime.fromtimestamp(timestamp)

class DirectoryProject(object):
    def __init__(self, dir, filename_ext):
        self.dir = dir
        self.filename_ext = filename_ext
        self.save_script = False

    @property  
    def path(self):
        return self.dir

    @property  
    def name(self):
        return self.dir


    def notebooks(self):
        names = glob.glob(os.path.join(self.dir,
                                       '*' + self.filename_ext))
        files = [(name, getmtime(name)) for name in names]
        nbs = [NBObject(backend=self, path=name, mtime=date) for name, date in files]
        sorted_nbs = sorted(nbs, key=lambda x: x.mtime, reverse=True)
        return sorted_nbs

    def __hash__(self):
        return hash(self.dir)

    def __eq__(self, other):
        """
            Makes backwards compatible to when ndir was just a string
        """
        if isinstance(other, basestring):
            return self.dir == other
        if isinstance(other, DirectoryProject):
            return self.dir == self.dir

    def __repr__(self):
        cn = self.__class__.__name__
        return "{0}: {1}/*{2}".format(cn, self.dir, self.filename_ext)
    
    def get_notebook_object(self, path):
        if not os.path.isfile(path):
            raise web.HTTPError(404, u'Notebook does not exist')
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

    def notebook_exists(self, path):
        """Does a notebook exist?"""
        return os.path.isfile(path)

    def new_notebook_object(self, path, public=False):
        return NBObject(self, path)

    def save_notebook_object(self, nb, path):
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

    def autosave_notebook(self, nb, nbo, client_id):
        self.save_notebook_object(nb, path=nbo.path)

    def delete_notebook(self, path):
        if not os.path.isfile(path):
            raise web.HTTPError(404, u'Notebook does not exist: ')

        os.unlink(path)

    def increment_filename(self, basename):
        """Return a non-used filename of the form basename<int>.
        
        This searches through the filenames (basename0, basename1, ...)
        until is find one that is not already being used. It is used to
        create Untitled and Copy names that are unique.
        """
        # normalize to name without file ext
        basename = basename.replace(self.filename_ext, '')
        ndir = self.dir
        i = 0
        while True:
            if basename != 'Untitled' and i == 0:
                name = basename
            else:
                name = u'%s%i' % (basename,i)
            name = name + self.filename_ext
            path = os.path.join(ndir, name)
            if not os.path.isfile(path):
                break
            else:
                i = i+1
        return path, name

class NBObject(object):
    def __init__(self, backend, path, name=None, mtime=None):
        self.backend = backend
        self.path = path
        self._name = name 
        self.tags = []
        self.mtime = mtime

    @property
    def name(self):
        return self._name or os.path.basename(self.path)


    def __repr__(self):
        return self.path

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        """
            Makes backwards compatible to when ndir was just a string
        """
        if isinstance(other, basestring):
            return self.path == other
        if isinstance(other, NBObject):
            return self.path == self.path

    def get_wd(self):
        """ Get Working Directory """
        return self.backend.dir
