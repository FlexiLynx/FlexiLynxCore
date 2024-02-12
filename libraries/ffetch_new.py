#!/bin/python3

#> Imports
import typing
import threading
import itertools
from enum import Enum
from collections import deque
from queue import SimpleQueue
from types import SimpleNamespace
from urllib import request as urlrequest
from http.client import HTTPResponse, HTTPMessage
#</Imports

#> Header >/
__all__ = ('FlexiLynxHTTPResponse', 'cache', 'request', 'fetch', 'fetch_chunked', 'URL', 'fetchx')

class FlexiLynxHTTPResponse:
    '''
        A wrapper around an `HTTPResponse` object that augments various facilities, offering:
         - Response caching
         - Iterable chunked reading
         - Various helpful properties
        Note that the original `HTTPResponse` object should *never* be used again; it will certainly cause problems both ways
    '''
    __slots__ = ('url', 'data', '_res', '_lock')

    def __init__(self, res: HTTPResponse, url: str | None = None):
        if getattr(res, '_flhhtpresponse_owned', False):
            raise TypeError('res is already owned by a FlexiLynxHTTPResponse and SHOULD NOT BE USED!!!')
        res._flhhtpresponse_owned = True
        self._res = res
        self._lock = threading.RLock()
        self.url = res.url if url is None else url
        self.data = None

    def __del__(self):
        self.close()
    def close(self):
        '''
            Closes the `FlexiLynxHTTPResponse`:
            - Closes the underlying `HTTPResponse`, then deletes it
            - Deletes `data`
        '''
        self._res.close()
        del self._res
        del self.data

    Continue = Enum('Continue', ('RAISE', 'CANCEL', 'BEGINNING', 'BEGINNING_CONSISTENT', 'CONTINUE'))
    def read(self, amt: int | None = None, *, whence: Continue = Continue.CONTINUE) -> bytes | None:
        '''
            Read and return the response body, or up to the next `amt` bytes
            If a read has already been completed, then returns the *entirety* of `self.data`
                This means that, if data has been cached, read will *always* return the entire data, not just `amt`
            If a chunk read is already in progress, then the behavior of `whence` decides what happens:
                `Continue.RAISE`: raises a `RuntimeError`
                `Continue.CANCEL`: returns `None`
                `Continue.BEGINNING`: returns `self.data` along with (up to) `amt` read bytes
                `Continue.BEGINNING_CONSISTENT`: returns up to `amt` bytes from `self.data`, reading more as necessary
                    If the cached data is larger than `amt`, then all of the cached data is returned and nothing is read
                    Acts the same as `Continue.BEGINNING` if `amt` is `None`
                `Continue.CONTINUE`: returns up to `amt` bytes read from the underlying response, similar to how streams work by default
            Note that this function is locked, along with `chunks()`. As such, it may deadlock whilst another read is in progress in a different thread
        '''
        with self._lock:
            ds = self.data_stat()
            # If closed
            if ds is self.DataStat.CLOSED:
                raise TypeError('This response is closed')
            # If complete
            if ds is self.DataStat.COMPLETE:
                return self.data
            # Not yet started
            if ds is self.DataStat.UNSTARTED:
                self.data = self._res.read() if (amt is None) else deque(self._res.read(amt))
                if self._res.isclosed(): self.data = bytes(self.data)
                return bytes(self.data)
            # Incomplete (the fun one)
            if whence is self.Continue.RAISE: raise RuntimeError('Refusing to resume a read when whence is Continue.RAISE')
            if whence is self.Continue.CANCEL: return None
            if amt is None:
                chunk = self._res.read()
            else:
                if whence is self.Continue.BEGINNING_CONSISTENT:
                    self.data.extend(self._res.read(max(amt - len(self.data), 0)))
                    return bytes(self.data) # beginning_consistent where amt is None
                chunk = self._res.read(amt)
            self.data.extend(chunk)
            if self._res.isclosed(): self.data = bytes(self.data)
            if whence is self.Continue.CONTINUE: return chunk # continue
            return bytes(self.data) # beginning
                
    def chunks(self, csize: int, *, whence_chunk: Continue = Continue.RAISE, read_full_cache: bool = False, chunk_cached: bool = False) -> typing.Generator[bytes, None, None]:
        '''
            Reads (and yields) the response body in chunks of `csize` byte(s)
            If the data has already been cached, then raises a `RuntimeError` if `read_full_cache` is false, otherwise
                yields a single `bytes`, or returns an iterator of `bytes` split into `csize` if `chunk_cached` is true
            If a chunk read is already in progress, then the behavior depends on the value of `whence_chunk`:
                `Continue.RAISE`: raises a `RuntimeError`
                `Continue.CANCEL`: yields nothing
                `Continue.BEGINNING`: yields already cached data, then yields newly read chunks
                    Yields a combination of already cached data and newly read chunks in the proper chunk size if `chunk_cached` is true, such that chunk size is consistent
                    `Continue.BEGINNING_CONSISTENT` behaves the same
                `Continue.CONTINUE`: ignores already cached data, only yields newly read chunks
                Any other value results in a `TypeError`
            Note that this function is locked, along with `read()`. As such, it may deadlock whilst another read is in progress in a different thread
        '''
        with self._lock:
            ds = self.data_stat()
            # If closed
            if ds is self.DataStat.CLOSED:
                raise TypeError('This response is closed')
            # If complete
            if ds is self.DataStat.COMPLETE:
                if not read_full_cache:
                    raise RuntimeError('Refusing to read full cache when read_full_cache is false')
                if chunk_cached:
                    yield from map(bytes, itertools.batched(self.data, csize))
                else:
                    yield self.data
                return
            # If in progress
            if ds is self.DataStat.INCOMPLETE:
                match whence_chunk:
                    case self.Continue.RAISE:
                        raise RuntimeError('Refused to continue reading chunks when whence_chunk is Continue.RAISE')
                    case self.Continue.CANCEL: return
                    case self.Continue.BEGINNING | self.Continue.BEGINNING_CONSISTENT:
                        if chunk_cached:
                            # Get data that doesn't fit cleanly into a chunk
                            remains = bytes(self.data[:len(self.data) - (len(self.data) % csize)])
                            # Chunk up all of the data except for the data from above
                            yield from map(bytes, itertools.batched(self.data[:len(self.data)-len(remains)], csize))
                            # Read enough data to finalize the remaining data from above
                            yield remains + self.read(csize)
                        else:
                            # Just yield the cached data
                            yield bytes(self.data)
            # Read the rest (if in progress) or read the entirety (if not) until everything's been read
            while (self.data_stat() is self.DataStat.INCOMPLETE) or (self.data_stat() is self.DataStat.UNSTARTED):
                yield self.read(csize)

    def _DataStatResType(name: str) -> type[int]:
        def __bool__(self):
            return self == 3
        return type(name, (int,), {'__slots__': (), '__bool__': __bool__})
    _DataStatRes = _DataStatResType('_DataStatRes')
    DataStat = Enum('DataStat', ('UNSTARTED', 'INCOMPLETE', 'COMPLETE', 'CLOSED'), type=_DataStatRes)
    def data_stat(self) -> DataStat:
        '''
            `DataStat.UNSTARTED`: Reading has not been started yet; boolean-evaluates to `False`
            `DataStat.INCOMPLETE`: Reading has been started but was not completed; boolean-evaluates to `False`
            `DataStat.COMPLETE`: Reading has been started and completed, all data is available; boolean-evaluates to `True`
            `DataStat.CLOSED`: This instance has been closed (usually via `.close()`), so the data was deleted; boolean-evaluates to `False`
                Could also be returned if the instance was improperly mutated (deleting `.data`) or improperly initialized (`.data` was never set)
            Will raise a `TypeError` if `data` is not a known type
        '''
        if not hasattr(self, 'data'): return self.DataStat.CLOSED
        if self.data is None: return self.DataStat.UNSTARTED
        elif isinstance(self.data, deque): return self.DataStat.INCOMPLETE
        elif isinstance(self.data, bytes): return self.DataStat.COMPLETE
        else: raise TypeError('data is set, but is an unknown type: expect None, deque, or bytes, not `{type(self.data).__name__}`')

    @property
    def headers(self) -> HTTPMessage:
        return self._res.headers

    def rlength(self) -> int | None:
        '''"reported" length from Content-Length header; could be `None`'''
        if self.data_stat() is self.DataStat.CLOSED: raise TypeError('Cannot get reported length of a closed response')
        return int(cl) if (cl := self.headers.get('Content-Length')) is not None else None
    def clength(self) -> int:
        '''"cached" length, AKA size of `.data` (which may not be final)'''
        if self.data_stat() is self.DataStat.CLOSED: raise TypeError('Cannot get cached length of a closed response')
        return 0 if self.data is None else len(self.data)
    def length(self) -> int:
        '''Returns the length of `.data`, similar to `clength()`, but raises `RuntimeError` when `.data` is not finalized (`.data != DataStat.COMPLETE`)'''
        ds = self.data_stat()
        if ds is self.DataStat.CLOSED: raise TypeError('Cannot get length of a closed response')
        if ds is self.DataStat.COMPLETE: return len(self.data)
        raise RuntimeError('Cannot get length of an incomplete response (maybe you need `.clength()`?)')

# Requesting & cache
cache = {}
def request(url: str, *, timeout: int | None = None, user_agent: str = 'Mozilla/5.0',
            cache_dict: dict[int, FlexiLynxHTTPResponse] = cache, read_cache: bool = True, write_cache: bool = True) -> FlexiLynxHTTPResponse:
    '''
        Requests data from `url`, constructing a `FlexiLynxHTTPResponse`
            Reads data from `cache` (or `cache_dict`, if given) if present when `read_cache` is true
            Adds data from `cache` (or `cache_dict`, if given) when `write_cache` is true
                Setting `write_cache` to true whilst `read_cache` to false is a good way to refresh a cached entry
    '''
    if read_cache or write_cache:
        hurl = URL.hash(url)
        if read_cache and ((c := cache_dict.get(hurl, None)) is not None):
            return c
    hr = FlexiLynxHTTPResponse(
        urlrequest.urlopen(
            urlrequest.Request(url, headers={'User-Agent': user_agent}), timeout=timeout),
        url)
    if write_cache:
        cache_dict[hurl] = hr
    return hr

# Fetching
def fetch(url: str, no_cache: bool = False, **kwargs) -> bytes:
    '''
        Something of a convenience wrapper for `request()`, but returns `bytes` instead of a `FlexiLynxHTTPResponse`
        See `help(request)` for `kwargs`
            `no_cache` simply sets `read_cache` and `write_cache` to `False` when given
    '''
    return request(url, **(({'read_cache': False, 'write_cache': False} if no_cache else {}) | kwargs)).read()
def fetch_chunked(url: str, csize: int, *, chunk_cached: bool = True, no_cache: bool = True, write_cache: bool = False, **kwargs) -> typing.Generator[bytes, None, None]:
    '''
        Similar to `fetch()` (with similar parameters), but yields chunks of bytes of (up to) `csize`
            The `chunk_cached` parameter is passed to `FlexiLynxHTTPResponse.chunks()`
    '''
    return (request(url, **(({'read_cache': False, 'write_cache': False}
                            if no_cache else {'write_cache': write_cache}) | kwargs))
            ).chunks(csize, read_full_cache=True, chunk_cached=chunk_cached, whence_chunk=FlexiLynxHTTPResponse.Continue.BEGINNING)

# URL manipulation
class URL:
    '''Functions for manipulating URLs'''
    # Class junk
    __slots__ = ()
    __new__ = None
    # Functions
    @staticmethod
    def hash(url: str) -> int:
        '''
            Hashes a `url` for caching and other purposes
                Uses Python's builtin `hash()`
        '''
        return hash(url)
    ## URL mangling
    @staticmethod
    def _mangle_cut(url: list[str], to: typing.Literal[-1, 0, 1] = 0) -> tuple[str, str]:
        return (url.pop(0) if ((to == -1) or (to == 0)) else '',
                url.pop(-1) if ((to == 1) or (to == 0)) and url else '')
    @classmethod
    def _mangle_cut_size(cls, url: list[str], size: int, dsize: int, reverse: bool) -> tuple[list[str], list[str]]:
        a = []; b = []
        ac = bc = True
        if reverse: url.reverse()
        while url and (ac or bc):
            if ac:
                if len(url[0]) > size: ac = False
                else:
                    a.append(url.pop(0))
                    size -= len(a[0]) + 1
            if not url: break
            if bc:
                if len(url[-1]) > size: bc = False
                else:
                    b.insert(0, url.pop(-1))
                    size -= len(b[-1]) + 1
        if reverse:
            a.reverse(); b.reverse()
            return (b, a)
        return (a, b)
    @classmethod
    def _mangle(cls, url: str, width: int, delim: str,
                shorten_protocol: bool, protocol_fmt: str, protocol_split: str, protocol_join: str, protocol_map: dict[str | None, str], protocol_unknown: str,
                cut_url: bool, cut_txt: str, cut_delim_txt: bool, cut_to: typing.Literal[-1, 0, 1], cut_reverse: bool, cut_aggressive: bool, cut_aggro_bias: int | None) -> tuple[str, ...]:
        # Protocol mangling
        if shorten_protocol:
            if protocol_split not in url:
                prot,url = None, url
            else:
                prot,url = url.split(protocol_split, 1)
            prefix = f'{protocol_fmt.format(protocol_map.get(prot.lower(), protocol_unknown))}{protocol_join}'
        else: prefix = ''
        # Exit if we don't need to split, otherwise split
        if not cut_url:
            return (prefix, url)
        url = url.split(delim)
        url = list(filter(None, url)) # remove empty entries
        # Cutting
        ## Pre-cutting work
        target = width - len(prefix)
        if (not cut_url) or (len(
            durl := delim.join(url)) <= (
            target := width - len(prefix))):
            return (prefix, durl)
        assert target > 0, f'Length of prefix {prefix!r} exceeds target width {width!r}'
        if cut_to not in {-1, 0, 1}:
            raise TypeError(f'Illegal value for parameter "cut_to": {cut_to!r}')
        ## Cut off start and/or end
        start,end = cls._mangle_cut(url, cut_to)
        ## Cut to size
        url = cut_txt.join(map(delim.join, cls._mangle_cut_size(url, target - sum(map(len, url)) - len(cut_txt), len(delim), cut_reverse)))
        ## Aggressive cut
        ### NOT IMPLEMENTED ###
        # Return
        return (prefix, start, url, end)
    @classmethod
    def mangle(cls, url: str, width: int = 60, delim: str = '/', *,
               # Protocol options
               shorten_protocol: bool = True, protocol_fmt: str = '[{}]', protocol_split: str = '://', protocol_join: str = ' ',
               protocol_map: dict[str | None, str] = {'http': ' ', 'https': 'S', 'ftp': 'F'}, protocol_unknown: str = '?',
               # Cutting options
               cut_url: bool = True, cut_txt: str = '/.../', cut_delim_txt: bool = False, cut_to: typing.Literal[-1, 0, 1] = 0, cut_reverse: bool = True,
               cut_aggressive: bool = True, cut_aggro_bias: int | None = -20) -> str:
        '''
            Tries its very best to make `url` take up at most `width` characters
                Used for display/formatting purposes (the resulting URL is not usually valid)
            If `shorten_protocol` is false, then all `protocol_...` arguments are ignored, and if `cut_url` is false, then the same for all `cut_...` arguments
            `cut_to`:
              - `-1`: Cut from the "start", try to keep the domain name
              - `0`: Cut from the "middle", try to keep both the domain name and last part of the url
              - `1`: Cut from the "end", try to keep the last part of the URL
                Anything else raises a `TypeError`
            `cut_aggressive` will allow the domain name and the last part of the URL to be truncated if cutting the middle doesn't remove enough
                `cut_aggro_bias`:
                  - `-x`: Keep (up to) `x` characters of the last part, then keep as much of the first part as possible
                  - `0` or `None`: Equally truncate the first and last parts
                  - `x`: Keep (up to) `x` characters of the first part, then keep as much of the last part as possible
        '''
        pre,*url = cls._mangle(
            url, width, delim,
            shorten_protocol, protocol_fmt, protocol_split, protocol_join, protocol_map, protocol_unknown,
            cut_url, cut_txt, cut_delim_txt, cut_to, cut_reverse, cut_aggressive, cut_aggro_bias,
        )
        return f'{pre}{delim.join((p.strip(delim) for p in url))}'

# Fancy fetching
def _fetchx_aiter_on(h: int, flhr: FlexiLynxHTTPResponse, q: SimpleQueue, csize: int):
    for _ in flhr.chunks(csize): q.put(h)
def _fetchx_update(request: int | None, requests: list[int], requestsmap: dict[int, FlexiLynxHTTPResponse], namemap: dict[int, str]) -> tuple[str]:
    texts = []
    if request is not None:
        if requestsmap[request].data_stat() is requestsmap[request].DataStat.COMPLETE:
            if request in requests:
                requests.remove(request)
            texts.append(f'X {namemap[request]} completed as {requestsmap[request].length()} byte(s)')
    for r in requests:
        texts.append(f'{"*" if r == request else " "} {namemap[r]} {requestsmap[r].clength()}/{requestsmap[r].rlength() or "?"} byte(s)')
    return tuple(texts)
def _fetchx_runrun(csize: int | None, requestsmap: dict[int, FlexiLynxHTTPResponse], requests: list[int], statuses: dict[int, int], fullscreen: bool, **mangle_args):
    for r in requests: print(f'Waiting: {r}', flush=True)
    q = SimpleQueue()
    ns = {h: URL.mangle(flhr.url, **mangle_args) for h,flhr in requestsmap.items()}
    ts = {h: threading.Thread(target=_fetchx_aiter_on, args=(h, flhr, q, csize), daemon=True) for h,flhr in requestsmap.items()}
    print('\x1b[2J\x1b[H' if fullscreen else f'\x1b[{len(requests)}F', end='', flush=True)
    for h in requests:
        print(f'\x1b[2K\rStarting: {h} -> {ns[h]}', flush=True)
        ts[h].start()
    while any(map(threading.Thread.is_alive, ts.values())):
        tt = _fetchx_update(q.get(), requests, requestsmap, ns)
        print(f'\x1b[{len(tt)}F', end='', flush=True)
        for t in tt:
            print(f'\x1b[2K\r{t}', flush=True)
        #print(f'\x1b[{len(t)}F\x1b[K{"\n\x1b[K".join(t)}', flush=True)

def fetchx(*urls: tuple[str], csize: int | None = 128*1024, cache_limit_kib: int = 512, unknown_chunk_limit_kib: int = 512,
           target_cache: dict[int, FlexiLynxHTTPResponse] = cache, request_kwargs: dict[str, typing.Any] = {}, alt_buff: bool = False, **mangle_args):
    # Copy cache target
    cache_dict = target_cache.copy()
    # Generate FlexiLynxHTTPResponses and tasks
    requestsmap = {URL.hash(url): request(url, cache_dict=cache_dict, **request_kwargs) for url in urls}
    requests = list(requestsmap.keys())
    statuses = dict.fromkeys(requests, 0)
    # Main event loop
    stored_e = None
    if alt_buff: print('\x1b[?1049h', end='', flush=True)
    try:
        _fetchx_runrun(csize, requestsmap, requests, statuses, fullscreen=alt_buff)
    except BaseException as e: stored_e = e
    finally:
        if alt_buff: print('\x1b[?1049l', end='', flush=True)
    if stored_e is not None: raise stored_e
    # Finalize cache
    noadd = {h: cache_dict[h] for h,flhr in requestsmap.items() if flhr.length() >= (cache_limit_kib * 1024)}
    target_cache |= {h: cache_dict[h] for h in (cache_dict.keys()-noadd.keys())}
    for flhr in noadd.values(): flhr.close()
