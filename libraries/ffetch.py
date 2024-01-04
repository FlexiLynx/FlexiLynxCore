#!/bin/python3

#> Imports
import typing
from http.client import HTTPResponse
from urllib import request as urlrequest
#</Imports

#> Header >/
__all__ = ('CachedHTTPResponse',
           'hash_url', 'pop_cache', 'cachedict_to_urldict',
           'request', 'fetch')

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
def pop_cache(item: str | CachedHTTPResponse | None = None, *, cache_dict: dict[typing.Hashable, CachedHTTPResponse] = cache,
              fail_on_missing: bool = True, dict_url_keys: bool = True) -> CachedHTTPResponse | dict[typing.Hashable, CachedHTTPResponse] | None:
    '''
        Removes entries from the cache in a variety of ways:
            Pops `item` from the cache if `item` is a string (corresponding to a URL) that is contained in the cache
                If the `item` is not in the cache, then throws `KeyError(item)` if `fail_on_missing`, otherwise returns `None`
            Pops `item.url_hash` from the cache if `item` is a `CachedHTTPResponse`
                If `item.url_hash` is not in the cache, then throws `KeyError(item)` if `fail_on_missing`, otherwise returns `None`
            Clears the cache and returns a copy of its previous state if `item` is `None`
                If `dict_url_keys` is true, then uses the values (`CachedHTTPResponse` instances) `url` attributes to return a dictionary of URLs and `CachedHTTPResponse`s,
                    otherwise returning a dictionary of URL hashes and `CachedHTTPResponse`s
        Throws `TypeError` if nothing can be done with `item`
    '''
    if url is None:
        popped = cachedict_to_urldict(cache_dict) if dict_url_keys else cache_dict.copy()
        cache_dict.clear()
    elif isinstance(item, str):
        popped = cache_dict.pop(hash_url(item), None)
    elif isinstance(item, CachedHTTPResponse):
        popped = cache_dict.pop(item.url_hash)
    else: raise TypeError(f'Cannot pop {item!r} from the cache')
    if fail_on_missing and (popped is None):
        raise KeyError(item)
    return popped
def cachedict_to_urldict(cache_dict: dict[typing.Hashable, CachedHTTPResponse] = cache) -> dict[str, CachedHTTPResponse]:
    '''Helper function to convert a dictionary of URLs and `CachedHTTPResponse`s from a dictionary of URL hashes and `CachedHTTPResponse`s'''
    return {c.url: c for c in cache_dict.values()}

def request(url: str, *, cache_dict: dict[typing.Hashable, CachedHTTPResponse] = cache,
            timeout: int | None = None,
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
            if (c := cache_dict.get(h, None)) is not None:
                if not return_as_cache:
                    raise ValueError('Cannot read CachedHTTPResponse from cache if return_as_cache is false')
                return c
    r = urlrequest.urlopen(url, timeout=timeout)
    if add_to_cache:
        if not return_as_cache:
            raise ValueError('Cannot add CachedHTTPResponse to cache if return_as_cache is false')
        r = CachedHTTPResponse(r)
        cache_dict[h] = r
    return r

def fetch(url: str, no_cache: bool = False, **kwargs) -> bytes:
    '''
        Fetches bytes from `url`, with optional caching features
        See `help(request())` for additional information and `kwargs`
            `no_cache=True` is a shortcut for `read_from_cache=False`, `add_to_cache=False`, and `return_as_cache=False`
    '''
    return request(url, **((
        {'read_from_cache': False, 'add_to_cache': False, 'return_as_cache': False} if no_cache else {})
        | kwargs)).read()
