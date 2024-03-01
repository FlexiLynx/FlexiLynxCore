#!/bin/python3

'''Provides the `Manager` class'''

#> Imports
from threading import RLock

from .module import Module

from . import logger

from FlexiLynx.core.util.parallel import mlock
#</Imports

#> Header >/
__all__ = ('Manager',)

class Manager:
    '''Serves as a database and manager of `Module`s'''
    __slots__ = ('modules', '_lock')

    def __init__(self):
        self.modules = {}
        self._lock = RLock()

    @mlock
    def add_module(self, m: Module, *, override: bool = False):
        '''
            Adds a module to the manager
            Raises a `RuntimeError` if `m`'s ID is already registered by a different module,
                unless `override`
        '''
        prev = getattr(self.modules, m.id, None)
        if not ((prev is None) or (prev is m)):
            msg = (f'Conflicting module IDs: {m.id}', f'Previous: {prev.package.at.as_posix()}\nNew: {m.package.at.as_posix()}')
            if not override:
                exc = RuntimeError(msg[0])
                exc.add_note(msg[1])
                raise exc
            logger.warning(f'{msg[0]}\n{msg[1]}')
        self.modules[m.id] = m
    LOAD_BIAS = ('library', 'hybrid', 'override', 'implementation')
    def load_order(self, max_after_passes: int = 8, fail_on_unstable: bool = False) -> tuple[str, ...]:
        '''
            Generates a loading order from the modules
            This could take quite a long time with extreme amounts of modules
                that have many items in `.before` or `.after`
            Note that if a stable loading order is not found after `max_after_passes`,
                the unstable load-order is returned anyway, along with a logging message,
                unless `fail_on_unstable` is true, in which case a `RuntimeError` is raised
            The load order is first sorted by the type of module ("library", then "hybrid", then "override", then "implementation")
                and by the module's ID, and then the modules' `.before` and `.after` are satisfyed
        '''
        logger.verbose(f'Generating load-order for {len(self.modules)} module(s)...')
        logger.debug('sort with bias LOAD_BIAS based on type, then module ID')
        load_order = sorted(self.modules.keys(), key=lambda i: (self.LOAD_BIAS.index(self.modules[i].type), i))
        logger.debug('generate after-map')
        after = {}
        for i in load_order:
            m = self.modules[i]
            if m.after:
                for a in filter(self.modules.__contains__, m.after):
                    after.setdefault(a, set()).add(i)
            if m.before:
                after.setdefault(i, set()).update(filter(self.modules.__contains__, m.before))
        if not after:
            logger.verbose('Stable load-order found (no after-map; passes needed)')
            return tuple(load_order)
        for p in range(max_after_passes):
            logger.debug(f'pass {p+1}/{max_after_passes}: {len(after)} item(s) to reorder')
            dirty = False
            for id,afters in after.items():
                first = min(map(load_order.index, afters))
                try: idindex = load_order.index(id, first)
                except ValueError: continue
                dirty = True
                load_order.insert(first, load_order.pop(idindex))
            if not dirty:
                logger.verbose(f'Stable load-order found after {p+1} pass(es)')
                break
            if p: logger.debug(f'pass {p+1} changed--unstable')
        else:
            if dirty:
                logger.error(f'Could not find stable load-order after {max_after_passes} pass(es)!')
                if fail_on_unstable:
                    raise RuntimeError(f'Failed to find stable load-order after {max_after_passes} pass(es)')
        return tuple(load_order)
