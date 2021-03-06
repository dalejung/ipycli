"""Tornado handlers for the notebook.

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

import logging
import Cookie
import time
import uuid
import os.path

from tornado import web
from tornado import websocket

from zmq.eventloop import ioloop
from zmq.utils import jsonapi

from IPython.external.decorator import decorator
from IPython.kernel.zmq.session import Session
from IPython.lib.security import passwd_check
from IPython.utils.jsonutil import date_default
from IPython.frontend.html.notebook.base.handlers import IPythonHandler

try:
    from docutils.core import publish_string
except ImportError:
    publish_string = None


_old_auth = web.authenticated
def debug_auth(*args, **kwargs):
    old_wrapped = _old_auth(*args, **kwargs)
    def new_wrapped(*args, **kwargs):
        print 'start', args[0].__class__.__name__
        res = old_wrapped(*args, **kwargs)
        print 'end', args[0].__class__.__name__
        return res
    return new_wrapped
web.authenticated = debug_auth

#-----------------------------------------------------------------------------
# Monkeypatch for Tornado <= 2.1.1 - Remove when no longer necessary!
#-----------------------------------------------------------------------------

# Google Chrome, as of release 16, changed its websocket protocol number.  The
# parts tornado cares about haven't really changed, so it's OK to continue
# accepting Chrome connections, but as of Tornado 2.1.1 (the currently released
# version as of Oct 30/2011) the version check fails, see the issue report:

# https://github.com/facebook/tornado/issues/385

# This issue has been fixed in Tornado post 2.1.1:

# https://github.com/facebook/tornado/commit/84d7b458f956727c3b0d6710

# Here we manually apply the same patch as above so that users of IPython can
# continue to work with an officially released Tornado.  We make the
# monkeypatch version check as narrow as possible to limit its effects; once
# Tornado 2.1.1 is no longer found in the wild we'll delete this code.

import tornado

if tornado.version_info <= (2,1,1):

    def _execute(self, transforms, *args, **kwargs):
        from tornado.websocket import WebSocketProtocol8, WebSocketProtocol76

        self.open_args = args
        self.open_kwargs = kwargs

        # The difference between version 8 and 13 is that in 8 the
        # client sends a "Sec-Websocket-Origin" header and in 13 it's
        # simply "Origin".
        if self.request.headers.get("Sec-WebSocket-Version") in ("7", "8", "13"):
            self.ws_connection = WebSocketProtocol8(self)
            self.ws_connection.accept_connection()

        elif self.request.headers.get("Sec-WebSocket-Version"):
            self.stream.write(tornado.escape.utf8(
                "HTTP/1.1 426 Upgrade Required\r\n"
                "Sec-WebSocket-Version: 8\r\n\r\n"))
            self.stream.close()

        else:
            self.ws_connection = WebSocketProtocol76(self)
            self.ws_connection.accept_connection()

    websocket.WebSocketHandler._execute = _execute
    del _execute

#-----------------------------------------------------------------------------
# Decorator for disabling read-only handlers
#-----------------------------------------------------------------------------

@decorator
def not_if_readonly(f, self, *args, **kwargs):
    if self.application.read_only:
        raise web.HTTPError(403, "Notebook server is read-only")
    else:
        return f(self, *args, **kwargs)

@decorator
def authenticate_unless_readonly(f, self, *args, **kwargs):
    """authenticate this page *unless* readonly view is active.

    In read-only mode, the notebook list and print view should
    be accessible without authentication.
    """

    @web.authenticated
    def auth_f(self, *args, **kwargs):
        return f(self, *args, **kwargs)

    def _wrap():
        print '_wrap'
        return f(self, *args, **kwargs)


    if self.application.read_only:
        return _wrap()
    else:
        return auth_f(self, *args, **kwargs)

#-----------------------------------------------------------------------------
# Top-level handlers
#-----------------------------------------------------------------------------

def set_default_headers(self):
    try:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        self.set_header("Access-Control-Allow-Headers",
            "Content-Type, Depth, User-Agent, X-File-Size, X-Requested-With, X-Requested-By, If-Modified-Since, X-File-Name, Cache-Control")
    except:
        # doesn't work for web sockets
        pass

IPythonHandler.set_default_headers = set_default_headers
# this is deprecated, but just keep around for backward compat
IPythonHandler.read_only = False

class AuthenticatedFileHandler(IPythonHandler, web.StaticFileHandler):
    """static files should only be accessible when logged in"""

    @authenticate_unless_readonly
    def get(self, path):
        return web.StaticFileHandler.get(self, path)


class ProjectDashboardHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self, project=None):
        nbm = self.application.notebook_manager
        if project is None:
            project = nbm.notebook_dir
        self.render(
            'projectdashboard.html', project=project,
            base_project_url=self.application.ipython_app.base_project_url,
            base_kernel_url=self.application.ipython_app.base_kernel_url,
            read_only=self.read_only,
            logged_in=self.logged_in,
            login_available=self.login_available
        )


class LoginHandler(IPythonHandler):

    def _render(self, message=None):
        self.render('login.html',
                next=self.get_argument('next', default='/'),
                read_only=self.read_only,
                logged_in=self.logged_in,
                login_available=self.login_available,
                base_project_url=self.application.ipython_app.base_project_url,
                message=message
        )

    def get(self):
        if self.current_user:
            self.redirect(self.get_argument('next', default='/'))
        else:
            self._render()

    def post(self):
        pwd = self.get_argument('password', default=u'')
        if self.application.password:
            if passwd_check(self.application.password, pwd):
                self.set_secure_cookie('username', str(uuid.uuid4()))
            else:
                self._render(message={'error': 'Invalid password'})
                return

        self.redirect(self.get_argument('next', default='/'))


class LogoutHandler(IPythonHandler):

    def get(self):
        self.clear_cookie('username')
        if self.login_available:
            message = {'info': 'Successfully logged out.'}
        else:
            message = {'warning': 'Cannot log out.  Notebook authentication '
                       'is disabled.'}

        self.render('logout.html',
                    read_only=self.read_only,
                    logged_in=self.logged_in,
                    login_available=self.login_available,
                    base_project_url=self.application.ipython_app.base_project_url,
                    message=message)


class NewHandler(IPythonHandler):

    @web.authenticated
    def get(self, path=None, public=False):
        """
        The GET works with FolderBackend
        Used for nb commandline tool
        """
        nbm = self.application.notebook_manager
        project = nbm.notebook_dir

        name = None
        backend = None

        # for now, pathed_notebooks will just enable a folder project
        if path:
            ndir, name = os.path.split(path)
            # see if notebook exists
            for be in nbm.notebook_dirs.values():
                if ndir == be.path:
                    backend = be
                    break
            if backend is None:
                backend = nbm.add_notebook_dir(ndir)

        # default to defaultdir
        if backend is None:
            backend = nbm.notebook_dirs[0]

        notebook_id = nbm.new_notebook(backend=backend, name=name, public=public)
        self.render(
            'notebook.html', project=project,
            notebook_id=notebook_id,
            base_project_url=self.application.ipython_app.base_project_url,
            base_kernel_url=self.application.ipython_app.base_kernel_url,
            notebook_path=path,
            kill_kernel=False,
            read_only=False,
            logged_in=self.logged_in,
            login_available=self.login_available,
            mathjax_url=self.application.ipython_app.mathjax_url,
        )

    @web.authenticated
    def post(self):
        nbm = self.application.notebook_manager

        project_path = self.get_argument('project_path', default=None)
        public = self.get_argument('public', default=False)
        public = bool(public)
        backend = nbm.backend_by_path(project_path)
        name = None
        notebook_id = nbm.new_notebook(backend=backend, name=name, public=public)
        data = {'notebook_id':notebook_id}
        self.set_header('Location', '/'+notebook_id)
        self.finish(jsonapi.dumps(data))


class NamedNotebookHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self, notebook_id):
        nbm = self.application.notebook_manager
        project = nbm.notebook_dir

        nb = nbm.mapping[notebook_id]
        notebook_path = nb.path

        self.render(
            'notebook.html', project=project,
            notebook_id=notebook_id,
            base_project_url=self.application.ipython_app.base_project_url,
            base_kernel_url=self.application.ipython_app.base_kernel_url,
            notebook_path=notebook_path,
            kill_kernel=False,
            read_only=self.read_only,
            logged_in=self.logged_in,
            login_available=self.login_available,
            mathjax_url=self.application.ipython_app.mathjax_url,
        )

class PathedNotebookHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self, notebook_path):
        # haven't built a pathednotebook backend.
        return
        nbm = self.application.notebook_manager
        project = nbm.notebook_dir
        notebook_id = nbm.get_pathed_notebook(notebook_path)
        if not notebook_id:
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)

        self.render(
            'notebook.html', project=project,
            notebook_id=notebook_id,
            notebook_path=notebook_path,
            base_project_url=self.application.ipython_app.base_project_url,
            base_kernel_url=self.application.ipython_app.base_kernel_url,
            kill_kernel=False,
            read_only=self.read_only,
            logged_in=self.logged_in,
            login_available=self.login_available,
            mathjax_url=self.application.ipython_app.mathjax_url,
        )


class PrintNotebookHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self, notebook_id):
        nbm = self.application.notebook_manager
        project = nbm.notebook_dir
        if not nbm.notebook_exists(notebook_id):
            raise web.HTTPError(404, u'Notebook does not exist: %s' % notebook_id)

        self.render(
            'printnotebook.html', project=project,
            notebook_id=notebook_id,
            base_project_url=self.application.ipython_app.base_project_url,
            base_kernel_url=self.application.ipython_app.base_kernel_url,
            kill_kernel=False,
            read_only=self.read_only,
            logged_in=self.logged_in,
            login_available=self.login_available,
            mathjax_url=self.application.ipython_app.mathjax_url,
        )

#-----------------------------------------------------------------------------
# Kernel handlers
#-----------------------------------------------------------------------------


class MainKernelHandler(IPythonHandler):

    @web.authenticated
    def get(self):
        km = self.application.kernel_manager
        self.finish(jsonapi.dumps(km.kernel_ids))

    @web.authenticated
    def post(self):
        km = self.application.kernel_manager
        nbm = self.application.notebook_manager
        notebook_id = self.get_argument('notebook', default=None)

        nbo = nbm.mapping[notebook_id]
        dirpath = nbo.get_wd()
        # if no dirpath. Start kernel is default_dir
        if dirpath is None:
            dirpath = nbm.notebook_dir

        kernel_id = km.start_kernel(notebook_id, cwd=dirpath)
        data = {'ws_url':self.ws_url,'kernel_id':kernel_id}
        self.set_header('Location', '/'+kernel_id)
        self.finish(jsonapi.dumps(data))


class KernelHandler(IPythonHandler):

    SUPPORTED_METHODS = ('DELETE')

    @web.authenticated
    def delete(self, kernel_id):
        km = self.application.kernel_manager
        km.shutdown_kernel(kernel_id)
        self.set_status(204)
        self.finish()


class KernelActionHandler(IPythonHandler):

    @web.authenticated
    def post(self, kernel_id, action):
        km = self.application.kernel_manager
        if action == 'interrupt':
            km.interrupt_kernel(kernel_id)
            self.set_status(204)
        if action == 'restart':
            km.restart_kernel(kernel_id)
            data = {'ws_url':self.ws_url,'kernel_id':kernel_id}
            self.set_header('Location', '/'+kernel_id)
            self.write(jsonapi.dumps(data))
        self.finish()


class ZMQStreamHandler(websocket.WebSocketHandler):

    def _reserialize_reply(self, msg_list):
        """Reserialize a reply message using JSON.

        This takes the msg list from the ZMQ socket, unserializes it using
        self.session and then serializes the result using JSON. This method
        should be used by self._on_zmq_reply to build messages that can
        be sent back to the browser.
        """
        idents, msg_list = self.session.feed_identities(msg_list)
        msg = self.session.unserialize(msg_list)
        try:
            msg['header'].pop('date')
        except KeyError:
            pass
        try:
            msg['parent_header'].pop('date')
        except KeyError:
            pass
        msg.pop('buffers')
        return jsonapi.dumps(msg, default=date_default)

    def _on_zmq_reply(self, msg_list):
        try:
            msg = self._reserialize_reply(msg_list)
        except Exception:
            self.application.log.critical("Malformed message: %r" % msg_list, exc_info=True)
        else:
            self.write_message(msg)

    def allow_draft76(self):
        """Allow draft 76, until browsers such as Safari update to RFC 6455.

        This has been disabled by default in tornado in release 2.2.0, and
        support will be removed in later versions.
        """
        return True


class AuthenticatedZMQStreamHandler(ZMQStreamHandler):

    def open(self, kernel_id):
        self.kernel_id = kernel_id.decode('ascii')
        try:
            cfg = self.application.ipython_app.config
        except AttributeError:
            # protect from the case where this is run from something other than
            # the notebook app:
            cfg = None
        self.session = Session(config=cfg)
        self.save_on_message = self.on_message
        self.on_message = self.on_first_message

    def get_current_user(self):
        user_id = self.get_secure_cookie("username")
        if user_id == '' or (user_id is None and not self.application.password):
            user_id = 'anonymous'
        return user_id

    def _inject_cookie_message(self, msg):
        """Inject the first message, which is the document cookie,
        for authentication."""
        if isinstance(msg, unicode):
            # Cookie can't constructor doesn't accept unicode strings for some reason
            msg = msg.encode('utf8', 'replace')
        try:
            self.request._cookies = Cookie.SimpleCookie(msg)
        except:
            logging.warn("couldn't parse cookie string: %s",msg, exc_info=True)

    def on_first_message(self, msg):
        self._inject_cookie_message(msg)
        if self.get_current_user() is None:
            logging.warn("Couldn't authenticate WebSocket connection")
            raise web.HTTPError(403)
        self.on_message = self.save_on_message


class IOPubHandler(AuthenticatedZMQStreamHandler):

    def initialize(self, *args, **kwargs):
        self._kernel_alive = True
        self._beating = False
        self.iopub_stream = None
        self.hb_stream = None

    def on_first_message(self, msg):
        try:
            super(IOPubHandler, self).on_first_message(msg)
        except web.HTTPError:
            self.close()
            return
        km = self.application.kernel_manager
        self.time_to_dead = km.time_to_dead
        self.first_beat = km.first_beat
        kernel_id = self.kernel_id
        try:
            self.iopub_stream = km.create_iopub_stream(kernel_id)
            self.hb_stream = km.create_hb_stream(kernel_id)
        except web.HTTPError:
            # WebSockets don't response to traditional error codes so we
            # close the connection.
            if not self.stream.closed():
                self.stream.close()
            self.close()
        else:
            self.iopub_stream.on_recv(self._on_zmq_reply)
            self.start_hb(self.kernel_died)

    def on_message(self, msg):
        pass

    def on_close(self):
        # This method can be called twice, once by self.kernel_died and once
        # from the WebSocket close event. If the WebSocket connection is
        # closed before the ZMQ streams are setup, they could be None.
        self.stop_hb()
        if self.iopub_stream is not None and not self.iopub_stream.closed():
            self.iopub_stream.on_recv(None)
            self.iopub_stream.close()
        if self.hb_stream is not None and not self.hb_stream.closed():
            self.hb_stream.close()

    def start_hb(self, callback):
        """Start the heartbeating and call the callback if the kernel dies."""
        if not self._beating:
            self._kernel_alive = True

            def ping_or_dead():
                self.hb_stream.flush()
                if self._kernel_alive:
                    self._kernel_alive = False
                    self.hb_stream.send(b'ping')
                    # flush stream to force immediate socket send
                    self.hb_stream.flush()
                else:
                    try:
                        callback()
                    except:
                        pass
                    finally:
                        self.stop_hb()

            def beat_received(msg):
                self._kernel_alive = True

            self.hb_stream.on_recv(beat_received)
            loop = ioloop.IOLoop.instance()
            self._hb_periodic_callback = ioloop.PeriodicCallback(ping_or_dead, self.time_to_dead*1000, loop)
            loop.add_timeout(time.time()+self.first_beat, self._really_start_hb)
            self._beating= True

    def _really_start_hb(self):
        """callback for delayed heartbeat start

        Only start the hb loop if we haven't been closed during the wait.
        """
        if self._beating and not self.hb_stream.closed():
            self._hb_periodic_callback.start()

    def stop_hb(self):
        """Stop the heartbeating and cancel all related callbacks."""
        if self._beating:
            self._beating = False
            self._hb_periodic_callback.stop()
            if not self.hb_stream.closed():
                self.hb_stream.on_recv(None)

    def kernel_died(self):
        self.application.kernel_manager.delete_mapping_for_kernel(self.kernel_id)
        self.application.log.error("Kernel %s failed to respond to heartbeat", self.kernel_id)
        self.write_message(
            {'header': {'msg_type': 'status'},
             'parent_header': {},
             'content': {'execution_state':'dead'}
            }
        )
        self.on_close()


class ShellHandler(AuthenticatedZMQStreamHandler):

    def initialize(self, *args, **kwargs):
        self.shell_stream = None

    def on_first_message(self, msg):
        try:
            super(ShellHandler, self).on_first_message(msg)
        except web.HTTPError:
            self.close()
            return
        km = self.application.kernel_manager
        self.max_msg_size = km.max_msg_size
        kernel_id = self.kernel_id
        try:
            self.shell_stream = km.create_shell_stream(kernel_id)
        except web.HTTPError:
            # WebSockets don't response to traditional error codes so we
            # close the connection.
            if not self.stream.closed():
                self.stream.close()
            self.close()
        else:
            self.shell_stream.on_recv(self._on_zmq_reply)

    def on_message(self, msg):
        if len(msg) < self.max_msg_size:
            msg = jsonapi.loads(msg)
            self.session.send(self.shell_stream, msg)

    def on_close(self):
        # Make sure the stream exists and is not already closed.
        if self.shell_stream is not None and not self.shell_stream.closed():
            self.shell_stream.close()


#-----------------------------------------------------------------------------
# Notebook web service handlers
#-----------------------------------------------------------------------------

class NotebookRootHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self):
        nbm = self.application.notebook_manager
        km = self.application.kernel_manager
        files = nbm.list_notebooks()
        used_projects = {}
        for f in files :
            f['kernel_id'] = km.kernel_for_notebook(f['notebook_id'])
            backend = nbm.backend_by_notebook_id(f['notebook_id'])
            used_projects[backend] = backend
            f['project_path'] = backend.path

        backends = []
        for backend in nbm.notebook_projects:
            if backend not in used_projects:
                continue
            b = {'name': backend.name, 'path': backend.path}
            backends.append(b)

        data = {'files': files, 'projects': backends}
        self.finish(jsonapi.dumps(data))

    @web.authenticated
    def post(self):
        nbm = self.application.notebook_manager
        body = self.request.body.strip()
        format = self.get_argument('format', default='json')
        name = self.get_argument('name', default=None)
        if body:
            notebook_id = nbm.save_new_notebook(body, name=name, format=format)
        else:
            notebook_id = nbm.new_notebook()
        self.set_header('Location', '/'+notebook_id)
        self.finish(jsonapi.dumps(notebook_id))

class AllNotebookRootHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self):
        nbm = self.application.notebook_manager
        km = self.application.kernel_manager
        files = nbm.all_notebooks()
        for f in files :
            f['kernel_id'] = km.kernel_for_notebook(f['notebook_id'])
            backend = nbm.backend_by_notebook_id(f['notebook_id'])
            f['project_path'] = backend.path

        backends = []
        for backend in nbm.notebook_projects:
            b = {'name': backend.name, 'path': backend.path}
            backends.append(b)

        data = {'files': files, 'projects': backends}
        self.finish(jsonapi.dumps(data))

class ActiveNotebooksHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self):
        nbm = self.application.notebook_manager
        km = self.application.kernel_manager
        files = nbm.all_notebooks()
        for f in files :
            f['kernel_id'] = km.kernel_for_notebook(f['notebook_id'])
            backend = nbm.backend_by_notebook_id(f['notebook_id'])
            f['project_path'] = backend.path

        # active kernels
        files = [f for f in files if f['kernel_id'] is not None]

        backends = []
        for backend in nbm.notebook_projects:
            b = {'name': backend.name, 'path': backend.path}
            backends.append(b)

        data = {'files': files, 'projects': backends}
        self.finish(jsonapi.dumps(data))

class NotebookTagHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self, tag):
        nbm = self.application.notebook_manager
        km = self.application.kernel_manager
        files = nbm.tagged_notebooks(tag)

        backend = None
        for f in files :
            f['kernel_id'] = km.kernel_for_notebook(f['notebook_id'])
            backend = nbm.backend_by_notebook_id(f['notebook_id'])
            f['project_path'] = backend.path

        # all these should be from the same backend, for now
        backends = []
        b = {'name': backend.name, 'path': backend.path}
        backends.append(b)

        data = {'files': files, 'projects': backends}
        self.finish(jsonapi.dumps(data))

class NotebookDirHandler(IPythonHandler):

    @authenticate_unless_readonly
    def get(self, dir):
        nbm = self.application.notebook_manager
        km = self.application.kernel_manager
        files = nbm.dir_notebooks(dir)

        used_projects = {}
        backend = None
        for f in files :
            f['kernel_id'] = km.kernel_for_notebook(f['notebook_id'])
            backend = nbm.backend_by_notebook_id(f['notebook_id'])
            used_projects[backend] = backend
            f['project_path'] = backend.path

        # all these should be from the same backend, for now
        backends = [{'name':backend.path, 'path': backend.path} for backend in used_projects]

        data = {'files': files, 'projects': backends}
        self.finish(jsonapi.dumps(data))

class NotebookHandler(IPythonHandler):

    SUPPORTED_METHODS = ('GET', 'PUT', 'DELETE')

    @authenticate_unless_readonly
    def get(self, notebook_id):
        nbm = self.application.notebook_manager
        format = self.get_argument('format', default='json')
        last_mod, name, data = nbm.get_notebook(notebook_id, format)

        if format == u'json':
            self.set_header('Content-Type', 'application/json')
            self.set_header('Content-Disposition','attachment; filename="%s.ipynb"' % name)
        elif format == u'py':
            self.set_header('Content-Type', 'application/x-python')
            self.set_header('Content-Disposition','attachment; filename="%s.py"' % name)
        self.set_header('Last-Modified', last_mod)
        self.finish(data)

    @web.authenticated
    def put(self, notebook_id):
        nbm = self.application.notebook_manager
        format = self.get_argument('format', default='json')
        name = self.get_argument('name', default=None)
        nbm.save_notebook(notebook_id, self.request.body, name=name, format=format)
        self.set_status(204)
        self.finish()

    @web.authenticated
    def delete(self, notebook_id):
        nbm = self.application.notebook_manager
        nbm.delete_notebook(notebook_id)
        self.set_status(204)
        self.finish()

class AutosaveNotebookHandler(IPythonHandler):

    SUPPORTED_METHODS = ('PUT')

    @web.authenticated
    def put(self, notebook_id, client_id):
        nbm = self.application.notebook_manager
        format = self.get_argument('format', default='json')
        name = self.get_argument('name', default=None)
        nbm.autosave_notebook(notebook_id, self.request.body, name=name, client_id=client_id, format=format)
        self.set_status(204)
        self.finish()

class RenameNotebookHandler(IPythonHandler):

    SUPPORTED_METHODS = ('PUT')

    @web.authenticated
    def put(self, notebook_id):
        nbm = self.application.notebook_manager
        format = self.get_argument('format', default='json')
        name = self.get_argument('name', default=None)
        nbm.rename_notebook(notebook_id, self.request.body, name=name, format=format)
        self.set_status(204)
        self.finish()


class NotebookCopyHandler(IPythonHandler):

    @web.authenticated
    def get(self, notebook_id):
        nbm = self.application.notebook_manager
        project = nbm.notebook_dir
        notebook_id = nbm.copy_notebook(notebook_id)
        notebook_path = nbm.find_path(notebook_id)
        self.render(
            'notebook.html', project=project,
            notebook_id=notebook_id,
            notebook_path=notebook_path,
            base_project_url=self.application.ipython_app.base_project_url,
            base_kernel_url=self.application.ipython_app.base_kernel_url,
            kill_kernel=False,
            read_only=False,
            logged_in=self.logged_in,
            login_available=self.login_available,
            mathjax_url=self.application.ipython_app.mathjax_url,
        )

class AddNotebookDirHandler(IPythonHandler):

    @web.authenticated
    def get(self, path):
        nbm = self.application.notebook_manager
        if not os.path.isdir(path):
            raise web.HTTPError(503, u'Not valid Directory')

        nbm.add_notebook_dir(path)


#-----------------------------------------------------------------------------
# Cluster handlers
#-----------------------------------------------------------------------------


class MainClusterHandler(IPythonHandler):

    @web.authenticated
    def get(self):
        cm = self.application.cluster_manager
        self.finish(jsonapi.dumps(cm.list_profiles()))


class ClusterProfileHandler(IPythonHandler):

    @web.authenticated
    def get(self, profile):
        cm = self.application.cluster_manager
        self.finish(jsonapi.dumps(cm.profile_info(profile)))


class ClusterActionHandler(IPythonHandler):

    @web.authenticated
    def post(self, profile, action):
        cm = self.application.cluster_manager
        if action == 'start':
            n = self.get_argument('n',default=None)
            if n is None:
                data = cm.start_cluster(profile)
            else:
                data = cm.start_cluster(profile,int(n))
        if action == 'stop':
            data = cm.stop_cluster(profile)
        self.finish(jsonapi.dumps(data))


#-----------------------------------------------------------------------------
# RST web service handlers
#-----------------------------------------------------------------------------


class RSTHandler(IPythonHandler):

    @web.authenticated
    def post(self):
        if publish_string is None:
            raise web.HTTPError(503, u'docutils not available')
        body = self.request.body.strip()
        source = body
        # template_path=os.path.join(os.path.dirname(__file__), u'templates', u'rst_template.html')
        defaults = {'file_insertion_enabled': 0,
                    'raw_enabled': 0,
                    '_disable_config': 1,
                    'stylesheet_path': 0
                    # 'template': template_path
        }
        try:
            html = publish_string(source, writer_name='html',
                                  settings_overrides=defaults
            )
        except:
            raise web.HTTPError(400, u'Invalid RST')
        print html
        self.set_header('Content-Type', 'text/html')
        self.finish(html)


