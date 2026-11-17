import marshal, sys, py_compile, tempfile, types
from pathlib import Path
app, kaynak = Path(sys.argv[1]), Path(sys.argv[2])
def norm(c):
    if isinstance(c, types.CodeType):
        return (c.co_code, tuple(norm(x) for x in c.co_consts), c.co_names, c.co_varnames, c.co_freevars, c.co_cellvars,
                c.co_name, c.co_argcount, c.co_kwonlyargcount, c.co_flags, c.co_filename)
    if isinstance(c, (tuple, frozenset)):
        return (type(c).__name__, tuple(norm(x) for x in (sorted(c, key=repr) if isinstance(c, frozenset) else c)))
    return c
fark, n = [], 0
for p in sorted((app / "bist_haber").rglob("*.pyc")):
    src = kaynak / p.relative_to(app).with_suffix(".py")
    with tempfile.TemporaryDirectory() as t:
        c = Path(t) / "x.pyc"
        py_compile.compile(str(src), cfile=str(c), dfile=p.relative_to(app).with_suffix(".py").as_posix(), doraise=True)
        a, b = marshal.loads(p.read_bytes()[16:]), marshal.loads(c.read_bytes()[16:])
    n += 1
    if norm(a) != norm(b):
        fark.append(p.relative_to(app).as_posix())
a = marshal.loads((app / "app_kod.pyc").read_bytes()[16:])
with tempfile.TemporaryDirectory() as t:
    c = Path(t) / "x.pyc"; py_compile.compile(str(kaynak / "app.py"), cfile=str(c), dfile="app.py", doraise=True)
    b = marshal.loads(c.read_bytes()[16:])
print("karşılaştırılan", n + 1, "farklı", fark + ([] if norm(a) == norm(b) else ["app_kod.pyc"]))
