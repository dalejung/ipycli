from ipycli.handlers import IPythonHandler,authenticate_unless_readonly
from zmq.utils import jsonapi

import kernel_client 

class StandaloneHandler(IPythonHandler):
    @authenticate_unless_readonly
    def get(self, kernel_id, html_obj):
        km = self.application.kernel_manager
        # kernel_id can also be a notebook_id
        try:
            client = km.get_kernel(kernel_id).client()
        except:
            kernel_id = km.kernel_for_notebook(kernel_id)
            client = km.get_kernel(kernel_id).client()

        client = kernel_client.KernelClient(client)

        code = '{html_obj}.to_html()'.format(html_obj=html_obj);
        data = client.execute(code)
        client.exit()

        data = data['text/plain']
        self.finish(data)
