from datetime import datetime, timezone, timedelta

def first(x):
    return x[0]

def utcnow():
    return datetime.now(tz=timezone.utc) + timedelta(days=2)

def ensure(b, m, retcode=1):
    if not b:
        inst = AssertionError(m)
        inst.retcode = retcode
        raise inst

def ymd(dt):
    ensure(isinstance(dt, datetime), "`ymd` expecting datetime object")
    return dt.strftime("%Y-%m-%d")
    
def splitfilter(fn, lst):
    ensure(callable(fn) and isinstance(lst, list), "bad arguments to splitfilter")
    group_a, group_b = [], []
    [(group_a if fn(x) else group_b).append(x) for x in lst]
    return group_a, group_b

lmap = lambda fn, lst: list(map(fn, lst))
lfilter = lambda fn, lst: list(filter(fn, lst))

def spy(val):
    print('spying: %s' % val)
    return val

def vals(d, *kl):
    return [d[k] for k in kl if k in d]
