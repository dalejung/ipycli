import inspect
import io
from Queue import Empty
from ipycli.handlers import AuthenticatedHandler,authenticate_unless_readonly
from zmq.utils import jsonapi

def get_source(func):
    """
    Grab the source of a function while un-indenting the first level
    """
    lines = inspect.getsource(func).split('\n')
    assert lines[0].startswith('def ')
    body_lines = lines[1:]
    first_line = body_lines[0]
    first_indent = len(first_line) - len(first_line.lstrip())

    unindented_lines = [line[first_indent:] for line in body_lines]
    unindented = '\n'.join(unindented_lines)
    file = inspect.getsourcefile(func)
    return {'file':file, 'source':unindented}

CODE_FORMAT = """
from ipycli.cell_func import get_source
get_source({func_name})
"""

class CellFuncHandler(AuthenticatedHandler):
    @authenticate_unless_readonly
    def get(self, kernel_id, func_name):
        km = self.application.kernel_manager
        #client = km.get_kernel(kernel_id).client()
        client = km._kernels.values()[0].client()
        client.start_channels()
        code = CODE_FORMAT.format(func_name=func_name)
        source = run_cell(client, code)
        client.stop_channels()

        data = {'source':source}
        self.finish(jsonapi.dumps(data))

def run_cell(client, cell, store_history=True):
    """
    Taken from ipython.frontend.terminal.console.ZMQInteractiveShell
    """
    if (not cell) or cell.isspace():
        return

    # flush stale replies, which could have been ignored, due to missed heartbeats
    while client.shell_channel.msg_ready():
        client.shell_channel.get_msg()
    # shell_channel.execute takes 'hidden', which is the inverse of store_hist
    msg_id = client.shell_channel.execute(cell, not store_history)
    while not client.shell_channel.msg_ready(): # wait for completion
        pass

    data = get_pyout(client)

    if client.shell_channel.msg_ready():
        handle_execute_reply(client, msg_id)
    return data

def handle_execute_reply(client, msg_id):
    msg = client.shell_channel.get_msg()
    if msg["parent_header"].get("msg_id", None) == msg_id:
        
        content = msg["content"]
        status = content['status']
        
        if status == 'aborted':
            #self.write('Aborted\n')
            return
        elif status == 'ok':
            # print execution payloads as well:
            for item in content["payload"]:
                text = item.get('text', None)
                if text:
                    pass
                    #page.page(text)
        elif status == 'error':
            for frame in content["traceback"]:
                print(frame)

def get_pyout(client):
    while client.iopub_channel.msg_ready():
        sub_msg = client.iopub_channel.get_msg()
        msg_type = sub_msg['header']['msg_type']
        if msg_type == 'pyout':
            data = sub_msg['content']['data']
            return data
