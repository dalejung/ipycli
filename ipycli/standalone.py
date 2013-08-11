from ipycli.handlers import IPythonHandler,authenticate_unless_readonly
from zmq.utils import jsonapi

import kernel_client 

CODE_FMT = """
from ipycli.standalone import get_html
get_html({html_obj}, "{attr}")
"""

def get_html(html_obj, attr):
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
