import inspect
from functools import partial

import ipycli.cell_func as cell_func

def fake_func(d=123, kw2=3):
    kw1 = 'dale'
    kw2 = 11

fake_func = partial(fake_func)

func = fake_func

keywords = cell_func.get_callable_keywords(fake_func)
cc = cell_func.get_source(fake_func, 'fake_func')
source = cc['source']

correct = {'d':123, 'kw1':'dale', 'kw2':11}
tdict = {}
exec source in tdict

for k in tdict:
    if k == '__builtins__':
        continue
    assert correct[k] == tdict[k]
