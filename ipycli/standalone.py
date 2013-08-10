from ipycli.handlers import IPythonHandler,authenticate_unless_readonly
from zmq.utils import jsonapi

import kernel_client 

class StandaloneHandler(IPythonHandler):
    @authenticate_unless_readonly
    def get(self, kernel_id, html_obj):
        km = self.application.kernel_manager
        client = km.get_kernel(kernel_id).client()
        client = kernel_client.KernelClient(client)

        client.start_channels()
        code = '{html_obj}.to_html()'.format(hmtl_obj=html_obj);
        data = run_cell(client, code)
        client.stop_channels()

        data = data['text/plain']
        self.finish(jsonapi.dumps(data))

