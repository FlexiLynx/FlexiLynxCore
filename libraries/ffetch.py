#!/bin/python3

#> Imports
import typing
from http.client import HTTPResponse
#</Imports

#> Header >/
__all__ = ('CachedHTTPResponse',)

class CachedHTTPResponse:
    '''
        A wrapper around an `HTTPResponse` object that caches values, as well as providing some helper properties

        Note that constructing this class leaves the original `HTTPResponse` in a dangerous state:
         - Reading in a `CachedHTTPResponse` may break the original
         - Reading in the original *will* break this class
    '''
    __slots__ = ('data', 'original')

    def __init__(self, original: HTTPResponse):
        self.data = None
        self.original = original
    def __getattr__(self, attr: str) -> typing.Any:
        return self.original.__getattribute__(attr)

    def read(self, amt: int | None = None) -> bytes:
        '''
            Read and return the response body, or up to the next `amt` bytes, caching the response in `self.data`
            If a read has already been completed, then returns the *entirety* of `self.data`
                This means that, if data has been cached, `read` will *always* return the entire data, not just `amt`
            If a chunk read is in progress (check with `chunk_read_in_progress`), then a `read()` will return the rest of the data
        '''
        if self.completed: return self.data
        chunk = None
        if amt is None: # read all
            if self.chunk_read_in_progress: # read the rest into a chunk
                chunk = self.original.read()
            else:
                self.data = self.original.read()
        else: # read chunk
            if not self.chunk_read_in_progress:
                self.data = bytearray()
            chunk = self.original.read(amt)
        if chunk is None: return self.data
        self.data.extend(chunk)
        if self.completed:
            self.data = bytes(self.data)
        return chunk

    @property
    def completed(self) -> bool:
        return self.isclosed()
    @property
    def has_read(self) -> bool:
        if self.chunk_read_in_progress:
            raise RuntimeError('Cannot read property "has_read" when a chunk-read is partially complete')
        return self.data is not None
    @property
    def chunk_read_in_progress(self) -> bool:
        return isinstance(self.data, bytearray)
