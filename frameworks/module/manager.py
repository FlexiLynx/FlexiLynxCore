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
