#!/bin/python3

#> Imports
import typing
#</Imports

#> Header >/
__all__ = ('mknamespace', 'rmknamespace')

def _namespace__call__(self: object, fn: typing.Callable):
    '''Add a function to the method object'''
    setattr(self, fn.__name__, fn)

def mknamespace(name: str = 'Namespace', doc: str | None = None, *,
                cattrs: dict[str, typing.Any] = {}, iattrs: dict[str, typing.Any] | None = None,
                instantiate: bool = True, slots: tuple[str] | None = None,
                make_decorator: bool = True) -> object | type:
    NamespaceType = type(name, (), cattrs)
    if doc is not None: NamespaceType.__doc__ = doc
    if make_decorator: NamespaceType.__call__ = _namespace__call__
    if not instantiate:
        assert iattrs is None, 'Cannot set instance attributes when instantiate is false'
        return NamespaceType
    ns = NamespaceType()
    if slots is None:
        if iattrs is not None: ns.__dict__.update(iattrs)
    else:
        assert not (iattrs.keys() - set(slots)), f'Some instance-attributes will not fit in slots {iattrs.keys() - set(slots)}'
        for a in slots: setattr(ns, iattrs[a])
    if doc is None: ns.__doc__ = doc
    return ns
def rmknamespace(root: object, names: str | tuple[str], doc: str | None = None, *, instantiate: typing.Literal[False] = False, **ns_args):
    assert ns_args.get('instantiate', False), 'Cannot recursively make namespaces with instantiate=True'
    for n in names[:-1]:
        if not hasattr(root, n):
            root.n = mknamespace(n)
        root = getattr(root, n)
    assert not hasattr(root, names[-1]), 'Namespace already exists!'
    ns = mknamespace(names[-1], doc, **ns_args)
    setattr(root, names[-1], ns)
    return ns
