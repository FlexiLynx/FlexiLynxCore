#!/bin/python3

'''Contains the `Artifact` class, see `help(Artifact)`'''

#> Imports
import typing
import hashlib
from dataclasses import dataclass

from FlexiLynx.core.util import base85
#</Imports

#> Header >/
__all__ = ('Artifact',)

@dataclass(slots=True, kw_only=True)
class Artifact:
    '''
        Represents a piece of downloadable data in a blueprint; usually a file
        `hashfn` is the hashing algorithm to use, whilst `hash` is the stored hash of the data
    '''
    url: str | None = None
    hash: bytes | str | None
    hashfn: typing.Literal[*hashlib.algorithms_guaranteed] = 'sha1'

    def hash_data(self, data: bytes | None = None) -> bytes:
        if data is None:
            data = self.data
            if data is None:
                raise TypeError('Cannot hash blank data (data was not provided and self.data is None)')
        return hashlib.new(self.hashfn, data).digest()
    def to_dict(self) -> dict:
        return {
            'url': self.url,
            'hash': f'{self.hashfn}:{"" if self.hash is None else base85.encode(self.hash)}',
        }
    @classmethod
    def from_dict(cls, d: dict) -> typing.Self:
        hsplit = d['hash'].split(':')
        return cls(url=d['url'], hash=base85.decode(hsplit[1]) if hsplit[1] else None, hashfn=hsplit[0])
