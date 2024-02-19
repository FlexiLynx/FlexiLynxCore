#!/bin/python3

'''...'''

#> Imports
import typing
from pathlib import Path
from dataclasses import dataclass, is_dataclass

from .artifact import Artifact
#</Imports

#> Header >/
__all__ = ('part_as_dict', 'AuthorPart', 'MetadataPart', 'ContentPart')

# Functions
def part_as_dict(part: object) -> dict:
    if hasattr(part, 'to_dict'):
        return part.to_dict()
    data = {}
    for f,v in ((f,getattr(part,f)) for f in part.__dataclass_fields__.keys()):
        data[f] = part_as_dict(v) if is_dataclass(v) else v
    return data
def part_from_dict(part: type, data: dict) -> dict:
    return part.from_dict(data) if hasattr(part, 'from_dict') else part(**data)

# Classes
_dc = dataclass(slots=True, kw_only=True)

@_dc
class AuthorPart:
    '''Contains the name and (optionally) contact information of the pack's creator'''
    name: str
    contact: str | None = None
@_dc
class MetadataPart:
    '''Contains metadata about the blueprint, such as its name and description'''
    name: str
    desc: str | None = None
    version: str | None = None
    author: AuthorPart | dict

    def __post_init__(self):
        if isinstance(self.author, dict):
            self.author = AuthorPart(**self.author)

@_dc
class ContentPart:
    '''
        Contains the files that make up the blueprint's content
        `url` serves two purposes:
            When an `Artifact` contains no `url`, it is used as the default
            If an `Artifact`'s `url` starts with a `/`, it is treated as relative to
                the containing `ContentPart`'s `url`
    '''
    url: str | None = None
    manifest: dict[Path | str, Artifact | dict]

    def __post_init__(self):
        # Init subvals
        for k,v in tuple(self.manifest.items()):
            if isinstance(v, dict):
                self.manifest[k] = Artifact(**v)
            if isinstance(k, str):
                self.manifest[Path(k)] = self.manifest[k]
                del self.manifest[k]

    def urlof(self, of: str) -> str | None:
        '''Returns the URL of a contained artifact, resolving special cases specified in `help(ContentPart)`'''
        url = self.manifest[of].url
        if url is None: return self.url
        if url.startswith('/'):
            if self.url is None:
                raise ValueError(f'Cannot resolve relative URL {url!r} when self.url is None')
            return f'{self.url.rstrip("/")}{url}'
        return url
