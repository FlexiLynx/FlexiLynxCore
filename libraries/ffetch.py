#!/bin/python3

#> Imports
import typing
from http.client import HTTPResponse
from urllib import request as urlrequest
#</Imports

#> Header >/
__all__ = ('CachedHTTPResponse', 'hash_url', 'request')

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
    @property
    def url_hash(self) -> typing.Hashable:
        return hash_url(self.url)

cache = {}
def hash_url(url: str) -> typing.Hashable:
    '''Pre-hashes a `url` for placing in the cache dictionary'''
    return hash(url)

def request(url: str, *, timeout: int | None = None,
            read_from_cache: bool = True, add_to_cache: bool = True, return_as_cache: bool = True) -> CachedHTTPResponse | HTTPResponse:
    '''
        Requests data from the `url`, waiting for an (optional) `timeout` seconds, with caching capabilities:
            Reads data from a module-level cache if `read_from_cache` is true
            Writes data to the module-level cache if `add_to_cache` is true
        Returns a `CachedHTTPResponse`, unless `return_as_cache` is false, in which case an `HTTPResponse` is returned
            Note that an `AssertionError` is raised if attempting to read from / add to cache when `return_as_cache` is false
                (if assertions are disabled, raises a `ValueError` at the time of the read/add instead of before doing anything)
    '''
    if read_from_cache or add_to_cache:
        assert return_as_cache, 'Cannot read from or add to cache when return_as_cache is false'
        h = hash_url(url)
        if read_from_cache:
            if (c := cache.get(h, None)) is not None:
                if not return_as_cache:
                    raise ValueError('Cannot read CachedHTTPResponse from cache if return_as_cache is false')
                return c
    r = urlrequest.urlopen(url, timeout=timeout)
    if add_to_cache:
        if not return_as_cache:
            raise ValueError('Cannot add CachedHTTPResponse to cache if return_as_cache is false')
        r = CachedHTTPResponse(r)
        cache[h] = r
    return r
