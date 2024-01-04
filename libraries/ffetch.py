#!/bin/python3

#> Imports
import typing
import itertools
from enum import Enum
from http.client import HTTPResponse
from urllib import request as urlrequest
#</Imports

#> Header >/
__all__ = ('FLHTTPResponse',
           'hash_url', 'pop_cache', 'cachedict_to_urldict',
           'request', 'fetch', 'fetch_chunks')

class FLHTTPResponse:
    '''
        A wrapper around an `HTTPResponse` object that augments various facilities, offering:
         - Response caching
         - Iterable chunked reading
         - Various helpful properties

        Note that constructing this class leaves the original `HTTPResponse` in a dangerous state:
         - Reading in a `FLHTTPResponse` may break the original
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
    ChunkContinue = Enum('ChunkContinue', ('RAISE', 'CANCEL', 'BEGINNING', 'CONTINUE'))
    def iter_chunks(self, chunk_size: int, *, continue_whence: ChunkContinue = ChunkContinue.RAISE, chunk_cached: bool = False) -> typing.Generator[bytes, None, None]:
        '''
            Reads (and yields) the response body in chunks of `chunk_size` byte(s)

            If the data has already been cached, this function yields a single value containing the entire body
                If `chunk_cached` is true, then instead yields appropriately sized chunks of the cached data
            If a chunk read is already in progress, then the behavior depends on the value of `continue_whence`:
                `ChunkContinue.RAISE`: raises a `RuntimeError`
                `ChunkContinue.CANCEL`: yields nothing
                `ChunkContinue.BEGINNING`: yields already cached data, then yields newly read chunks
                    Yields a combination of already cached data and newly read chunks in the proper chunk size if `chunk_cached` is true, such that chunk size is consistent
                `ChunkContinue.CONTINUE`: ignores already cached data, only yields newly read chunks
                Any other value results in a `TypeError`
        '''
        if self.completed:
            if chunk_cached:
                yield from (bytes(chunk) for chunk in itertools.batched(self.data, chunksize))
            else:
                yield self.data
            return
        if self.chunk_read_in_progress:
            match continue_whence:
                case self.ChunkContinue.RAISE:
                    raise RuntimeError('Cannot iterate chunks while a chunk-read is already in progress and continue_whence is ChunkContinue.RAISE')
                case self.ChunkContinue.CANCEL: return
                case self.ChunkContinue.BEGINNING:
                    if chunk_cached:
                        remaining = self.data[:len(self.data) - (len(self.data) % chunk_size)]
                        yield from (bytes(chunk) for chunk in itertools.batched(self.data[:len(self.data)-len(remaining)], chunk_size))
                        yield bytes(remaining) + self.read(remainder)
                    else: yield bytes(self.data)
                case self.ChunkContinue.CONTINUE: pass
                case _: raise TypeError(f'Illegal value for continue_whence: {continue_whence!r}; expected ChunkContinue')
        while not self.completed:
            yield self.read(chunk_size)

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
def pop_cache(item: str | FLHTTPResponse | None = None, *, cache_dict: dict[typing.Hashable, FLHTTPResponse] = cache,
              fail_on_missing: bool = True, dict_url_keys: bool = True) -> FLHTTPResponse | dict[typing.Hashable, FLHTTPResponse] | None:
    '''
        Removes entries from the cache in a variety of ways:
            Pops `item` from the cache if `item` is a string (corresponding to a URL) that is contained in the cache
                If the `item` is not in the cache, then throws `KeyError(item)` if `fail_on_missing`, otherwise returns `None`
            Pops `item.url_hash` from the cache if `item` is a `FLHTTPResponse`
                If `item.url_hash` is not in the cache, then throws `KeyError(item)` if `fail_on_missing`, otherwise returns `None`
            Clears the cache and returns a copy of its previous state if `item` is `None`
                If `dict_url_keys` is true, then uses the values (`FLHTTPResponse` instances) `url` attributes to return a dictionary of URLs and `FLHTTPResponse`s,
                    otherwise returning a dictionary of URL hashes and `FLHTTPResponse`s
        Throws `TypeError` if nothing can be done with `item`
    '''
    if item is None:
        popped = cachedict_to_urldict(cache_dict) if dict_url_keys else cache_dict.copy()
        cache_dict.clear()
    elif isinstance(item, str):
        popped = cache_dict.pop(hash_url(item), None)
    elif isinstance(item, FLHTTPResponse):
        popped = cache_dict.pop(item.url_hash)
    else: raise TypeError(f'Cannot pop {item!r} from the cache')
    if fail_on_missing and (popped is None):
        raise KeyError(item)
    return popped
def cachedict_to_urldict(cache_dict: dict[typing.Hashable, ] = cache) -> dict[str, FLHTTPResponse]:
    '''Helper function to convert a dictionary of URLs and `FLHTTPResponse`s from a dictionary of URL hashes and `FLHTTPResponse`s'''
    return {c.url: c for c in cache_dict.values()}

def request(url: str, *, timeout: int | None = None,
            cache_dict: dict[typing.Hashable, FLHTTPResponse] = cache, read_from_cache: bool = True, add_to_cache: bool = True) -> FLHTTPResponse:
    '''
        Requests data from the `url`, waiting for an (optional) `timeout` seconds, with caching capabilities:
            Reads data from a module-level cache (or `cache_dict`) if `read_from_cache` is true
            Writes data to the module-level cache (or `cache_dict`) if `add_to_cache` is true
    '''
    if read_from_cache or add_to_cache:
        h = hash_url(url)
        if read_from_cache:
            if (c := cache_dict.get(h, None)) is not None:
                return c
    hr = FLHTTPResponse(urlrequest.urlopen(url, timeout=timeout))
    if add_to_cache: cache_dict[h] = hr
    return hr

def fetch(url: str, no_cache: bool = False, **kwargs) -> bytes:
    '''
        Fetches bytes from `url`, with optional caching features
        See `help(request)` for additional information and `kwargs`
            `no_cache=True` is a shortcut for `read_from_cache=False` and `add_to_cache=False`
    '''
    return request(url, **(({'read_from_cache': False, 'add_to_cache': False} if no_cache else {}) | kwargs)).read()
def fetch_chunks(url: str, chunk_size: int | None, chunk_count: int | None = None, *, chunk_cached: bool = True, no_cache: bool = False, add_to_cache: bool = False, **kwargs) -> typing.Iterator[bytes]:
    '''
        Fetches bytes in chunks of `chunk_size` byte(s) each
            If `chunk_count` is given, then `chunk_size` is set so that the amount of chunks is (roughly) equivelant to `chunk_count`
                The chunk size is calculated with `int((FLHTTPResponse.length / chunk_count) + 0.5)`
                `chunk_size` is used as a fallback in case the request has no `Content-Length` header
                `chunk_size` can be set to `None` to raise a `ValueError` when the `Content-Length` header is missing (`chunk_size` may only be `None` if `chunk_count` is provided)
        See `help(request)` for additional information and `kwargs`
            `no_cache=True` is a shortcut for `read_from_cache=False` and `add_to_cache=False`
            Differing from `request()`, `add_to_cache` is false by default in this function, as chunk-reading is usually used for larger files
                `read_from_cache` is still true by default
        If `chunk_cached` is true, then cached values will be split into chunks
    '''
    hr = request(url, **(({'add_to_cache': False, 'read_from_cache': False}
                          if no_cache else {'add_to_cache': add_to_cache}) | kwargs))
    if chunk_count is not None:
        if hr.length is not None:
            chunk_size = int((hr.length / chunk_count) + 0.5)
        elif chunk_size is None:
            raise ValueError(f'URL {url!r} did not provide a Content-Length header')
    elif chunk_size is None: raise TypeError('chunk_size may not be None if chunk_count is not provided')
    return hr.iter_chunks(chunk_size, chunk_cached=chunk_cached)
