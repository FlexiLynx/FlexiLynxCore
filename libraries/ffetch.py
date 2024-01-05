#!/bin/python3

#> Imports
import sys
import typing
import itertools
from enum import Enum
from dataclasses import dataclass
from http.client import HTTPResponse
from urllib import request as urlrequest
#</Imports

#> Header >/
__all__ = ('FLHTTPResponse',
           'hash_url', 'pop_cache', 'cachedict_to_urldict',
           'request', 'fetch', 'fetch_chunks',
           'FancyFetch', 'fancy_fetch')

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

    def calc_chunksize(self, chunks: int) -> int | None:
        '''
            Calculates how large each chunk should be to get `chunks` chunks from self
                Uses the expression `int((self.length / chunks) + 0.5) or self.length` to calculate chunk size
            If a `Content-Length` header wasn't sent (`self.length` is `None`), then returns `None`
        '''
        if self.length is None: return None
        return int((self.length / chunks) + 0.5) or self.length

    # override length
    @property
    def length(self) -> int | None:
        return int(cl) if (cl := self.headers.get('Content-Length')) is not None else None

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

def request(url: str | urlrequest.Request, *, timeout: int | None = None, user_agent: str = 'Mozilla/5.0',
            cache_dict: dict[typing.Hashable, FLHTTPResponse] = cache, read_from_cache: bool = True, add_to_cache: bool = True) -> FLHTTPResponse:
    '''
        Requests data from the `url`, waiting for an (optional) `timeout` seconds, with caching capabilities:
            Reads data from a module-level cache (or `cache_dict`) if `read_from_cache` is true
            Writes data to the module-level cache (or `cache_dict`) if `add_to_cache` is true
        `user_agent` is only set if `url` is a string and not a `urllib.request.Request`
    '''
    if read_from_cache or add_to_cache:
        h = hash_url(url.url if isinstance(url, urlrequest.Request) else url)
        if read_from_cache:
            if (c := cache_dict.get(h, None)) is not None:
                return c
    if isinstance(url, str):
        url = urlrequest.Request(url, headers={'User-Agent': user_agent})
    hr = FLHTTPResponse(urlrequest.urlopen(url, timeout=timeout))
    if add_to_cache: cache_dict[h] = hr
    return hr

def fetch(url: str | urlrequest.Request, no_cache: bool = False, **kwargs) -> bytes:
    '''
        Fetches bytes from `url`, with optional caching features
        See `help(request)` for additional information and `kwargs`
            `no_cache=True` is a shortcut for `read_from_cache=False` and `add_to_cache=False`
    '''
    return request(url, **(({'read_from_cache': False, 'add_to_cache': False} if no_cache else {}) | kwargs)).read()
def fetch_chunks(url: str | urlrequest.Request, chunk_size: int | None, chunk_count: int | None = None, *, chunk_cached: bool = True, no_cache: bool = False, add_to_cache: bool = False, **kwargs) -> typing.Iterator[bytes]:
    '''
        Fetches bytes in chunks of `chunk_size` byte(s) each
            If `chunk_count` is given, then `chunk_size` is set so that the amount of chunks is (roughly) equivelant to `chunk_count`
                The chunk size is calculated with `<response>.calc_chunksize(chunk_count)`, which (by default) runs `int((<response>.length / chunk_count) + 0.5) or <response>.length`
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
        chunk_size = hr.calc_chunksize(chunk_count) or chunk_size
        if chunk_size is None:
            raise ValueError(f'URL {url!r} did not provide a Content-Length header')
    elif chunk_size is None: raise TypeError('chunk_size may not be None if chunk_count is not provided')
    return hr.iter_chunks(chunk_size, chunk_cached=chunk_cached)

@dataclass(eq=False, kw_only=True, slots=True)
class FancyFetch:
    # Config
    file:                 typing.TextIO = sys.stderr
    do_line_clear:        bool = True
    line_clear_seq:       str = '\x1b[2K\r'
    line_end_char:        str = '\n'
    max_cache_size:       int = ((2**10)**2)//10 # one tenth of a MiB
    size_prefixes:        tuple[tuple[int, str], ...] = tuple((pfx, 1024**(mag)) for mag,pfx in enumerate(('b', 'kib', 'mib', 'gib'))) \
                                                        + tuple((pfx, 1000**(mag+1)) for mag,pfx in enumerate(('kb', 'mb', 'gb')))
    # Chunk config
    chunk_count:          int = 10
    no_chunk_size:        int = (2**10)**2 # one MiB
    chunk_size_fallback:  int = ((2**10)**2)//2 # half an MiB
    ## Format config
    ### Lines
    complete_line_fmt:    str = '{url}: downloaded {kib_fetched:.2G} KiB'
    cached_line_fmt:      str = '{url}: loaded {kib_total:.2G} KiB from cache'
    #### Size known
    ks_line_fmt:          str = '{url}: fetching {kib_total:.2G} KiB'
    ks_chunk_line_fmt:    str = '{url}: {complete:04.0%} <{bar_full}{bar_empty}>  {mib_fetched:.2G}/{mib_total:.2G} MiB (chunk {chunk_fetched} of {chunk_total})'
    #### Size unknown
    us_line_fmt:          str = '{url}: fetching up to {mib_total:.2G} MiB'
    us_line_exceeded_fmt: str = '{url}: read data exceeded {mib_total:.2G} MiB, swapping to chunked reading'
    us_chunk_line_fmt:    str = '{url}: {b_fetched} byte(s) fetched (chunk {chunk_fetched} of ?)'
    ### Symbols
    bar_chunk:            str = '#'
    bar_empty:            str = '-'
    ### URL config
    url_max_width:        int = 60
    url_trunc_txt:        str = '...'
    url_protocols:        dict = tuple({'http': '[ ]', 'https': '[S]', 'ftp': '[F]'}.items())
    url_protocol_unknown: str = '[?]'

    def fetch_known_size(self, config: dict, r: FLHTTPResponse):
        '''Fetches data of a known size, delegating to `chunked_fetch_known_size()` if the data is large enough'''
        staticfmt = self.static_format_map(config, r)
        if r.length > config['no_chunk_size']:
            return self.chunked_fetch_known_size(config, staticfmt, r)
        self.on_fetch_known_size(config, staticfmt, r)
        return r.read()
    def chunked_fetch_known_size(self, config: dict, staticfmt: dict, r: FLHTTPResponse) -> bytes:
        '''Fetches chunked data of a known size'''
        self.on_chunk_known_size(config, staticfmt, r, 0)
        for chunk,_ in enumerate(r.iter_chunks(r.calc_chunksize(config['chunk_count']))):
            self.on_chunk_known_size(config, staticfmt, r, chunk)
        return r.read()
    def fetch_unknown_size(self, config: dict, r: FLHTTPResponse) -> bytes:
        '''Fetches data of an unknown size, delegating to `chunked_fetch_unknown_size()` when the size reaches a certain threshold'''
        staticfmt = self.static_format_map(config, r)
        self.on_fetch_unknown_size(config, staticfmt)
        data = r.read()
        if r.completed: return data
        self.on_swap_unknown_size(config, staticfmt)
        return self.chunked_fetch_unknown_size(config, staticfmt, r)
    def chunked_fetch_unknown_size(self, config: dict, staticfmt: dict, r: FLHTTPResponse) -> bytes:
        '''Fetches chunked data of an unknown size'''
        self.on_chunk_unknown_size(config, staticfmt, r, 1)
        for chunk,_ in enumerate(r.iter_chunks(config['chunk_size_fallback'])):
            self.on_chunk_unknown_size(config, staticfmt, r, chunk+1)
        return r.read()

    def on_complete(self, config: dict, staticfmt: dict, r: FLHTTPResponse):
        '''Writes a message that the fetching has completed'''
        self.print_end(config, config['completed_line_fmt'].format_map(staticfmt | self.dynamic_format_map(config, r)), True)
    def on_fetch_known_size(self, config: dict, staticfmt: dict, r: FLHTTPResponse):
        '''Writes a message that unchunked data is being read of a known size'''
        self.print(config, config['ks_line_fmt'].format_map(staticfmt | self.dynamic_format_map(config, r)))
    def on_chunk_known_size(self, config: dict, staticfmt: dict, r: FLHTTPResponse, chunk: int):
        '''Writes a message for each read chunk of a known size'''
        self.print_clear(config, config['ks_chunk_line_fmt'].format_map(staticfmt | self.dynamic_format_map(config, r) | self.chunk_format_map(config, chunk)))
    def on_fetch_unknown_size(self, config: dict, staticfmt: dict, r: FLHTTPResponse):
        '''Writes a message that unchunked data is being read of an unknown size'''
        self.print_end(config, config['us_line_fmt'].format_map(staticfmt | self.dynamic_format_map(config, r)))
    def on_swap_unknown_size(self, config: dict, staticfmt: dict, r: FLHTTPResponse):
        '''Writes a message that enough data was read, with the total count being unknown, to swap to chunked mode'''
        self.print_end(config, config['us_line_exceeded_fmt'].format_map(staticfmt | self.dynamic_format_map(config, r)))
    def on_chunk_unknown_size(self, config: dict, staticfmt: dict):
        '''Writes a message for each read chunk of an unknown size'''
        self.print_clear(config, config['us_chunk_line_fmt'].format_map(staticfmt | self.dynamic_format_map(config, r) | self.chunk_format_map(config, chunk)))

    def print(self, config: dict, text: str):
        '''Called to print text without any end'''
        print(text, end=None, file=config['file'])
    def print_end(self, config: dict, text: str, prefix_end: bool = False):
        '''Called to print and add the line ending char (prints the line ending char before as well if `prefix_end` is true)'''
        if prefix_end: print(end=config['line_end_char'], file=config['file'])
        print(text, end=config['line_end_char'], file=config['file'])
    def print_clear(self, config: dict, text: str):
        '''Called to clear and reprint the current line'''
        config['file'].write(config['line_clear_seq'] if config['do_line_clear'] else config['line_end_char'])
        config['file'].flush()
        config['file'].write(text)
        config['file'].flush()

    def static_format_map(self, config: dict, r: FLHTTPResponse) -> dict:
        '''
            Converts a `FLHTTPResponse` into *most* of the format values used in line formats that should not change over time
                Does not include chunk-related format values
        '''
        return config | {
            'url': self.format_url(config, r.url),
        } | self.size_format_map(config, '_total', r.length or None)
    def chunk_format_map(self, config: dict, chunk: int, known_total: bool = True) -> dict:
        '''Returns a format map for chunk-related entries'''
        return {
            'chunk_fetched': chunk+1, 'chunk_total': config['chunk_count'] if known_total else None,
            'bar_full': config['bar_chunk'] * (chunk+1),
            'bar_empty': (config['bar_empty'] * (config['chunk_count']-chunk-1)) if known_total else None,
        }
    def dynamic_format_map(self, config: dict, r: FLHTTPResponse) -> dict:
        '''
            Converts a `FLHTTPResponse` into *most* of the format values used in line formats that change over time
                Does not include chunk-related format values
        '''
        return {
            'complete': (len(r.data or b'') / r.length) if r.length else '?',
        } | self.size_format_map(config, '_fetched', len(r.data or b''))
    def size_format_map(self, config: dict, suffix: str, size: int | None) -> dict:
        '''Returns a format map for sizes in various formats from a size (bytes)'''
        return {f'{pfx}{suffix}': size / div for pfx,div in config['size_prefixes']}
    def format_url(self, config: dict, url: str) -> str:
        '''Preprocesses a URL for `format_map()`'''
        prot,url = url.split('://', 1)
        url = f'{dict(config["url_protocols"]).get(prot, config["url_protocol_unknown"])}{url}'
        if len(url) > config['url_max_width']:
            return f'{url[:config["url_max_width"]-len(config["url_trunc_txt"])]}{config["url_trunc_txt"]}'
        return url

fancy_fetch = FancyFetch()
