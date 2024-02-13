#!/bin/python3

'''A collection of functions that were commonly created as lambdas'''

#> Imports

#</Imports

#> Header >/
__all__ = ('noop',)

def noop(*args, **kwargs) -> None:
    '''Takes everything and returns nothing (`None`)'''
    return None
