import inspect
import linecache
import io
import re
from Queue import Empty
from ipycli.handlers import AuthenticatedHandler,authenticate_unless_readonly
from zmq.utils import jsonapi
import time

def get_source(func, func_name):
    """
    Grab the source of a function while un-indenting the first level
    """
    source = getsource(func, func_name)
    lines = source.split('\n')
    lines = [line for line in lines if line]
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
get_source({func_name}, "{func_name}")
"""

class CellFuncHandler(AuthenticatedHandler):
    @authenticate_unless_readonly
    def get(self, kernel_id, func_name):
        km = self.application.kernel_manager
        client = km.get_kernel(kernel_id).client()

        client.start_channels()
        code = CODE_FORMAT.format(func_name=func_name)
        data = run_cell(client, code)
        client.stop_channels()

        data = data['text/plain']
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
        if parent and client.session.session != parent['session']:
            continue
        if msg_type == 'pyout':
            data = sub_msg['content']['data']
            return data

def findsource(object, cache_key):
    """
    findsource that does not cache
    """
    file = inspect.getsourcefile(object)
    if not file:
        raise IOError('source code not available')
    lines = None

    with open(file) as f:
        lines = f.readlines()
    if not lines:
        raise IOError('could not get source code')

    if inspect.isfunction(object):
        code = object.func_code
    if inspect.iscode(code):
        if not hasattr(code, 'co_firstlineno'):
            raise IOError('could not find function definition')
        lnum = code.co_firstlineno - 1
        pat = re.compile(r'^(\s*def\s)|(.*(?<!\w)lambda(:|\s))|^(\s*@)')
        while lnum > 0:
            if pat.match(lines[lnum]): break
            lnum = lnum - 1
        # store func cache
        return lines, lnum
    raise IOError('could not find code code')

_FUNC_CACHE = {}
def getsourcelines(object, cache_key):
    """
    Cache based off of func_code object. When invalid, it'll
    check the file. 

    There's still a corner case.

    import module
    source = getsourcelines(module.func)
    # change module Change #2
    reload(module)
    # change module Change #3
    source = getsourcelines(module.func)

    source will relect change #3, even though #2 is currently the 
    code in the python interpreter. We need to get the lines
    from disk and change #2 is gone and only exists as compiled code
    """
    old_func_code, old_ret = _FUNC_CACHE.get(cache_key, (None, None))
    if object.func_code == old_func_code:
        return old_ret
    lines, lnum = _getsourcelines(object, cache_key)
    _FUNC_CACHE[cache_key] = (object.func_code, (lines, lnum))
    return lines, lnum

def _getsourcelines(object, cache_key):
    lines, lnum = findsource(object, cache_key)
    if inspect.ismodule(object): return lines, 0
    else: return inspect.getblock(lines[lnum:]), lnum + 1

def getsource(object, cache_key):
    lines, lnum = getsourcelines(object, cache_key)
    return ''.join(lines)
