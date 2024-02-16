#!/bin/python3

#> Imports
import io
import bz2
import typing
import threading
from enum import Enum
from http.client import HTTPResponse, HTTPMessage

from .parallel import mlock
#</Imports

#> Header >/
__all__ = ('HTTPResponseCacher',)

# Fetching
class HTTPResponseCacher:
    '''
        A wrapper around an `HTTPResponse` object that augments various facilities, offering:
         - Response caching
         - Iterable chunked reading
         - Various helpful properties
        Note that the original `HTTPResponse` object should *never* be used again; it will certainly cause problems both ways
    '''
    __slots__ = ('url', '_res', '_lock', '_rlock', '_data', '_len', '_comp')

    def __init__(self, res: HTTPResponse, url: str | None = None, *, compress_level: int = 7):
        if getattr(res, '_cached_owned', False):
            raise TypeError('res is already owned')
        res._cached_owned = True
        self._res = res
        self._lock = threading.RLock()
        self._rlock = threading.RLock()
        self.url = res.url if url is None else url
        self._data = None
        self._len = None
        self._comp = bz2.BZ2Compressor(compress_level)

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
                return bz2.decompress(self._data.read())
            return bz2.decompress(self._data)
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
