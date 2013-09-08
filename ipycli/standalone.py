import os.path

from ipycli.handlers import IPythonHandler,authenticate_unless_readonly

import kernel_client 

CODE_FMT = """
from ipycli.standalone import get_html
get_html({html_obj}, "{attr}")
"""

def get_html(html_obj, attr):
    if hasattr(html_obj, 'html_obj'):
        html_obj = getattr(html_obj, 'html_obj')

    if hasattr(html_obj, attr):
        html = getattr(html_obj, attr)

    try:
        html = html_obj[attr]
    except:
        pass

    if callable(html):
        html = html()

    return html

class StandaloneHandler(IPythonHandler):
    @authenticate_unless_readonly
    def get(self, kernel_id, html_obj, attr=None):
        if not attr:
            self.redirect(self.request.path + '/to_html')
            return

        km = self.application.kernel_manager
        # kernel_id can also be a notebook_id
        try:
            client = km.get_kernel(kernel_id).client()
        except:
            kernel_id = km.kernel_for_notebook(kernel_id)
            client = km.get_kernel(kernel_id).client()

        client = kernel_client.KernelClient(client)

        code = CODE_FMT.format(html_obj=html_obj, attr=attr);
        data = client.execute(code)
        client.exit()

        html = '';
        if 'text/plain' in data:
            html = eval(data['text/plain'])

        self.finish(html)

class DirectoryHtml(object):
    """
    An HTMLObject that refences a directory
    """
    def __init__(self, dir, default=None):
        self.dir = dir
        self.default = default

    def __getitem__(self, key):
        path = os.path.join(self.dir, key)
        if os.path.exists(path):
            with open(path) as f:
                html = f.read()
            return html
        raise KeyError()

    def to_html(self):
        if self.default:
            return self[self.default]

def link(html_obj, link_name=None):
    """ 
    Use a Javascript Object so we can output the link using href and not onclick

    `window.location.pathname.split('/')[1]` should be notebook_id
    """
    from IPython.core.display import Javascript
    if link_name is None:
        link_name = html_obj
    js = """
    (function() {{
        var link_href = '/standalone/'+window.location.pathname.split('/')[1]+'/{html_obj}';
        element.append('<a target="_new" href="'+link_href+'">{link_name}</a>');
        container.show()
    }})()
    """.format(html_obj=html_obj, link_name=link_name)
    return Javascript(data=js)
