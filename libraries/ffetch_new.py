#!/bin/python3

#> Imports
import typing
import threading
import itertools
from enum import Enum
from collections import deque
from urllib import request as urlrequest
from http.client import HTTPResponse, HTTPMessage
#</Imports

#> Header >/
__all__ = ('FlexiLynxHTTPResponse',)

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
            ds = self.data_stat
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
            Reads (and yields) the response body in chunks of `chunk_size` byte(s)
            If the data has already been cached, then raises a `RuntimeError` if `read_full_cache` is false, otherwise
                yields a single `bytes`, or returns an iterator of `bytes` split into `csize` if `chunk_cached` is true
            If a chunk read is already in progress, then the behavior depends on the value of `whence_chunk`:
                `Continue.RAISE`: raises a `RuntimeError`
                `Continue.CANCEL`: yields nothing
                `Continue.BEGINNING`: yields already cached data, then yields newly read chunks
                    Yields a combination of already cached data and newly read chunks in the proper chunk size if `chunk_cached` is true, such that chunk size is consistent
                `Continue.CONTINUE`: ignores already cached data, only yields newly read chunks
                    `Continue.BEGINNING_CONSISTENT` behaves the same
                Any other value results in a `TypeError`
            Note that this function is locked, along with `read()`. As such, it may deadlock whilst another read is in progress in a different thread
        '''
        with self._lock:
            ds = self.data_stat
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
            while (self.data_stat is self.DataStat.INCOMPLETE) or (self.data_stat is self.DataStat.UNSTARTED):
                yield self.read(csize)

    def _DataStatResType(name: str) -> type[int]:
        def __bool__(self):
            return self == 3
        return type(name, (int,), {'__slots__': (), '__bool__': __bool__})
    _DataStatRes = _DataStatResType('_DataStatRes')
    DataStat = Enum('DataStat', ('UNSTARTED', 'INCOMPLETE', 'COMPLETE', 'CLOSED'), type=_DataStatRes)
    @property
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
    @property
    def rlength(self) -> int | None:
        '''"reported" length from Content-Length header; could be `None`'''
        if self.data_stat is self.DataStat.CLOSED: raise TypeError('Cannot get reported length of a closed response')
        return int(cl) if (cl := self.headers.get('Content-Length')) is not None else None
    @property
    def clength(self) -> int:
        '''"cached" length, AKA size of `.data` (which may not be final)'''
        if self.data_stat is self.DataStat.CLOSED: raise TypeError('Cannot get cached length of a closed response')
        return 0 if self.data is None else len(self.data)
    @property
    def length(self) -> int:
        '''Returns the length of `.data`, similar to `clength()`, but raises `RuntimeError` when `.data` is not finalized (`.data != DataStat.COMPLETE`)'''
        ds = self.data_stat
        if ds is self.DataStat.CLOSED: raise TypeError('Cannot get length of a closed response')
        if ds is self.DataStat.COMPLETE: return len(self.data)
        raise RuntimeError('Cannot get length of an incomplete response (maybe you need `.clength()`?)')
