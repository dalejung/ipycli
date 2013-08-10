from IPython.lib.kernel import find_connection_file
from IPython.kernel.manager import KernelManager

import time

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

    if client.shell_channel.msg_ready():
        handle_execute_reply(client, msg_id)
    # meh. sometimes iopub doesn't have the pyout.
    # sleep for 100ms to make sure it's in there
    # probably shouldn't be here
    time.sleep(.1)
    data = get_pyout(client)
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
        parent = sub_msg["parent_header"]

        if msg_type == 'status' and sub_msg['content']['execution_state'] == 'idle':
            pass

        if parent and client.session.session != parent['session']:
            continue
        if msg_type == 'pyout':
            data = sub_msg['content']['data']
            return data


class KernelClient(object):
    def __init__(self, client):
        self.client = client
        self.client.start_channels()

    def execute(self, code):
        data = run_cell(self.client, code)
        return data

    def exit(self):
        self.client.stop_channels()

def get_client(cf):
    connection_file = find_connection_file(cf)
    km = KernelManager(connection_file=connection_file)
    km.load_connection_file()

    client = km.client()
    return KernelClient(client)
