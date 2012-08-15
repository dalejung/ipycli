import glob
import io
import os.path
import datetime

from tornado import web

from IPython.nbformat import current

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
        nbs = [NBObject(backend=self, path=name) for name in names]
        return nbs

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

    def new_notebook_object(self, path):
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
        old_path = nbo.path 
        ndir, filename = os.path.split(old_path)
        filename = '.' + filename + '.' + client_id + ".save"
        path = os.path.join(ndir, filename)
        self.save_notebook_object(nb, path=path)

    def delete_notebook(self, path):
        if not os.path.isfile(path):
            raise web.HTTPError(404, u'Notebook does not exist: ')

        os.unlink(path)

        if self.save_script:
            old_pypath = os.path.splitext(old_path)[0] + '.py'
            if os.path.isfile(old_pypath):
                os.unlink(old_pypath)

    def increment_filename(self, basename):
        """Return a non-used filename of the form basename<int>.
        
        This searches through the filenames (basename0, basename1, ...)
        until is find one that is not already being used. It is used to
        create Untitled and Copy names that are unique.
        """
        ndir = self.dir
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

class NBObject(object):
    def __init__(self, backend, path):
        self.backend = backend
        self.path = path

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
