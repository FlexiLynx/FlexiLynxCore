#!/bin/python3

'''Utilities for working with and generating regular expressions'''

#> Imports
import re
import typing

from ..seqtool import sequential
#</Imports

#> Header >/
__all__ = ('ichar_patt', 'char_patt')

def ichar_patt(chars: str) -> typing.Iterator[str]:
    '''
        Converts a string of characters into a more compact set of regular expressions that matches them
            Yield a series of strings for each group of characters (could be a single char or a range)
    '''
    for seq in filter(None, (bytes(seq).decode() for seq in sequential(map(ord, chars)))):
        if len(seq) == 1: yield re.escape(seq[0]) # one single character
        elif len(seq) == 2: yield re.escape(''.join(seq))
        else: yield f'{re.escape(seq[0])}-{re.escape(seq[-1])}'
def char_patt(chars: str) -> str:
    '''
        Converts a string of characters into a more compact regular expressions that matches them
        Returns a string instead of a `re.Pattern` to prevent wasting time unnecessarily recompiling it if its a part of a larger pattern
    '''
    return ''.join(ichar_patt(chars))
