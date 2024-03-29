#!/bin/python3

#> Imports
import io
import lzma
import typing
import threading
from enum import Enum
from queue import SimpleQueue
from http.client import HTTPResponse, HTTPMessage
from urllib.request import urlopen, Request

from .typing import Protocol
from .parallel import mlock
#</Imports

#> Header >/
__all__ = ('URL', 'HTTPResponseCacher', 'request', 'fetch', 'fetch_chunked', 'fetchx', 'fetch1')

# URL manipulation
class URL:
    '''Functions for manipulating URLs'''
    __slots__ = ()
    __new__ = NotImplemented
    # Functions
    @staticmethod
    def hash(url: str) -> int:
        '''Hashes `url` for caching'''
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
                cut_url: bool, cut_txt: str, cut_delim_txt: bool, cut_to: typing.Literal[-1, 0, 1], cut_reverse: bool) -> tuple[str, ...]:
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
        # Return
        return (prefix, start, url, end)
    @classmethod
    def mangle(cls, url: str, width: int = 60, delim: str = '/', *,
               # Protocol options
               shorten_protocol: bool = True, protocol_fmt: str = '[{}]', protocol_split: str = '://', protocol_join: str = ' ',
               protocol_map: dict[str | None, str] = {'http': ' ', 'https': 'S', 'ftp': 'F'}, protocol_unknown: str = '?',
               # Cutting options
               cut_url: bool = True, cut_txt: str = '/.../', cut_delim_txt: bool = False, cut_to: typing.Literal[-1, 0, 1] = 0, cut_reverse: bool = True) -> str:
        '''
            Tries its very best to make `url` take up at most `width` characters
                Used for display/formatting purposes (the resulting URL is not usually valid)
            If `shorten_protocol` is false, then all `protocol_...` arguments are ignored, and if `cut_url` is false, then the same for all `cut_...` arguments
            `cut_to`:
              - `-1`: Cut from the "start", try to keep the domain name
              - `0`: Cut from the "middle", try to keep both the domain name and last part of the url
              - `1`: Cut from the "end", try to keep the last part of the URL
                Anything else raises a `TypeError`
        '''
        pre,*url = cls._mangle(
            url, width, delim,
            shorten_protocol, protocol_fmt, protocol_split, protocol_join, protocol_map, protocol_unknown,
            cut_url, cut_txt, cut_delim_txt, cut_to, cut_reverse,
        )
        return f'{pre}{delim.join((p.strip(delim) for p in url))}'

# Requesting
class HTTPResponseCacher:
    '''
        A wrapper around an `HTTPResponse` object that augments various facilities, offering:
         - Response caching
         - Iterable chunked reading
         - Various helpful properties
        Note that the original `HTTPResponse` object should *never* be used again; it will certainly cause problems both ways
    '''
    __slots__ = ('url', '_res', '_lock', '_rlock', '_data', '_len', '_comp', '_dcomp')

    _Compressor = Protocol('Compressor', 'Supported compression objects', compress=typing.Callable[[bytes], bytes], flush=typing.Callable[[], bytes])
    def __init__(self, res: HTTPResponse, url: str | None = None, *, compressor: _Compressor | None = None, decompressor: typing.Callable[[bytes], bytes] = lzma.decompress):
        if getattr(res, '_cached_owned', False):
            raise TypeError('res is already owned')
        res._cached_owned = True
        self._res = res
        self._lock = threading.RLock()
        self._rlock = threading.RLock()
        self.url = res.url if url is None else url
        self._data = None
        self._len = None
        self._comp = lzma.LZMACompressor() if compressor is None else compressor
        self._dcomp = decompressor

    def close(self):
        '''Closes this response cacher, closing and deleting the underlying `HTTPResponse` and cached data'''
        try:
            self._res.close()
            del self._res
        except AttributeError: pass
        try: self._data.close()
        except Exception: pass
        try: del self._data
        except AttributeError: pass
    __del__ = close

    @property
    def data(self) -> bytes | None:
        with self._rlock:
            if self._data is None: return None
            if isinstance(self._data, io.BytesIO):
                return self._dcomp(self._data.read())
            return self._dcomp(self._data)
    def _data_rst(self):
        # internal function; resets the data buffer
        with self._rlock:
            self._data = io.BytesIO()
            self._len = 0
    def _data_add(self, data: bytes):
        # internal function; adds data to the buffer
        with self._rlock:
            if self._data is None: self._data_rst()
            self._len += len(data)
            self._data.write(self._comp.compress(data))
    def _data_fin(self):
        # internal function; finalizes the data and renders it to bytes
        with self._rlock:
            self._data.write(self._comp.flush())
            with self._data: # close it after
                self._data = self._data.getvalue()

    Stat = Enum('Stat', ('UNSTARTED', 'INCOMPLETE', 'COMPLETE', 'CLOSED'))
    def stat(self) -> Stat:
        '''
            `Stat.UNSTARTED`: Reading has not yet been started
            `Stat.INCOMPLETE`: Reading has been started, but was not finalized
            `Stat.COMPLETE`: Reading has been finalized
            `Stat.CLOSED`: This instance has been closed
        '''
        with self._rlock:
            if not hasattr(self, '_data'): return self.Stat.CLOSED
            if self._data is None: return self.Stat.UNSTARTED
            if isinstance(self._data, io.BytesIO): return self.Stat.INCOMPLETE
            return self.Stat.COMPLETE

    @mlock
    def read(self, amt: int | None = None, reread: bool = True) -> bytes:
        '''
            Read and return the entire response body, or up to the next `amt` bytes
                Raises `RuntimeError` if the data is cached and `reread` is false
                Will return more than `amt` if the data is already entirely cached
        '''
        s = self.stat()
        if s is self.Stat.CLOSED:
            raise TypeError('Cannot read a closed response')
        if s is self.Stat.COMPLETE:
            if reread: return self.data
            raise RuntimeError('Refusing to reread a completed cache when reread is false')
        data = self._res.read(amt)
        self._data_add(data)
        if self._res.isclosed(): self._data_fin()
        return data
    ChunkWhence = Enum('ChunkWhence', ('START', 'START_CHUNK', 'CONTINUE'))
    @mlock
    def chunks(self, csize: int, reread: bool = True) -> typing.Generator[bytes, None, None]:
        '''
            Reads and yields the response body in chunks of (up to) `csize` byte(s)
            Where data has already been completely cached, yields the entirety of the data in one chunk
                Raises `RuntimeError` instead if `reread` is false
        '''
        s = self.stat()
        if s is self.Stat.CLOSED:
            raise TypeError('Cannot chunk-read a closed response')
        if s is self.Stat.COMPLETE:
            if reread:
                yield self.data
                return
            raise RuntimeError('Refusing to chunk-rereacd a completed cache when reread is false')
        while (self.stat() is self.Stat.INCOMPLETE) or (self.stat() is self.Stat.UNSTARTED):
            yield self.read(csize)

    @property
    def headers(self) -> HTTPMessage:
        if self.stat() is self.Stat.CLOSED: raise AttributeError('Cannot get headers from a closed response')
        return self._res.headers

    def rlength(self) -> int | None:
        '''"Reported" length from the `Content-Length` header'''
        if self.stat() is self.Stat.CLOSED: raise TypeError('Cannot get reported length from a closed response')
        with self._rlock:
            return int(cl) if (cl := self.headers.get('Content-Length')) is not None else None
    def alength(self) -> int:
        '''The accumulated size of all read bytes **before** compression'''
        if self.stat() is self.Stat.CLOSED: raise TypeError('Cannot get accumulated length from a closed response')
        with self._rlock:
            return 0 if self._data is None else self._len
    def clength(self) -> int:
        '''The stored size of the read data **after** compression'''
        if self.stat() is self.Stat.CLOSED: raise TypeError('Cannot get compressed length from a closed response')
        with self._rlock:
            if self._data is None: return 0
            if isinstance(self._data, bytes): return len(self._data)
            return self._data.tell()

cache = {}
def request(url: str, *, timeout: int | None = None, user_agent: str = 'Mozilla/5.0',
            cache_dict: dict[int, HTTPResponseCacher] = cache, read_cache: bool = True, write_cache: bool = True) -> HTTPResponseCacher:
    '''
        Requests data from `url`, constructing a `HTTPResponseCacher`
        Reads data from `cache` (or `cache_dict`, if given) if present when `read_cache` is true
        Adds data to `cache` (or `cache_dict`, if given) when `write_cache` is true
            Setting `write_cache` to true whilst `read_cache` is false is a good way to refresh a cached entry
    '''
    if read_cache:
        hurl = URL.hash(url)
        if (c := cache_dict.get(hurl, None)) is not None: return c
    elif write_cache: hurl = URL.hash(url)
    hrc = HTTPResponseCacher(urlopen(Request(url, headers={'User-Agent': user_agent}), timeout=timeout), url)
    if write_cache: cache_dict[hurl] = hrc
    return hrc

# Fetching
def fetch(url: str, **kwargs) -> bytes:
    '''
        A convenience wrapper for `request()`, returning bytes
        See `help(request)` for `kwargs`
    '''
    return request(url, **kwargs).read()
def fetch_chunked(url: str, csize: int, *, write_cache: bool = False, **kwargs) -> typing.Generator[bytes, None, None]:
    '''
        Similar to `fetch()`, but yields chunks of bytes of (up to) `csize`
            When the data is already cached (and `read_cache` is not false), it is yielded as a single chunk
        See `help(request)` for additional `kwargs`,
            note that `write_cache` is false by default in this function as chunk-reads are usually used for larger data
    '''
    return request(url, write_cache=write_cache, **kwargs).chunks(csize)

## Fancy fetching
def _fetchx_achunk(val: int, hrc: HTTPResponseCacher, csize: int, queue: SimpleQueue):
    for _ in hrc.chunks(csize): queue.put(val)
def _fetchx_fsize(size: int | None, patt: str = '{:3.1f}{}', unknown: str = '?') -> str:
    if size is None: return unknown
    size = float(size)
    for u in ('B', 'KiB', 'MiB' ,'GiB', 'TiB', 'PiB', 'EiB', 'ZiB'): # forward proofing
        if size < 1024.0:
            return patt.format(size, u)
        size /= 1024.0
    return patt.format(size, u)
def _fetchx_rsize(hrc: HTTPResponseCacher, perc: bool = True) -> str:
    return (f'{_fetchx_fsize(hrc.alength())} /'
            f' {_fetchx_fsize(hrc.rlength())}'
            f'{f" <{hrc.alength() / hrc.rlength() * 100:3.1f}%>" if (perc and (hrc.rlength() is not None)) else ""}'
            f' [comp.: {_fetchx_fsize(hrc.clength())} <{f"{hrc.clength() / hrc.alength() * 100:3.1f}" if hrc.alength() else "..."}%>]')
def _fetchx_update(target: int | None, order: list[int], rmap: dict[int, HTTPResponseCacher], nmap: dict[int, str]) -> typing.Iterator[str]:
    if (target is not None) and (rmap[target].stat() is rmap[target].Stat.COMPLETE) and (target in order):
        order.remove(target)
        yield (f'+ {nmap[target]} completed as {_fetchx_rsize(rmap[target])}')
    for r in order:
        yield (f'{">" if r == target else " "} {nmap[r]} {_fetchx_rsize(rmap[r])}')
def _fetchx(csize: int, urls: dict[int, str], rmap: dict[int, HTTPResponseCacher], nmap: dict[int, str], fullscreen: bool):
    if fullscreen: print('\x1b[2J\x1b[H', end='', flush=True)
    order = list(urls.keys())
    for r in tuple(order):
        if rmap[r].stat() is rmap[r].Stat.COMPLETE:
            print(f'x {nmap[r]} completed from cache as {_fetchx_rsize(rmap[r], False)}')
            order.remove(r)
    if not order: return
    for r in order: print(f'- Waiting: <{r}> {nmap[r]}')
    queue = SimpleQueue()
    threads = {r: threading.Thread(target=_fetchx_achunk, args=(r, rmap[r], csize, queue), daemon=True) for r in order}
    print(f'\x1b[{len(order)}F', end='', flush=True)
    for r in order:
        print(f'\x1b[2K\r~ Starting: <{r}> -> {nmap[r]}')
        threads[r].start()
    while any(map(threading.Thread.is_alive, threads.values())):
        lines = tuple(_fetchx_update(queue.get(), order, rmap, nmap))
        print(f'\x1b[{len(lines)}F\x1b[2K\r{"\n\x1b[2K\r".join(lines)}', flush=True)
    if (lines := tuple(_fetchx_update(None if queue.empty() else queue.get(), order, rmap, nmap))):
        print(f'\x1b[{len(lines)}F\x1b[2K\r{"\n\x1b[2K\r".join(lines)}', flush=True)
def fetchx(*urls: str, csize: int = 512*1024, cache_limit_kib: int = 512, target_cache: dict[int, HTTPResponseCacher] = cache,
           request_kwargs: dict[str, typing.Any] = {}, mangle_kwargs: dict[str, typing.Any] = {},
           alt_buff: bool = False, fullscreen: bool | None = None) -> tuple[bytes, ...]:
    '''
        Fetches multiple URLs at the same time, displaying progress to the user using ANSI escape sequences
        `alt_buff` switches the console to an alternate framebuffer to preserve the terminal
            The console is switched back regardless of any exceptions that occur whilst fetching
        `fullscreen` clears the entire terminal instead of just rewriting the lines that the function itself wrote
            If `fullscreen` is not given (`None`), it is set to the same value as `alt_buff`
        `request_kwargs` and `mangle_kwargs` are passed to every call of `request()` and `URL.mangle()`, respectively
    '''
    if fullscreen is None: fullscreen = alt_buff
    # Copy cache target
    cdict = target_cache.copy()
    # Generate responses and tasks
    o_urls = tuple(map(URL.hash, urls))
    urls = {URL.hash(url): url for url in urls}
    rmap = {hurl: request(url, cache_dict=cdict, **request_kwargs) for hurl,url in urls.items()}
    nmap = {hurl: URL.mangle(url, **mangle_kwargs) for hurl,url in urls.items()}
    # Run main function, swap to alternate buffer if needed
    stored_e = None
    if alt_buff: print('\x1b[?1049h', end='', flush=True)
    try: _fetchx(csize, urls, rmap, nmap, fullscreen)
    except BaseException as e: stored_e = e
    finally:
        if alt_buff: print('\x1b[?1049l', end='', flush=True)
    if stored_e is not None: raise stored_e
    # Get data, finalize cache, and return data
    data = tuple(rmap[hurl].data for hurl in o_urls)
    noadd = {h: cdict[h] for h,hrc in rmap.items() if hrc.clength() >= (cache_limit_kib * 1024)}
    for h in cdict.keys()-noadd.keys(): target_cache[h] = cdict[h]
    for hrc in noadd.values(): hrc.close()
    return data
def fetch1(url: str, **fetchx_kwargs) -> bytes:
    '''Convenience wrapper for only `fetchx()`-ing one URL'''
    return fetchx(url, **fetchx_kwargs)[0]
