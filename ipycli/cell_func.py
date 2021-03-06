import inspect
import linecache
from functools import partial
import io
import re
from Queue import Empty
from zmq.utils import jsonapi
import time

from ipycli.handlers import IPythonHandler,authenticate_unless_readonly
import kernel_client 

def get_source(func, func_name):
    """
    Grab the source of a function while un-indenting the first level

    Note:
        keyword arguments for the function will be placed into source
        body as assignments. This is so we can define defaults

        def fake_func(d=123, kw2=3):
            kw1 = 'dale'
            kw2 = 11

        generates the following source. Essentially keyword header + code

        # keywords
        kw2 = 3
        d = 123

        kw1 = 'dale'
        kw2 = 11
    """
    base_func = func
    if isinstance(func, partial):
        base_func = func.func

    source = getsource(base_func, func_name)
    file = inspect.getsourcefile(base_func)
    keywords = get_callable_keywords(func)

    lines = source.split('\n')
    # get rid of empty last line
    if not lines[-1]:
        lines = lines[:-1]
    assert lines[0].startswith('def ')

    # unindent the code lines
    code_lines = _unindent_lines(lines[1:])
    keyword_lines = ["{k} = {v}".format(k=k, v=repr(v)) for k, v in keywords.items()]
    if keyword_lines:
        keyword_lines = ['# keywords'] + keyword_lines + ['']

    unindented = '\n'.join(keyword_lines + code_lines)
    return {'file':file, 'source':unindented}

def _unindent_lines(lines):
    first_line = lines[0]
    first_indent = len(first_line) - len(first_line.lstrip())

    unindented_lines = [line[first_indent:] for line in lines]
    return unindented_lines

CODE_FORMAT = """
from ipycli.cell_func import get_source
get_source({func_name}, "{func_name}")
"""

class CellFuncHandler(IPythonHandler):
    @authenticate_unless_readonly
    def get(self, kernel_id, func_name):
        km = self.application.kernel_manager
        client = km.get_kernel(kernel_id).client()

        client = kernel_client.KernelClient(client)
        code = CODE_FORMAT.format(func_name=func_name)
        data = client.execute(code)

        data = data['text/plain']
        self.finish(jsonapi.dumps(data))

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

def _func_keywords(func):
    argspec = inspect.getargspec(func)
    args = argspec.args
    if not args:
        return {}
    defaults = argspec.defaults
    if len(args) != len(defaults):
        raise Exception("We only support kwargs")
    keywords = dict(zip(args, defaults))
    return keywords

def _partial_keywords(func):
    keywords = _func_keywords(func.func)
    if func.keywords:
        keywords.update(func.keywords)
    return keywords

def get_callable_keywords(func):
    """
    Grab the defined keywords for a function or partial.
    """
    if isinstance(func, partial):
        return _partial_keywords(func)
    return _func_keywords(func)
