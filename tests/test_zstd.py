import _compression
from io import BytesIO, UnsupportedOperation
import builtins
import itertools
import os
import re
import sys
import pathlib
import pickle
import random
import tempfile
import unittest
from unittest import skipIf

from test.support import (  # type: ignore
    _1G, bigmemtest, run_unittest
)

import pyzstd as zstd
from pyzstd import ZstdCompressor, RichMemZstdCompressor, \
                   ZstdDecompressor, EndlessZstdDecompressor, ZstdError, \
                   CParameter, DParameter, Strategy, \
                   compress, compress_stream, richmem_compress, \
                   decompress, decompress_stream, \
                   ZstdDict, train_dict, finalize_dict, \
                   zstd_version, zstd_version_info, compressionLevel_values, \
                   get_frame_info, get_frame_size, \
                   ZstdFile, open
from pyzstd import _zstd

DECOMPRESSED_DAT = None
COMPRESSED_DAT = None

DECOMPRESSED_100_PLUS_32KB = None
COMPRESSED_100_PLUS_32KB = None

SKIPPABLE_FRAME = None

THIS_FILE_BYTES = None
THIS_FILE_STR = None
COMPRESSED_THIS_FILE = None

COMPRESSED_BOGUS = None

SAMPLES = None

TRAINED_DICT = None

MULTITHREADED = None

def setUpModule():
    global DECOMPRESSED_DAT
    DECOMPRESSED_DAT = b'abcdefg123456' * 1000

    global COMPRESSED_DAT
    COMPRESSED_DAT = compress(DECOMPRESSED_DAT)

    global DECOMPRESSED_100_PLUS_32KB
    DECOMPRESSED_100_PLUS_32KB = b'a' * (100 + 32*1024)

    global COMPRESSED_100_PLUS_32KB
    COMPRESSED_100_PLUS_32KB = compress(DECOMPRESSED_100_PLUS_32KB)

    global SKIPPABLE_FRAME
    SKIPPABLE_FRAME = (0x184D2A50).to_bytes(4, byteorder='little') + \
                      (32*1024).to_bytes(4, byteorder='little') + \
                      b'a' * (32*1024)

    global THIS_FILE_BYTES, THIS_FILE_STR
    with builtins.open(os.path.abspath(__file__), 'rb') as f:
        THIS_FILE_BYTES = f.read()
        THIS_FILE_BYTES = re.sub(rb'\r?\n', rb'\n', THIS_FILE_BYTES)
        THIS_FILE_STR = THIS_FILE_BYTES.decode('utf-8')

    global COMPRESSED_THIS_FILE
    COMPRESSED_THIS_FILE = compress(THIS_FILE_BYTES)

    global COMPRESSED_BOGUS
    COMPRESSED_BOGUS = DECOMPRESSED_DAT

    # dict data
    words = [b'red', b'green', b'yellow', b'black', b'withe', b'blue',
             b'lilac', b'purple', b'navy', b'glod', b'silver', b'olive',
             b'dog', b'cat', b'tiger', b'lion', b'fish', b'bird']
    lst = []
    for i in range(1500):
        sample = [b'%s = %d' % (random.choice(words), random.randrange(100))
                  for j in range(20)]
        sample = b'\n'.join(sample)

        lst.append(sample)
    global SAMPLES
    SAMPLES = lst

    global TRAINED_DICT
    TRAINED_DICT = train_dict(SAMPLES, 200*1024)

    global MULTITHREADED
    MULTITHREADED = (CParameter.nbWorkers.bounds() != (0, 0))

class FunctionsTestCase(unittest.TestCase):

    def test_version(self):
        s = '.'.join((str(i) for i in zstd_version_info))
        self.assertEqual(s, zstd_version)

    def test_compressionLevel_values(self):
        self.assertEqual(type(compressionLevel_values.default), int)
        self.assertEqual(type(compressionLevel_values.min), int)
        self.assertEqual(type(compressionLevel_values.max), int)

        self.assertLess(compressionLevel_values.min, compressionLevel_values.max)

    def test_compress_decompress(self):
        raw_dat = THIS_FILE_BYTES[:len(THIS_FILE_BYTES)//6]
        default, minv, maxv = compressionLevel_values

        for level in range(max(-20, minv), maxv+1):
            dat1 = compress(raw_dat, level)
            dat2 = decompress(dat1)
            self.assertEqual(dat2, raw_dat)

    def test_get_frame_info(self):
        # no dict
        info = get_frame_info(COMPRESSED_100_PLUS_32KB[:20])
        self.assertEqual(info.decompressed_size, 32*1024+100)
        self.assertEqual(info.dictionary_id, 0)

        # use dict
        dat = compress(b'a'*345, zstd_dict=TRAINED_DICT)
        info = get_frame_info(dat)
        self.assertEqual(info.decompressed_size, 345)
        self.assertNotEqual(info.dictionary_id, 0)

        with self.assertRaises(ZstdError):
            get_frame_info(b'aaaaaaaaaaaaaa')

    def test_get_frame_size(self):
        size = get_frame_size(COMPRESSED_100_PLUS_32KB)
        self.assertEqual(size, len(COMPRESSED_100_PLUS_32KB))

        with self.assertRaises(ZstdError):
            get_frame_size(b'aaaaaaaaaaaaaa')

class ClassShapeTestCase(unittest.TestCase):

    def test_ZstdCompressor(self):
        # class attributes
        ZstdCompressor.CONTINUE
        ZstdCompressor.FLUSH_BLOCK
        ZstdCompressor.FLUSH_FRAME

        # method & member
        ZstdCompressor()
        ZstdCompressor(12, TRAINED_DICT)
        c = ZstdCompressor(level_or_option=2, zstd_dict=TRAINED_DICT)

        c.compress(b'123456')
        c.compress(b'123456', ZstdCompressor.CONTINUE)
        c.compress(data=b'123456', mode=c.CONTINUE)

        c.flush()
        c.flush(ZstdCompressor.FLUSH_BLOCK)
        c.flush(mode=c.FLUSH_FRAME)

        c.last_mode

        # decompressor method & member
        with self.assertRaises(AttributeError):
            c.decompress(b'')
        with self.assertRaises(AttributeError):
            c.at_frame_edge
        with self.assertRaises(AttributeError):
            c.eof
        with self.assertRaises(AttributeError):
            c.needs_input

        # read only attribute
        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            c.last_mode = ZstdCompressor.FLUSH_BLOCK

        # name
        self.assertIn('.ZstdCompressor', str(type(c)))

        # doesn't support pickle
        with self.assertRaises(TypeError):
            pickle.dumps(c)

        # supports subclass
        class SubClass(ZstdCompressor):
            pass

    def test_RichMemZstdCompressor(self):
        # class attributes
        with self.assertRaises(AttributeError):
            RichMemZstdCompressor.CONTINUE

        with self.assertRaises(AttributeError):
            RichMemZstdCompressor.FLUSH_BLOCK

        with self.assertRaises(AttributeError):
            RichMemZstdCompressor.FLUSH_FRAME

        # method & member
        RichMemZstdCompressor()
        RichMemZstdCompressor(12, TRAINED_DICT)
        c = RichMemZstdCompressor(level_or_option=4, zstd_dict=TRAINED_DICT)

        c.compress(b'123456')
        c.compress(data=b'123456')

        # ZstdCompressor method & member
        with self.assertRaises(TypeError):
            c.compress(b'123456', ZstdCompressor.FLUSH_FRAME)
        with self.assertRaises(AttributeError):
            c.flush()
        with self.assertRaises(AttributeError):
            c.last_mode

        # decompressor method & member
        with self.assertRaises(AttributeError):
            c.decompress(b'')
        with self.assertRaises(AttributeError):
            c.at_frame_edge
        with self.assertRaises(AttributeError):
            c.eof
        with self.assertRaises(AttributeError):
            c.needs_input

        # name
        self.assertIn('.RichMemZstdCompressor', str(type(c)))

        # doesn't support pickle
        with self.assertRaises(TypeError):
            pickle.dumps(c)

        # supports subclass
        class SubClass(RichMemZstdCompressor):
            pass

    def test_Decompressor(self):
        # method & member
        ZstdDecompressor()
        ZstdDecompressor(TRAINED_DICT, {})
        d = ZstdDecompressor(zstd_dict=TRAINED_DICT, option={})

        d.decompress(b'')
        d.decompress(b'', 100)
        d.decompress(data=b'', max_length = 100)

        d.eof
        d.needs_input
        d.unused_data

        # ZstdCompressor attributes
        with self.assertRaises(AttributeError):
            d.CONTINUE
        with self.assertRaises(AttributeError):
            d.FLUSH_BLOCK
        with self.assertRaises(AttributeError):
            d.FLUSH_FRAME
        with self.assertRaises(AttributeError):
            d.compress(b'')
        with self.assertRaises(AttributeError):
            d.flush()

        # EndlessZstdDecompressor attribute
        with self.assertRaises(AttributeError):
            d.at_frame_edge

        # read only attributes
        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            d.eof = True
        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            d.needs_input = True
        with self.assertRaisesRegex(AttributeError, 'not writable'):
            d.unused_data = b''

        # name
        self.assertIn('.ZstdDecompressor', str(type(d)))

        # doesn't support pickle
        with self.assertRaises(TypeError):
            pickle.dumps(d)

        # supports subclass
        class SubClass(ZstdDecompressor):
            pass

    def test_EndlessDecompressor(self):
        # method & member
        EndlessZstdDecompressor(TRAINED_DICT, {})
        EndlessZstdDecompressor(zstd_dict=TRAINED_DICT, option={})
        d = EndlessZstdDecompressor()

        d.decompress(b'')
        d.decompress(b'', 100)
        d.decompress(data=b'', max_length = 100)

        d.at_frame_edge
        d.needs_input

        # ZstdCompressor attributes
        with self.assertRaises(AttributeError):
            EndlessZstdDecompressor.CONTINUE
        with self.assertRaises(AttributeError):
            EndlessZstdDecompressor.FLUSH_BLOCK
        with self.assertRaises(AttributeError):
            EndlessZstdDecompressor.FLUSH_FRAME
        with self.assertRaises(AttributeError):
            d.compress(b'')
        with self.assertRaises(AttributeError):
            d.flush()

        # ZstdDecompressor attributes
        with self.assertRaises(AttributeError):
            d.eof
        with self.assertRaises(AttributeError):
            d.unused_data

        # read only attributes
        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            d.needs_input = True

        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            d.at_frame_edge = True

        # name
        self.assertIn('.EndlessZstdDecompressor', str(type(d)))

        # doesn't support pickle
        with self.assertRaises(TypeError):
            pickle.dumps(d)

        # supports subclass
        class SubClass(EndlessZstdDecompressor):
            pass

    def test_ZstdDict(self):
        ZstdDict(b'12345678', True)
        zd = ZstdDict(b'12345678', is_raw=True)

        self.assertEqual(type(zd.dict_content), bytes)
        self.assertEqual(zd.dict_id, 0)

        # name
        self.assertIn('.ZstdDict', str(type(zd)))

        # doesn't support pickle
        with self.assertRaises(TypeError):
            pickle.dumps(zd)

        # supports subclass
        class SubClass(ZstdDict):
            pass

    def test_Strategy(self):
        # class attributes
        Strategy.fast
        Strategy.dfast
        Strategy.greedy
        Strategy.lazy
        Strategy.lazy2
        Strategy.btlazy2
        Strategy.btopt
        Strategy.btultra
        Strategy.btultra2

    def test_CParameter(self):
        CParameter.compressionLevel
        CParameter.windowLog
        CParameter.hashLog
        CParameter.chainLog
        CParameter.searchLog
        CParameter.minMatch
        CParameter.targetLength
        CParameter.strategy

        CParameter.enableLongDistanceMatching
        CParameter.ldmHashLog
        CParameter.ldmMinMatch
        CParameter.ldmBucketSizeLog
        CParameter.ldmHashRateLog

        CParameter.contentSizeFlag
        CParameter.checksumFlag
        CParameter.dictIDFlag

        CParameter.nbWorkers
        CParameter.jobSize
        CParameter.overlapLog

        t = CParameter.windowLog.bounds()
        self.assertEqual(len(t), 2)
        self.assertEqual(type(t[0]), int)
        self.assertEqual(type(t[1]), int)

    def test_DParameter(self):
        DParameter.windowLogMax

        t = DParameter.windowLogMax.bounds()
        self.assertEqual(len(t), 2)
        self.assertEqual(type(t[0]), int)
        self.assertEqual(type(t[1]), int)

class CompressorDecompressorTestCase(unittest.TestCase):

    def test_simple_bad_args(self):
        # ZstdCompressor
        self.assertRaises(TypeError, ZstdCompressor, [])
        self.assertRaises(TypeError, ZstdCompressor, level_or_option=3.14)
        self.assertRaises(TypeError, ZstdCompressor, level_or_option='abc')
        self.assertRaises(TypeError, ZstdCompressor, level_or_option=b'abc')

        self.assertRaises(TypeError, ZstdCompressor, zstd_dict=123)
        self.assertRaises(TypeError, ZstdCompressor, zstd_dict=b'abcd1234')
        self.assertRaises(TypeError, ZstdCompressor, zstd_dict={1:2, 3:4})

        self.assertRaises(TypeError, ZstdCompressor, rich_mem=None)
        self.assertRaises(TypeError, ZstdCompressor, rich_mem=True)

        with self.assertRaises(ValueError):
            ZstdCompressor(2**31)
        with self.assertRaises(ValueError):
            ZstdCompressor({2**31 : 100})

        with self.assertRaises(ZstdError):
            ZstdCompressor({CParameter.windowLog:100})
        with self.assertRaises(ZstdError):
            ZstdCompressor({3333 : 100})

        # EndlessZstdDecompressor
        self.assertRaises(TypeError, EndlessZstdDecompressor, ())
        self.assertRaises(TypeError, EndlessZstdDecompressor, zstd_dict=123)
        self.assertRaises(TypeError, EndlessZstdDecompressor, zstd_dict=b'abc')
        self.assertRaises(TypeError, EndlessZstdDecompressor, zstd_dict={1:2, 3:4})

        self.assertRaises(TypeError, EndlessZstdDecompressor, option=123)
        self.assertRaises(TypeError, EndlessZstdDecompressor, option='abc')
        self.assertRaises(TypeError, EndlessZstdDecompressor, option=b'abc')

        with self.assertRaises(ValueError):
            EndlessZstdDecompressor(option={2**31 : 100})

        with self.assertRaises(ZstdError):
            EndlessZstdDecompressor(option={DParameter.windowLogMax:100})
        with self.assertRaises(ZstdError):
            EndlessZstdDecompressor(option={3333 : 100})

        # Method bad arguments
        zc = ZstdCompressor()
        self.assertRaises(TypeError, zc.compress)
        self.assertRaises(TypeError, zc.compress, b"foo", b"bar")
        self.assertRaises(TypeError, zc.compress, "str")
        self.assertRaises(TypeError, zc.flush, b"blah", 1)

        self.assertRaises(ValueError, zc.compress, b'', -1)
        self.assertRaises(ValueError, zc.compress, b'', 3)
        self.assertRaises(ValueError, zc.flush, zc.CONTINUE) # 0
        self.assertRaises(ValueError, zc.flush, 3)

        zc.compress(b'')
        zc.compress(b'', zc.CONTINUE)
        zc.compress(b'', zc.FLUSH_BLOCK)
        zc.compress(b'', zc.FLUSH_FRAME)
        empty = zc.flush()
        zc.flush(zc.FLUSH_BLOCK)
        zc.flush(zc.FLUSH_FRAME)

        lzd = EndlessZstdDecompressor()
        self.assertRaises(TypeError, lzd.decompress)
        self.assertRaises(TypeError, lzd.decompress, b"foo", b"bar")
        self.assertRaises(TypeError, lzd.decompress, "str")
        lzd.decompress(empty)

    def test_compress_parameters(self):
        d = {CParameter.compressionLevel : 10,

             CParameter.windowLog : 12,
             CParameter.hashLog : 10,
             CParameter.chainLog : 12,
             CParameter.searchLog : 12,
             CParameter.minMatch : 4,
             CParameter.targetLength : 12,
             CParameter.strategy : Strategy.lazy,

             CParameter.enableLongDistanceMatching : 1,
             CParameter.ldmHashLog : 12,
             CParameter.ldmMinMatch : 11,
             CParameter.ldmBucketSizeLog : 5,
             CParameter.ldmHashRateLog : 12,

             CParameter.contentSizeFlag : 1,
             CParameter.checksumFlag : 1,
             CParameter.dictIDFlag : 0,

             CParameter.nbWorkers : 2 if MULTITHREADED else 0,
             CParameter.jobSize : 50_000 if MULTITHREADED else 0,
             CParameter.overlapLog : 9 if MULTITHREADED else 0,
             }
        ZstdCompressor(level_or_option=d)

        # larger than signed int, ValueError
        d1 = d.copy()
        d1[CParameter.ldmBucketSizeLog] = 2**31
        self.assertRaises(ValueError, ZstdCompressor, d1)

        # value out of bounds, ZstdError
        d2 = d.copy()
        d2[CParameter.ldmBucketSizeLog] = 10
        self.assertRaises(ZstdError, ZstdCompressor, d2)

        # clamp compressionLevel
        compress(b'', compressionLevel_values.max+1)
        compress(b'', compressionLevel_values.min-1)

        compress(b'', {CParameter.compressionLevel:compressionLevel_values.max+1})
        compress(b'', {CParameter.compressionLevel:compressionLevel_values.min-1})

        # zstd lib doesn't support MT compression
        if not MULTITHREADED:
            with self.assertWarnsRegex(RuntimeWarning, r'multi-threaded'):
                ZstdCompressor({CParameter.nbWorkers:4})
            ZstdCompressor({CParameter.jobSize:4})
            ZstdCompressor({CParameter.overlapLog:4})

    def test_decompress_parameters(self):
        d = {DParameter.windowLogMax : 15}
        EndlessZstdDecompressor(option=d)

        # larger than signed int, ValueError
        d1 = d.copy()
        d1[DParameter.windowLogMax] = 2**31
        self.assertRaises(ValueError, EndlessZstdDecompressor, None, d1)

        # value out of bounds, ZstdError
        d2 = d.copy()
        d2[DParameter.windowLogMax] = 32
        self.assertRaises(ZstdError, EndlessZstdDecompressor, None, d2)

    @skipIf(CParameter.nbWorkers.bounds() == (0, 0),
            "zstd build doesn't support multi-threaded compression")
    def test_zstd_multithread_compress(self):
        size = 40*1024*1024
        b = THIS_FILE_BYTES * (size // len(THIS_FILE_BYTES))

        option = {CParameter.compressionLevel : 4,
                  CParameter.nbWorkers : 2}

        # compress()
        dat1 = compress(b, option)
        dat2 = decompress(dat1)
        self.assertEqual(dat2, b)

        # richmem_compress()
        with self.assertWarns(ResourceWarning):
            dat1 = richmem_compress(b, option)
        dat2 = decompress(dat1)
        self.assertEqual(dat2, b)

        # ZstdCompressor
        c = ZstdCompressor(option)
        dat1 = c.compress(b, c.CONTINUE)
        dat2 = c.compress(b, c.FLUSH_BLOCK)
        dat3 = c.compress(b, c.FLUSH_FRAME)
        dat4 = decompress(dat1+dat2+dat3)
        self.assertEqual(dat4, b * 3)

    def test_rich_mem_compress(self):
        b = THIS_FILE_BYTES[:len(THIS_FILE_BYTES)//3]

        dat1 = richmem_compress(b)
        dat2 = decompress(dat1)
        self.assertEqual(dat2, b)

    @skipIf(CParameter.nbWorkers.bounds() == (0, 0),
            "zstd build doesn't support multi-threaded compression")
    def test_rich_mem_compress_warn(self):
        b = THIS_FILE_BYTES[:len(THIS_FILE_BYTES)//3]

        # warning when multi-threading compression
        with self.assertWarns(ResourceWarning):
            dat1 = richmem_compress(b, {CParameter.nbWorkers:2})

        dat2 = decompress(dat1)
        self.assertEqual(dat2, b)

    def test_decompress_1byte(self):
        d = EndlessZstdDecompressor()

        dat = d.decompress(COMPRESSED_THIS_FILE, 1)
        size = len(dat)

        while True:
            if d.needs_input:
                break
            else:
                dat = d.decompress(b'', 1)

            if not dat:
                break
            size += len(dat)

            if size < len(THIS_FILE_BYTES):
                self.assertFalse(d.at_frame_edge)
            else:
                self.assertTrue(d.at_frame_edge)

        self.assertEqual(size, len(THIS_FILE_BYTES))
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_decompress_2bytes(self):
        d = EndlessZstdDecompressor()

        dat = d.decompress(COMPRESSED_THIS_FILE, 2)
        size = len(dat)

        while True:
            if d.needs_input:
                break
            else:
                dat = d.decompress(b'', 2)

            if not dat:
                break
            size += len(dat)

            if size < len(THIS_FILE_BYTES):
                self.assertFalse(d.at_frame_edge)
            else:
                self.assertTrue(d.at_frame_edge)

        self.assertEqual(size, len(THIS_FILE_BYTES))
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_decompress_3_1bytes(self):
        d = EndlessZstdDecompressor()
        bi = BytesIO(COMPRESSED_THIS_FILE)
        size = 0

        while True:
            if d.needs_input:
                in_dat = bi.read(3)
                if not in_dat:
                    break
            else:
                in_dat = b''

            dat = d.decompress(in_dat, 1)
            size += len(dat)

            if size < len(THIS_FILE_BYTES):
                self.assertFalse(d.at_frame_edge)
            else:
                self.assertTrue(d.at_frame_edge)

        self.assertEqual(size, len(THIS_FILE_BYTES))
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_decompress_3_2bytes(self):
        d = EndlessZstdDecompressor()
        bi = BytesIO(COMPRESSED_THIS_FILE)
        size = 0

        while True:
            if d.needs_input:
                in_dat = bi.read(3)
                if not in_dat:
                    break
            else:
                in_dat = b''

            dat = d.decompress(in_dat, 2)
            size += len(dat)

            if size < len(THIS_FILE_BYTES):
                self.assertFalse(d.at_frame_edge)
            else:
                self.assertTrue(d.at_frame_edge)

        self.assertEqual(size, len(THIS_FILE_BYTES))
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_decompress_1_3bytes(self):
        d = EndlessZstdDecompressor()
        bi = BytesIO(COMPRESSED_THIS_FILE)
        size = 0

        while True:
            if d.needs_input:
                in_dat = bi.read(1)
                if not in_dat:
                    break
            else:
                in_dat = b''

            dat = d.decompress(in_dat, 3)
            size += len(dat)

            if size < len(THIS_FILE_BYTES):
                self.assertFalse(d.at_frame_edge)
            else:
                self.assertTrue(d.at_frame_edge)

        self.assertEqual(size, len(THIS_FILE_BYTES))
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_decompress_epilogue_flags(self):
        # TEST_DAT_130KB has a 4 bytes checksum at frame epilogue
        _130KB = 130 * 1024

        # full unlimited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB)
        self.assertEqual(len(dat), _130KB)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')
        self.assertEqual(len(dat), 0)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')
        self.assertEqual(len(dat), 0)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # full limited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB, _130KB)
        self.assertEqual(len(dat), _130KB)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'', 0)
        self.assertEqual(len(dat), 0)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # [:-4] unlimited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-4])
        self.assertEqual(len(dat), _130KB)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')
        self.assertEqual(len(dat), 0)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # [:-4] limited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-4], _130KB)
        self.assertEqual(len(dat), _130KB)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat = d.decompress(b'', 0)
        self.assertEqual(len(dat), 0)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        # [:-3] unlimited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-3])
        self.assertEqual(len(dat), _130KB)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')
        self.assertEqual(len(dat), 0)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # [:-3] limited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-3], _130KB)
        self.assertEqual(len(dat), _130KB)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat = d.decompress(b'', 0)
        self.assertEqual(len(dat), 0)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        # [:-1] unlimited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-1])
        self.assertEqual(len(dat), _130KB)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')
        self.assertEqual(len(dat), 0)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # [:-1] limited
        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-1], _130KB)
        self.assertEqual(len(dat), _130KB)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat = d.decompress(b'', 0)
        self.assertEqual(len(dat), 0)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

    def test_decompress_2x130KB(self):
        decompressed_size = get_frame_info(TEST_DAT_130KB).decompressed_size
        self.assertEqual(decompressed_size, 130 * 1024)

        d = EndlessZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB + TEST_DAT_130KB)
        self.assertEqual(len(dat), 2 * 130 * 1024)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_compress_flushblock(self):
        point = len(THIS_FILE_BYTES) // 2

        c = ZstdCompressor()
        self.assertEqual(c.last_mode, c.FLUSH_FRAME)
        dat1 = c.compress(THIS_FILE_BYTES[:point])
        self.assertEqual(c.last_mode, c.CONTINUE)
        dat1 += c.compress(THIS_FILE_BYTES[point:], c.FLUSH_BLOCK)
        self.assertEqual(c.last_mode, c.FLUSH_BLOCK)

        d = EndlessZstdDecompressor()
        dat2 = d.decompress(dat1)

        self.assertEqual(dat2, THIS_FILE_BYTES)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_compress_flushframe(self):
        # test compress & decompress
        point = len(THIS_FILE_BYTES) // 2

        c = ZstdCompressor()

        dat1 = c.compress(THIS_FILE_BYTES[:point])
        self.assertEqual(c.last_mode, c.CONTINUE)

        dat1 += c.compress(THIS_FILE_BYTES[point:], c.FLUSH_FRAME)
        self.assertEqual(c.last_mode, c.FLUSH_FRAME)

        nt = get_frame_info(dat1)
        self.assertEqual(nt.decompressed_size, None) # no content size

        d = EndlessZstdDecompressor()
        dat2 = d.decompress(dat1)

        self.assertEqual(dat2, THIS_FILE_BYTES)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # single .FLUSH_FRAME mode has content size
        c = ZstdCompressor()
        dat = c.compress(THIS_FILE_BYTES, mode=c.FLUSH_FRAME)
        self.assertEqual(c.last_mode, c.FLUSH_FRAME)

        nt = get_frame_info(dat)
        self.assertEqual(nt.decompressed_size, len(THIS_FILE_BYTES))

    def test_decompressor_arg(self):
        zd = ZstdDict(b'12345678', True)

        with self.assertRaises(TypeError):
            d = ZstdDecompressor(zstd_dict={})

        with self.assertRaises(TypeError):
            d = ZstdDecompressor(option=zd)

        ZstdDecompressor()
        ZstdDecompressor(zd, {})
        ZstdDecompressor(zstd_dict=zd, option={DParameter.windowLogMax:25})

    def test_decompressor_1(self):
        _130_KB = 130 * 1024

        # empty
        d = ZstdDecompressor()
        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)

        # 130KB full
        d = ZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB)

        self.assertEqual(len(dat), _130_KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)

        # 130KB full, limit output
        d = ZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB, _130_KB)

        self.assertEqual(len(dat), _130_KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)

        # 130KB, without 4 bytes checksum
        d = ZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-4])

        self.assertEqual(len(dat), _130_KB)
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)

        # above, limit output
        d = ZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB[:-4], _130_KB)

        self.assertEqual(len(dat), _130_KB)
        self.assertFalse(d.eof)
        self.assertFalse(d.needs_input)

        # full, unused_data
        TRAIL = b'89234893abcd'
        d = ZstdDecompressor()
        dat = d.decompress(TEST_DAT_130KB + TRAIL, _130_KB)

        self.assertEqual(len(dat), _130_KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, TRAIL)

    def test_decompressor_chunks_read_300(self):
        _130_KB = 130 * 1024
        TRAIL = b'89234893abcd'
        DAT = TEST_DAT_130KB + TRAIL
        d = ZstdDecompressor()

        bi = BytesIO(DAT)
        lst = []
        while True:
            if d.needs_input:
                dat = bi.read(300)
                if not dat:
                    break
            else:
                raise Exception('should not get here')

            ret = d.decompress(dat)
            lst.append(ret)
            if d.eof:
                break

        ret = b''.join(lst)

        self.assertEqual(len(ret), _130_KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data + bi.read(), TRAIL)

    def test_decompressor_chunks_read_3(self):
        _130_KB = 130 * 1024
        TRAIL = b'89234893'
        DAT = TEST_DAT_130KB + TRAIL
        d = ZstdDecompressor()

        bi = BytesIO(DAT)
        lst = []
        while True:
            if d.needs_input:
                dat = bi.read(3)
                if not dat:
                    break
            else:
                dat = b''

            ret = d.decompress(dat, 1)
            lst.append(ret)
            if d.eof:
                break

        ret = b''.join(lst)

        self.assertEqual(len(ret), _130_KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data + bi.read(), TRAIL)

    def test_compress_empty(self):
        # output empty content frame
        self.assertNotEqual(compress(b''), b'')
        self.assertNotEqual(richmem_compress(b''), b'')

        c = ZstdCompressor()
        self.assertNotEqual(c.compress(b'', c.FLUSH_FRAME), b'')

        c = RichMemZstdCompressor()
        self.assertNotEqual(c.compress(b''), b'')

        # output b''
        bi = BytesIO(b'')
        bo = BytesIO()
        compress_stream(bi, bo)
        self.assertEqual(bo.getvalue(), b'')
        bi.close()
        bo.close()

    def test_decompress_empty(self):
        self.assertEqual(decompress(b''), b'')

        d = ZstdDecompressor()
        self.assertEqual(d.decompress(b''), b'')
        self.assertFalse(d.eof)

        d = EndlessZstdDecompressor()
        self.assertEqual(d.decompress(b''), b'')
        self.assertTrue(d.at_frame_edge)

        bi = BytesIO(b'')
        bo = BytesIO()
        decompress_stream(bi, bo)
        self.assertEqual(bo.getvalue(), b'')
        bi.close()
        bo.close()

class DecompressorFlagsTestCase(unittest.TestCase):

    def setUp(self):
        option = {CParameter.checksumFlag:1}
        c = ZstdCompressor(option)

        self.DECOMPRESSED_42 = b'a'*42
        self.FRAME_42 = c.compress(self.DECOMPRESSED_42, c.FLUSH_FRAME)

        self.DECOMPRESSED_60 = b'a'*60
        self.FRAME_60 = c.compress(self.DECOMPRESSED_60, c.FLUSH_FRAME)

        self.FRAME_42_60 = self.FRAME_42 + self.FRAME_60
        self.DECOMPRESSED_42_60 = self.DECOMPRESSED_42 + self.DECOMPRESSED_60

        self._130KB = 130*1024

        c = ZstdCompressor()
        self.UNKNOWN_FRAME_42 = c.compress(self.DECOMPRESSED_42) + c.flush()
        self.UNKNOWN_FRAME_60 = c.compress(self.DECOMPRESSED_60) + c.flush()
        self.UNKNOWN_FRAME_42_60 = self.UNKNOWN_FRAME_42 + self.UNKNOWN_FRAME_60

        self.TRAIL = b'12345678abcdefg!@#$%^&*()_+|'

    def test_function_decompress(self):
        self.assertEqual(decompress(b''), b'')

        self.assertEqual(len(decompress(COMPRESSED_100_PLUS_32KB)), 100+32*1024)

        # 1 frame
        self.assertEqual(decompress(self.FRAME_42), self.DECOMPRESSED_42)

        self.assertEqual(decompress(self.UNKNOWN_FRAME_42), self.DECOMPRESSED_42)

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(self.FRAME_42[:1])

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(self.FRAME_42[:-4])

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(self.FRAME_42[:-1])

        # 2 frames
        self.assertEqual(decompress(self.FRAME_42_60), self.DECOMPRESSED_42_60)

        self.assertEqual(decompress(self.UNKNOWN_FRAME_42_60), self.DECOMPRESSED_42_60)

        self.assertEqual(decompress(self.FRAME_42 + self.UNKNOWN_FRAME_60),
                         self.DECOMPRESSED_42_60)

        self.assertEqual(decompress(self.UNKNOWN_FRAME_42 + self.FRAME_60),
                         self.DECOMPRESSED_42_60)

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(self.FRAME_42_60[:-4])

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(self.UNKNOWN_FRAME_42_60[:-1])

        # 130KB
        self.assertEqual(len(decompress(TEST_DAT_130KB)), 130*1024)

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(TEST_DAT_130KB[:-4])

        with self.assertRaisesRegex(ZstdError, "incomplete frame"):
            decompress(TEST_DAT_130KB[:-1])

        # Unknown frame descriptor
        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            decompress(b'aaaaaaaaa')

        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            decompress(self.FRAME_42 + b'aaaaaaaaa')

        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            decompress(self.UNKNOWN_FRAME_42_60 + b'aaaaaaaaa')

        # doesn't match checksum
        checksum = TEST_DAT_130KB[-4:]
        if checksum[0] == 255:
            wrong_checksum = bytes([254]) + checksum[1:]
        else:
            wrong_checksum = bytes([checksum[0]+1]) + checksum[1:]

        dat = TEST_DAT_130KB[:-4] + wrong_checksum

        with self.assertRaisesRegex(ZstdError, "doesn't match checksum"):
            decompress(dat)

    def test_function_skippable(self):
        self.assertEqual(decompress(SKIPPABLE_FRAME), b'')
        self.assertEqual(decompress(SKIPPABLE_FRAME + SKIPPABLE_FRAME), b'')

        # 1 frame + 2 skippable
        self.assertEqual(len(decompress(SKIPPABLE_FRAME + SKIPPABLE_FRAME + TEST_DAT_130KB)),
                         self._130KB)

        self.assertEqual(len(decompress(TEST_DAT_130KB + SKIPPABLE_FRAME + SKIPPABLE_FRAME)),
                         self._130KB)

        self.assertEqual(len(decompress(SKIPPABLE_FRAME + TEST_DAT_130KB + SKIPPABLE_FRAME)),
                         self._130KB)

        # unknown size
        self.assertEqual(decompress(SKIPPABLE_FRAME + self.UNKNOWN_FRAME_60),
                         self.DECOMPRESSED_60)

        self.assertEqual(decompress(self.UNKNOWN_FRAME_60 + SKIPPABLE_FRAME),
                         self.DECOMPRESSED_60)

        # 2 frames + 1 skippable
        self.assertEqual(decompress(self.FRAME_42 + SKIPPABLE_FRAME + self.FRAME_60),
                         self.DECOMPRESSED_42_60)

        self.assertEqual(decompress(SKIPPABLE_FRAME + self.FRAME_42_60),
                         self.DECOMPRESSED_42_60)

        self.assertEqual(decompress(self.UNKNOWN_FRAME_42_60 + SKIPPABLE_FRAME),
                         self.DECOMPRESSED_42_60)

        # incomplete
        with self.assertRaises(ZstdError):
            decompress(SKIPPABLE_FRAME[:1])

        with self.assertRaises(ZstdError):
            decompress(SKIPPABLE_FRAME[:-1])

        with self.assertRaises(ZstdError):
            decompress(SKIPPABLE_FRAME[:-1] + self.FRAME_60)

        with self.assertRaises(ZstdError):
            decompress(self.FRAME_42 + SKIPPABLE_FRAME[:-1])

        # Unknown frame descriptor
        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            decompress(b'aaaaaaaaa' + SKIPPABLE_FRAME)

        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            decompress(SKIPPABLE_FRAME + b'aaaaaaaaa')

        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            decompress(SKIPPABLE_FRAME + SKIPPABLE_FRAME + b'aaaaaaaaa')

    def test_decompressor_1(self):
        # empty 1
        d = ZstdDecompressor()

        dat = d.decompress(b'')
        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        dat = d.decompress(b'', 0)
        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        dat = d.decompress(COMPRESSED_100_PLUS_32KB + b'a')
        self.assertEqual(dat, DECOMPRESSED_100_PLUS_32KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'a')
        self.assertEqual(d.unused_data, b'a') # twice

        # empty 2
        d = ZstdDecompressor()

        dat = d.decompress(b'', 0)
        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        dat = d.decompress(b'')
        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        dat = d.decompress(COMPRESSED_100_PLUS_32KB + b'a')
        self.assertEqual(dat, DECOMPRESSED_100_PLUS_32KB)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'a')
        self.assertEqual(d.unused_data, b'a') # twice

        # 1 frame
        d = ZstdDecompressor()
        dat = d.decompress(self.FRAME_42)

        self.assertEqual(dat, self.DECOMPRESSED_42)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        with self.assertRaises(EOFError):
            d.decompress(b'')

        # 1 frame, trail
        d = ZstdDecompressor()
        dat = d.decompress(self.FRAME_42 + self.TRAIL)

        self.assertEqual(dat, self.DECOMPRESSED_42)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, self.TRAIL)
        self.assertEqual(d.unused_data, self.TRAIL) # twice

        # 1 frame, 32KB
        temp = compress(b'a'*(32*1024))
        d = ZstdDecompressor()
        dat = d.decompress(temp, 32*1024)

        self.assertEqual(dat, b'a'*(32*1024))
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        with self.assertRaises(EOFError):
            d.decompress(b'')

        # 1 frame, 32KB+100, trail
        d = ZstdDecompressor()
        dat = d.decompress(COMPRESSED_100_PLUS_32KB+self.TRAIL, 100) # 100 bytes

        self.assertEqual(len(dat), 100)
        self.assertFalse(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')

        dat = d.decompress(b'') # 32KB

        self.assertEqual(len(dat), 32*1024)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, self.TRAIL)
        self.assertEqual(d.unused_data, self.TRAIL) # twice

        with self.assertRaises(EOFError):
            d.decompress(b'')

        # incomplete 1
        d = ZstdDecompressor()
        dat = d.decompress(self.FRAME_60[:1])

        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        # incomplete 2
        d = ZstdDecompressor()

        dat = d.decompress(self.FRAME_60[:-4])
        self.assertEqual(dat, self.DECOMPRESSED_60)
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        # incomplete 3
        d = ZstdDecompressor()

        dat = d.decompress(self.FRAME_60[:-1])
        self.assertEqual(dat, self.DECOMPRESSED_60)
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')

        # incomplete 4
        d = ZstdDecompressor()

        dat = d.decompress(self.FRAME_60[:-4], 60)
        self.assertEqual(dat, self.DECOMPRESSED_60)
        self.assertFalse(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        dat = d.decompress(b'')
        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        # Unknown frame descriptor
        d = ZstdDecompressor()
        with self.assertRaisesRegex(ZstdError, "Unknown frame descriptor"):
            d.decompress(b'aaaaaaaaa')

    def test_decompressor_skippable(self):
        # 1 skippable
        d = ZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME)

        self.assertEqual(dat, b'')
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        # 1 skippable, max_length=0
        d = ZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME, 0)

        self.assertEqual(dat, b'')
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        # 1 skippable, trail
        d = ZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME + self.TRAIL)

        self.assertEqual(dat, b'')
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, self.TRAIL)
        self.assertEqual(d.unused_data, self.TRAIL) # twice

        # incomplete
        d = ZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME[:-1])

        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        # incomplete
        d = ZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME[:-1], 0)

        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertFalse(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)
        self.assertEqual(d.unused_data, b'')
        self.assertEqual(d.unused_data, b'') # twice

    def test_endless_1(self):
        # empty
        d = EndlessZstdDecompressor()
        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'', 0)

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # 1 frame, a
        d = EndlessZstdDecompressor()
        dat = d.decompress(self.FRAME_42)

        self.assertEqual(dat, self.DECOMPRESSED_42)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(self.FRAME_60, 60)

        self.assertEqual(dat, self.DECOMPRESSED_60)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # 1 frame, b
        d = EndlessZstdDecompressor()
        dat = d.decompress(self.FRAME_42, 21)

        self.assertNotEqual(dat, self.DECOMPRESSED_42)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat += d.decompress(self.FRAME_60, 21)

        self.assertEqual(dat, self.DECOMPRESSED_42)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat = d.decompress(b'', 60)

        self.assertEqual(dat, self.DECOMPRESSED_60)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # 1 frame, trail
        d = EndlessZstdDecompressor()
        dat = None
        with self.assertRaises(ZstdError):
            d.decompress(self.FRAME_42 + self.TRAIL)

        self.assertTrue(d.at_frame_edge) # resetted
        self.assertTrue(d.needs_input)   # resetted

        # 2 frames, a
        d = EndlessZstdDecompressor()
        dat = d.decompress(self.FRAME_42_60)

        self.assertEqual(dat, self.DECOMPRESSED_42+self.DECOMPRESSED_60)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # 2 frame2, b
        d = EndlessZstdDecompressor()
        dat = d.decompress(self.FRAME_42_60, 42)

        self.assertEqual(dat, self.DECOMPRESSED_42)
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat = d.decompress(b'')

        self.assertEqual(dat, self.DECOMPRESSED_60)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # incomplete
        d = EndlessZstdDecompressor()
        dat = d.decompress(self.FRAME_42_60[:-2])

        self.assertEqual(dat, self.DECOMPRESSED_42 + self.DECOMPRESSED_60)
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_endlessdecompressor_skippable(self):
        # 1 skippable
        d = EndlessZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME)

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # 1 skippable, max_length=0
        d = EndlessZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME, 0)

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        # 1 skippable, trail
        d = EndlessZstdDecompressor()
        with self.assertRaises(ZstdError):
            d.decompress(SKIPPABLE_FRAME + self.TRAIL)

        self.assertEqual(dat, b'')
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

         # incomplete
        d = EndlessZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME[:-1], 0)

        self.assertEqual(dat, b'')
        self.assertFalse(d.at_frame_edge)
        self.assertFalse(d.needs_input)

        dat = d.decompress(b'')

        self.assertEqual(dat, b'')
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

       # incomplete
        d = EndlessZstdDecompressor()
        dat = d.decompress(SKIPPABLE_FRAME + SKIPPABLE_FRAME[:-1])

        self.assertEqual(dat, b'')
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

        dat = d.decompress(b'')
        self.assertEqual(dat, b'')
        self.assertFalse(d.at_frame_edge)
        self.assertTrue(d.needs_input)

class ZstdDictTestCase(unittest.TestCase):

    def test_is_raw(self):
        # content < 8
        b = b'1234567'
        with self.assertRaises(ValueError):
            ZstdDict(b)

        # content == 8
        b = b'12345678'
        zd = ZstdDict(b, is_raw=True)
        self.assertEqual(zd.dict_id, 0)

        temp = compress(b'aaa12345678', 3, zd)
        self.assertEqual(b'aaa12345678', decompress(temp, zd))

        # is_raw == False
        b = b'12345678abcd'
        with self.assertRaises(ValueError):
            ZstdDict(b)

        # read only attributes
        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            zd.dict_content = b

        with self.assertRaisesRegex(AttributeError, 'readonly attribute'):
            zd.dict_id = 10000

        # ZstdDict arguments
        zd = ZstdDict(TRAINED_DICT.dict_content, is_raw=False)
        self.assertNotEqual(zd.dict_id, 0)

        zd = ZstdDict(TRAINED_DICT.dict_content, is_raw=True)
        self.assertNotEqual(zd.dict_id, 0) # note this assertion

        with self.assertRaises(TypeError):
            ZstdDict("12345678abcdef", is_raw=True)
        with self.assertRaises(TypeError):
            ZstdDict(TRAINED_DICT)

    def test_invalid_dict(self):
        DICT_MAGIC = 0xEC30A437.to_bytes(4, byteorder='little')
        dict = DICT_MAGIC + b'abcdefghighlmnopqrstuvwxyz'
        zd = ZstdDict(dict, is_raw=False)

        with self.assertRaisesRegex(ZstdError, 'ZSTD_CDict'):
            compress(b'', 12, zd)

        with self.assertRaisesRegex(ZstdError, 'ZSTD_DDict'):
            decompress(b'', zd)

    def test_train_dict(self):
        DICT_SIZE1 = 200*1024

        global TRAINED_DICT
        TRAINED_DICT = zstd.train_dict(SAMPLES, DICT_SIZE1)
        ZstdDict(TRAINED_DICT.dict_content, False)

        self.assertNotEqual(TRAINED_DICT.dict_id, 0)
        self.assertGreater(len(TRAINED_DICT.dict_content), 0)
        self.assertLessEqual(len(TRAINED_DICT.dict_content), DICT_SIZE1)
        self.assertTrue(re.match(r'^<ZstdDict dict_id=\d+ dict_size=\d+>$', str(TRAINED_DICT)))

        # compress/decompress
        c = ZstdCompressor(zstd_dict=TRAINED_DICT)
        for sample in SAMPLES:
            dat1 = compress(sample, zstd_dict=TRAINED_DICT)
            dat2 = decompress(dat1, TRAINED_DICT)
            self.assertEqual(sample, dat2)

            dat1 = c.compress(sample)
            dat1 += c.flush()
            dat2 = decompress(dat1, TRAINED_DICT)
            self.assertEqual(sample, dat2)

    def test_finalize_dict(self):
        if zstd_version_info < (1, 4, 5):
            return

        DICT_SIZE2 = 200*1024
        C_LEVEL = 6
        dic2 = finalize_dict(TRAINED_DICT, SAMPLES, DICT_SIZE2, C_LEVEL)

        self.assertNotEqual(dic2.dict_id, 0)
        self.assertGreater(len(dic2.dict_content), 0)
        self.assertLessEqual(len(dic2.dict_content), DICT_SIZE2)

        # compress/decompress
        c = ZstdCompressor(C_LEVEL, dic2)
        for sample in SAMPLES:
            dat1 = compress(sample, C_LEVEL, dic2)
            dat2 = decompress(dat1, dic2)
            self.assertEqual(sample, dat2)

            dat1 = c.compress(sample)
            dat1 += c.flush()
            dat2 = decompress(dat1, dic2)
            self.assertEqual(sample, dat2)

        # dict mismatch
        self.assertNotEqual(TRAINED_DICT.dict_id, dic2.dict_id)

        dat1 = compress(SAMPLES[0], zstd_dict=TRAINED_DICT)
        with self.assertRaises(ZstdError):
            decompress(dat1, dic2)

    def test_train_dict_arguments(self):
        with self.assertRaises(ValueError):
            train_dict([], 100_000)

        with self.assertRaises(ValueError):
            train_dict(SAMPLES, -100)

        with self.assertRaises(ValueError):
            train_dict(SAMPLES, 0)

    @skipIf(zstd_version_info < (1, 4, 5), 'finalize_dict avaliable in zstd v1.4.5+')
    def test_finalize_dict_arguments(self):
        with self.assertRaises(TypeError):
            finalize_dict({1:2}, [b'aaa', b'bbb'], 100_000, 2)

        with self.assertRaises(ValueError):
            finalize_dict(TRAINED_DICT, [], 100_000, 2)

        with self.assertRaises(ValueError):
            finalize_dict(TRAINED_DICT, SAMPLES, -100, 2)

        with self.assertRaises(ValueError):
            finalize_dict(TRAINED_DICT, SAMPLES, 0, 2)

    def test_train_dict_c(self):
        # argument wrong type
        with self.assertRaises(TypeError):
            _zstd._train_dict({}, [], 100)
        with self.assertRaises(TypeError):
            _zstd._train_dict(b'', 99, 100)
        with self.assertRaises(TypeError):
            _zstd._train_dict(b'', [], 100.1)

        # size > size_t
        with self.assertRaises(ValueError):
            _zstd._train_dict(b'', [2**64+1], 100)

        # dict_size <= 0
        with self.assertRaises(ValueError):
            _zstd._train_dict(b'', [], 0)

    @skipIf(zstd_version_info < (1, 4, 5), 'finalize_dict avaliable in zstd v1.4.5+')
    def test_finalize_dict_c(self):
        # argument wrong type
        with self.assertRaises(TypeError):
            _zstd._finalize_dict({}, b'', [], 100, 5)
        with self.assertRaises(TypeError):
            _zstd._finalize_dict(TRAINED_DICT.dict_content, {}, [], 100, 5)
        with self.assertRaises(TypeError):
            _zstd._finalize_dict(TRAINED_DICT.dict_content, b'', 99, 100, 5)
        with self.assertRaises(TypeError):
            _zstd._finalize_dict(TRAINED_DICT.dict_content, b'', [], 100.1, 5)
        with self.assertRaises(TypeError):
            _zstd._finalize_dict(TRAINED_DICT.dict_content, b'', [], 100, 5.1)

        # size > size_t
        with self.assertRaises(ValueError):
            _zstd._finalize_dict(TRAINED_DICT.dict_content, b'', [2**64+1], 100, 5)

        # dict_size <= 0
        with self.assertRaises(ValueError):
            _zstd._finalize_dict(TRAINED_DICT.dict_content, b'', [], 0, 5)

class OutputBufferTestCase(unittest.TestCase):

    def setUp(self):
        KB = 1024
        MB = 1024 * 1024

        # should be same as the definition in _zstdmodule.c
        self.BLOCK_SIZE = \
             [ 32*KB, 64*KB, 256*KB, 1*MB, 4*MB, 8*MB, 16*MB, 16*MB,
               32*MB, 32*MB, 32*MB, 32*MB, 64*MB, 64*MB, 128*MB, 128*MB,
               256*MB ]

        # accumulated size
        self.ACCUMULATED_SIZE = list(itertools.accumulate(self.BLOCK_SIZE))

        self.TEST_RANGE = 5

        self.NO_SIZE_OPTION = {CParameter.compressionLevel: compressionLevel_values.min,
                               CParameter.contentSizeFlag: 0}

    def compress_unknown_size(self, size):
        return compress(b'a' * size, self.NO_SIZE_OPTION)

    def test_empty_input(self):
        dat1 = b''

        # decompress() function
        dat2 = decompress(dat1)
        self.assertEqual(len(dat2), 0)

        # ZstdDecompressor class
        d = ZstdDecompressor()
        dat2 = d.decompress(dat1)
        self.assertEqual(len(dat2), 0)
        self.assertFalse(d.eof)
        self.assertTrue(d.needs_input)

        # EndlessZstdDecompressor class
        d = EndlessZstdDecompressor()
        dat2 = d.decompress(dat1)
        self.assertEqual(len(dat2), 0)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_zero_size_output(self):
        dat1 = self.compress_unknown_size(0)

        # decompress() function
        dat2 = decompress(dat1)
        self.assertEqual(len(dat2), 0)

        # ZstdDecompressor class
        d = ZstdDecompressor()
        dat2 = d.decompress(dat1)
        self.assertEqual(len(dat2), 0)
        self.assertTrue(d.eof)
        self.assertFalse(d.needs_input)

        # EndlessZstdDecompressor class
        d = EndlessZstdDecompressor()
        dat2 = d.decompress(dat1)
        self.assertEqual(len(dat2), 0)
        self.assertTrue(d.at_frame_edge)
        self.assertTrue(d.needs_input)

    def test_edge_sizes(self):
        for index in range(self.TEST_RANGE):
            for extra in [-1, 0, 1]:
                SIZE = self.ACCUMULATED_SIZE[index] + extra
                dat1 = self.compress_unknown_size(SIZE)

                # decompress() function
                dat2 = decompress(dat1)
                self.assertEqual(len(dat2), SIZE)

                # ZstdDecompressor class
                d = ZstdDecompressor()
                dat2 = d.decompress(dat1)
                self.assertEqual(len(dat2), SIZE)
                self.assertTrue(d.eof)
                self.assertFalse(d.needs_input)

                # EndlessZstdDecompressor class
                d = EndlessZstdDecompressor()
                dat2 = d.decompress(dat1)
                self.assertEqual(len(dat2), SIZE)
                self.assertTrue(d.at_frame_edge)
                self.assertTrue(d.needs_input)

    def test_edge_sizes_stream(self):
        SIZE = self.ACCUMULATED_SIZE[self.TEST_RANGE]
        dat1 = self.compress_unknown_size(SIZE)

        # ZstdDecompressor class
        d = ZstdDecompressor()
        d.decompress(dat1, 0)

        for index in range(self.TEST_RANGE+1):
            B_SIZE = self.BLOCK_SIZE[index]
            dat2 = d.decompress(b'', B_SIZE)

            self.assertEqual(len(dat2), B_SIZE)
            self.assertFalse(d.needs_input)
            if index < self.TEST_RANGE:
                self.assertFalse(d.eof)
            else:
                self.assertTrue(d.eof)

        # EndlessZstdDecompressor class
        d = EndlessZstdDecompressor()
        d.decompress(dat1, 0)

        for index in range(self.TEST_RANGE+1):
            B_SIZE = self.BLOCK_SIZE[index]
            dat2 = d.decompress(b'', B_SIZE)

            self.assertEqual(len(dat2), B_SIZE)
            if index < self.TEST_RANGE:
                self.assertFalse(d.at_frame_edge)
                self.assertFalse(d.needs_input)
            else:
                self.assertTrue(d.at_frame_edge)
                self.assertTrue(d.needs_input)

    def test_endlessdecompressor_2_frames(self):
        self.assertGreater(self.TEST_RANGE - 2, 0)

        for extra in [-1, 0, 1]:
            # frame 1 size
            SIZE1 = self.ACCUMULATED_SIZE[self.TEST_RANGE - 2] + extra
            # frame 2 size
            SIZE2 = self.ACCUMULATED_SIZE[self.TEST_RANGE] - SIZE1

            FRAME1 = self.compress_unknown_size(SIZE1)
            FRAME2 = self.compress_unknown_size(SIZE2)

            # one step
            d = EndlessZstdDecompressor()

            dat2 = d.decompress(FRAME1 + FRAME2)
            self.assertEqual(len(dat2), SIZE1 + SIZE2)
            self.assertTrue(d.at_frame_edge)
            self.assertTrue(d.needs_input)

            # two step
            d = EndlessZstdDecompressor()

            # frame 1
            dat2 = d.decompress(FRAME1 + FRAME2, SIZE1)
            self.assertEqual(len(dat2), SIZE1)
            self.assertFalse(d.at_frame_edge) # input stream not at a frame edge
            self.assertFalse(d.needs_input)

            # frame 2
            dat2 = d.decompress(b'')
            self.assertEqual(len(dat2), SIZE2)
            self.assertTrue(d.at_frame_edge)
            self.assertTrue(d.needs_input)

    def test_known_size(self):
        # only decompress() function supports first frame with known size

        # 1 frame, the decompressed size is known
        SIZE1 = 123_456
        known_size = compress(b'a' * SIZE1)

        dat = decompress(known_size)
        self.assertEqual(len(dat), SIZE1)

        # 2 frame, the second frame's decompressed size is unknown
        for extra in [-1, 0, 1]:
            SIZE2 = self.BLOCK_SIZE[1] + self.BLOCK_SIZE[2] + extra
            unkown_size = self.compress_unknown_size(SIZE2)

            dat = decompress(known_size + unkown_size)
            self.assertEqual(len(dat), SIZE1 + SIZE2)

    @bigmemtest(size = 2*_1G, memuse = 1)
    @unittest.skipUnless(sys.maxsize > 2**32, '64-bit build test')
    def test_large_output(self, size):
        SIZE = self.ACCUMULATED_SIZE[-1] + self.BLOCK_SIZE[-1] + 100_000
        dat1 = self.compress_unknown_size(SIZE)

        dat2 = decompress(dat1)
        leng_dat2 = len(dat2)
        del dat2
        self.assertEqual(leng_dat2, SIZE)

class FileTestCase(unittest.TestCase):

    def test_init(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            pass
        with ZstdFile(BytesIO(), "w") as f:
            pass
        with ZstdFile(BytesIO(), "x") as f:
            pass
        with ZstdFile(BytesIO(), "a") as f:
            pass

        with ZstdFile(BytesIO(), "w", level_or_option=12) as f:
            pass
        with ZstdFile(BytesIO(), "w", level_or_option={CParameter.checksumFlag:1}) as f:
            pass
        with ZstdFile(BytesIO(), "w", level_or_option={}) as f:
            pass
        with ZstdFile(BytesIO(), "w", level_or_option=20, zstd_dict=TRAINED_DICT) as f:
            pass

        with ZstdFile(BytesIO(), "r", level_or_option={DParameter.windowLogMax:25}) as f:
            pass
        with ZstdFile(BytesIO(), "r", level_or_option={}, zstd_dict=TRAINED_DICT) as f:
            pass

    def test_init_with_PathLike_filename(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            filename = pathlib.Path(tmp_f.name)

        with ZstdFile(filename, "a") as f:
            f.write(DECOMPRESSED_100_PLUS_32KB)
        with ZstdFile(filename) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)

        with ZstdFile(filename, "a") as f:
            f.write(DECOMPRESSED_100_PLUS_32KB)
        with ZstdFile(filename) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB * 2)

        os.remove(filename)

    def test_init_with_filename(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            filename = pathlib.Path(tmp_f.name)

        with ZstdFile(filename) as f:
            pass
        with ZstdFile(filename, "w") as f:
            pass
        with ZstdFile(filename, "a") as f:
            pass

        os.remove(filename)

    def test_init_mode(self):
        bi = BytesIO()

        with ZstdFile(bi, "r"):
            pass
        with ZstdFile(bi, "rb"):
            pass
        with ZstdFile(bi, "w"):
            pass
        with ZstdFile(bi, "wb"):
            pass
        with ZstdFile(bi, "a"):
            pass
        with ZstdFile(bi, "ab"):
            pass

    def test_init_with_x_mode(self):
        with tempfile.NamedTemporaryFile() as tmp_f:
            filename = pathlib.Path(tmp_f.name)

        for mode in ("x", "xb"):
            with ZstdFile(filename, mode):
                pass
            with self.assertRaises(FileExistsError):
                with ZstdFile(filename, mode):
                    pass
            os.remove(filename)

    def test_init_bad_mode(self):
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), (3, "x"))
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "xt")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "x+")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "rx")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "wx")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "rt")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "r+")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "wt")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "w+")
        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "rw")

        # doesn't raise ZstdError, due to:
        # (DParameter.windowLogMax == CParameter.compressionLevel == 100)
        if DParameter.windowLogMax == CParameter.compressionLevel:
            ZstdFile(BytesIO(), "w",
                     level_or_option={DParameter.windowLogMax:compressionLevel_values.max})

            ZstdFile(BytesIO(), "w",
                     level_or_option={DParameter.windowLogMax:compressionLevel_values.max+1})

        with self.assertRaises(TypeError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "r", level_or_option=12)

        with self.assertRaises(ZstdError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "r", level_or_option={CParameter.checksumFlag:1})

    def test_init_bad_check(self):
        with self.assertRaises(TypeError):
            ZstdFile(BytesIO(), "w", level_or_option='asd')
        # CHECK_UNKNOWN and anything above CHECK_ID_MAX should be invalid.
        with self.assertRaises(ZstdError):
            ZstdFile(BytesIO(), "w", level_or_option={999:9999})
        with self.assertRaises(ZstdError):
            ZstdFile(BytesIO(), "w", level_or_option={CParameter.windowLog:99})

        with self.assertRaises(TypeError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "r", level_or_option=33)

        with self.assertRaises(ValueError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB),
                             level_or_option={DParameter.windowLogMax:2**31})

        with self.assertRaises(ZstdError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB),
                             level_or_option={444:333})

        with self.assertRaises(TypeError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), zstd_dict={1:2})

        with self.assertRaises(TypeError):
            ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), zstd_dict=b'dict123456')


    def test_close(self):
        with BytesIO(COMPRESSED_100_PLUS_32KB) as src:
            f = ZstdFile(src)
            f.close()
            # ZstdFile.close() should not close the underlying file object.
            self.assertFalse(src.closed)
            # Try closing an already-closed ZstdFile.
            f.close()
            self.assertFalse(src.closed)

        # Test with a real file on disk, opened directly by LZMAFile.
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            filename = pathlib.Path(tmp_f.name)

        f = ZstdFile(filename)
        fp = f._fp
        f.close()
        # Here, ZstdFile.close() *should* close the underlying file object.
        self.assertTrue(fp.closed)
        # Try closing an already-closed ZstdFile.
        f.close()

        os.remove(filename)

    def test_closed(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        try:
            self.assertFalse(f.closed)
            f.read()
            self.assertFalse(f.closed)
        finally:
            f.close()
        self.assertTrue(f.closed)

        f = ZstdFile(BytesIO(), "w")
        try:
            self.assertFalse(f.closed)
        finally:
            f.close()
        self.assertTrue(f.closed)

    def test_fileno(self):
        # 1
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        try:
            self.assertRaises(UnsupportedOperation, f.fileno)
        finally:
            f.close()
        self.assertRaises(ValueError, f.fileno)

        # 2
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            filename = pathlib.Path(tmp_f.name)

        f = ZstdFile(filename)
        try:
            self.assertEqual(f.fileno(), f._fp.fileno())
            self.assertIsInstance(f.fileno(), int)
        finally:
            f.close()
        self.assertRaises(ValueError, f.fileno)

        os.remove(filename)

    def test_seekable(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        try:
            self.assertTrue(f.seekable())
            f.read()
            self.assertTrue(f.seekable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.seekable)

        f = ZstdFile(BytesIO(), "w")
        try:
            self.assertFalse(f.seekable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.seekable)

        src = BytesIO(COMPRESSED_100_PLUS_32KB)
        src.seekable = lambda: False
        f = ZstdFile(src)
        try:
            self.assertFalse(f.seekable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.seekable)

    def test_readable(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        try:
            self.assertTrue(f.readable())
            f.read()
            self.assertTrue(f.readable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.readable)

        f = ZstdFile(BytesIO(), "w")
        try:
            self.assertFalse(f.readable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.readable)

    def test_writable(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        try:
            self.assertFalse(f.writable())
            f.read()
            self.assertFalse(f.writable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.writable)

        f = ZstdFile(BytesIO(), "w")
        try:
            self.assertTrue(f.writable())
        finally:
            f.close()
        self.assertRaises(ValueError, f.writable)

    def test_read(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)
            self.assertEqual(f.read(), b"")

        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)

        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB),
                              level_or_option={DParameter.windowLogMax:20}) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)
            self.assertEqual(f.read(), b"")

    def test_read_0(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            self.assertEqual(f.read(0), b"")
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB),
                              level_or_option={DParameter.windowLogMax:20}) as f:
            self.assertEqual(f.read(0), b"")

    def test_read_10(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            chunks = []
            while True:
                result = f.read(10)
                if not result:
                    break
                self.assertLessEqual(len(result), 10)
                chunks.append(result)
            self.assertEqual(b"".join(chunks), DECOMPRESSED_100_PLUS_32KB)

    def test_read_multistream(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB * 5)) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB * 5)

        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB + SKIPPABLE_FRAME)) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)

        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB + COMPRESSED_DAT)) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB + DECOMPRESSED_DAT)

    def test_read_multistream_buffer_size_aligned(self):
        # Test the case where a stream boundary coincides with the end
        # of the raw read buffer.
        saved_buffer_size = _compression.BUFFER_SIZE
        _compression.BUFFER_SIZE = len(COMPRESSED_100_PLUS_32KB)
        try:
            with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB *  5)) as f:
                self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB * 5)
        finally:
            _compression.BUFFER_SIZE = saved_buffer_size

    def test_read_incomplete(self):
        with ZstdFile(BytesIO(TEST_DAT_130KB[:-200])) as f:
            self.assertRaises(EOFError, f.read)

    def test_read_truncated(self):
        # Drop stream epilogue: 4 bytes checksum
        truncated = TEST_DAT_130KB[:-4]
        with ZstdFile(BytesIO(truncated)) as f:
            self.assertRaises(EOFError, f.read)

        with ZstdFile(BytesIO(truncated)) as f:
            self.assertEqual(f.read(130*1024), decompress(TEST_DAT_130KB))
            self.assertRaises(EOFError, f.read, 1)

        # Incomplete header
        for i in range(20):
            with ZstdFile(BytesIO(truncated[:i])) as f:
                self.assertRaises(EOFError, f.read, 1)

    def test_read_bad_args(self):
        f = ZstdFile(BytesIO(COMPRESSED_DAT))
        f.close()
        self.assertRaises(ValueError, f.read)
        with ZstdFile(BytesIO(), "w") as f:
            self.assertRaises(ValueError, f.read)
        with ZstdFile(BytesIO(COMPRESSED_DAT)) as f:
            self.assertRaises(TypeError, f.read, float())

    def test_read_bad_data(self):
        with ZstdFile(BytesIO(COMPRESSED_BOGUS)) as f:
            self.assertRaises(ZstdError, f.read)

    def test_read1(self):
        with ZstdFile(BytesIO(TEST_DAT_130KB)) as f:
            blocks = []
            while True:
                result = f.read1()
                if not result:
                    break
                blocks.append(result)
            self.assertEqual(len(b"".join(blocks)), 130*1024)
            self.assertEqual(f.read1(), b"")

    def test_read1_0(self):
        with ZstdFile(BytesIO(COMPRESSED_DAT)) as f:
            self.assertEqual(f.read1(0), b"")

    def test_read1_10(self):
        with ZstdFile(BytesIO(COMPRESSED_DAT)) as f:
            blocks = []
            while True:
                result = f.read1(10)
                if not result:
                    break
                blocks.append(result)
            self.assertEqual(b"".join(blocks), DECOMPRESSED_DAT)
            self.assertEqual(f.read1(), b"")

    def test_read1_multistream(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB * 5)) as f:
            blocks = []
            while True:
                result = f.read1()
                if not result:
                    break
                blocks.append(result)
            self.assertEqual(b"".join(blocks), DECOMPRESSED_100_PLUS_32KB * 5)
            self.assertEqual(f.read1(), b"")

    def test_read1_bad_args(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        f.close()
        self.assertRaises(ValueError, f.read1)
        with ZstdFile(BytesIO(), "w") as f:
            self.assertRaises(ValueError, f.read1)
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            self.assertRaises(TypeError, f.read1, None)

    def test_peek(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            result = f.peek()
            self.assertGreater(len(result), 0)
            self.assertTrue(DECOMPRESSED_100_PLUS_32KB.startswith(result))
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            result = f.peek(10)
            self.assertGreater(len(result), 0)
            self.assertTrue(DECOMPRESSED_100_PLUS_32KB.startswith(result))
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)

    def test_peek_bad_args(self):
        with ZstdFile(BytesIO(), "w") as f:
            self.assertRaises(ValueError, f.peek)

    def test_iterator(self):
        with BytesIO(THIS_FILE_BYTES) as f:
            lines = f.readlines()
        compressed = compress(THIS_FILE_BYTES)

        with ZstdFile(BytesIO(compressed)) as f:
            self.assertListEqual(list(iter(f)), lines)

        # readline
        with BytesIO(THIS_FILE_BYTES) as f:
            lines = f.readlines()
        with ZstdFile(BytesIO(compressed)) as f:
            for line in lines:
                self.assertEqual(f.readline(), line)

        # readlines
        with BytesIO(THIS_FILE_BYTES) as f:
            lines = f.readlines()
        with ZstdFile(BytesIO(compressed)) as f:
            self.assertListEqual(f.readlines(), lines)

    def test_decompress_limited(self):
        bomb = compress(b'\0' * int(2e6), 10)
        self.assertLess(len(bomb), _compression.BUFFER_SIZE)

        decomp = ZstdFile(BytesIO(bomb))
        self.assertEqual(decomp.read(1), b'\0')

        max_decomp = 1 + _compression.BUFFER_SIZE
        self.assertLessEqual(decomp._buffer.raw.tell(), max_decomp)

    def test_write(self):
        with BytesIO() as dst:
            with ZstdFile(dst, "w") as f:
                f.write(THIS_FILE_BYTES)

            comp = ZstdCompressor()
            expected = comp.compress(THIS_FILE_BYTES) + comp.flush()
            self.assertEqual(dst.getvalue(), expected)

        with BytesIO() as dst:
            with ZstdFile(dst, "w", level_or_option=12) as f:
                f.write(THIS_FILE_BYTES)

            comp = ZstdCompressor(12)
            expected = comp.compress(THIS_FILE_BYTES) + comp.flush()
            self.assertEqual(dst.getvalue(), expected)

        with BytesIO() as dst:
            with ZstdFile(dst, "w", level_or_option={CParameter.checksumFlag:1}) as f:
                f.write(THIS_FILE_BYTES)

            comp = ZstdCompressor({CParameter.checksumFlag:1})
            expected = comp.compress(THIS_FILE_BYTES) + comp.flush()
            self.assertEqual(dst.getvalue(), expected)

        with BytesIO() as dst:
            option = {CParameter.compressionLevel:-5,
                      CParameter.checksumFlag:1}
            with ZstdFile(dst, "w", level_or_option=option) as f:
                f.write(THIS_FILE_BYTES)

            comp = ZstdCompressor(option)
            expected = comp.compress(THIS_FILE_BYTES) + comp.flush()
            self.assertEqual(dst.getvalue(), expected)

    def test_write_101(self):
        with BytesIO() as dst:
            with ZstdFile(dst, "w") as f:
                for start in range(0, len(THIS_FILE_BYTES), 101):
                    f.write(THIS_FILE_BYTES[start:start+101])

            comp = ZstdCompressor()
            expected = comp.compress(THIS_FILE_BYTES) + comp.flush()
            self.assertEqual(dst.getvalue(), expected)

    def test_write_append(self):
        def comp(data):
            comp = ZstdCompressor()
            return comp.compress(data) + comp.flush()

        part1 = THIS_FILE_BYTES[:1024]
        part2 = THIS_FILE_BYTES[1024:1536]
        part3 = THIS_FILE_BYTES[1536:]
        expected = b"".join(comp(x) for x in (part1, part2, part3))
        with BytesIO() as dst:
            with ZstdFile(dst, "w") as f:
                f.write(part1)
            with ZstdFile(dst, "a") as f:
                f.write(part2)
            with ZstdFile(dst, "a") as f:
                f.write(part3)
            self.assertEqual(dst.getvalue(), expected)

    def test_write_bad_args(self):
        f = ZstdFile(BytesIO(), "w")
        f.close()
        self.assertRaises(ValueError, f.write, b"foo")
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB), "r") as f:
            self.assertRaises(ValueError, f.write, b"bar")
        with ZstdFile(BytesIO(), "w") as f:
            self.assertRaises(TypeError, f.write, None)
            self.assertRaises(TypeError, f.write, "text")
            self.assertRaises(TypeError, f.write, 789)

    def test_writelines(self):
        def comp(data):
            comp = ZstdCompressor()
            return comp.compress(data) + comp.flush()

        with BytesIO(THIS_FILE_BYTES) as f:
            lines = f.readlines()
        with BytesIO() as dst:
            with ZstdFile(dst, "w") as f:
                f.writelines(lines)
            expected = comp(THIS_FILE_BYTES)
            self.assertEqual(dst.getvalue(), expected)

    def test_seek_forward(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.seek(555)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB[555:])

    def test_seek_forward_across_streams(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB * 2)) as f:
            f.seek(len(DECOMPRESSED_100_PLUS_32KB) + 123)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB[123:])

    def test_seek_forward_relative_to_current(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.read(100)
            f.seek(1236, 1)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB[1336:])

    def test_seek_forward_relative_to_end(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.seek(-555, 2)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB[-555:])

    def test_seek_backward(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.read(1001)
            f.seek(211)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB[211:])

    def test_seek_backward_across_streams(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB * 2)) as f:
            f.read(len(DECOMPRESSED_100_PLUS_32KB) + 333)
            f.seek(737)
            self.assertEqual(f.read(),
              DECOMPRESSED_100_PLUS_32KB[737:] + DECOMPRESSED_100_PLUS_32KB)

    def test_seek_backward_relative_to_end(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.seek(-150, 2)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB[-150:])

    def test_seek_past_end(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.seek(len(DECOMPRESSED_100_PLUS_32KB) + 9001)
            self.assertEqual(f.tell(), len(DECOMPRESSED_100_PLUS_32KB))
            self.assertEqual(f.read(), b"")

    def test_seek_past_start(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            f.seek(-88)
            self.assertEqual(f.tell(), 0)
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)

    def test_seek_bad_args(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        f.close()
        self.assertRaises(ValueError, f.seek, 0)
        with ZstdFile(BytesIO(), "w") as f:
            self.assertRaises(ValueError, f.seek, 0)
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            self.assertRaises(ValueError, f.seek, 0, 3)
            # io.BufferedReader raises TypeError instead of ValueError
            self.assertRaises((TypeError, ValueError), f.seek, 9, ())
            self.assertRaises(TypeError, f.seek, None)
            self.assertRaises(TypeError, f.seek, b"derp")

    def test_tell(self):
        with ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB)) as f:
            pos = 0
            while True:
                self.assertEqual(f.tell(), pos)
                result = f.read(183)
                if not result:
                    break
                pos += len(result)
            self.assertEqual(f.tell(), len(DECOMPRESSED_100_PLUS_32KB))
        with ZstdFile(BytesIO(), "w") as f:
            for pos in range(0, len(DECOMPRESSED_100_PLUS_32KB), 144):
                self.assertEqual(f.tell(), pos)
                f.write(DECOMPRESSED_100_PLUS_32KB[pos:pos+144])
            self.assertEqual(f.tell(), len(DECOMPRESSED_100_PLUS_32KB))

    def test_tell_bad_args(self):
        f = ZstdFile(BytesIO(COMPRESSED_100_PLUS_32KB))
        f.close()
        self.assertRaises(ValueError, f.tell)

    def test_file_dict(self):
        bi = BytesIO()
        with ZstdFile(bi, 'w', zstd_dict=TRAINED_DICT) as f:
            f.write(SAMPLES[0])

        bi.seek(0)
        with ZstdFile(bi, zstd_dict=TRAINED_DICT) as f:
            dat = f.read()

        self.assertEqual(dat, SAMPLES[0])

class OpenTestCase(unittest.TestCase):

    def test_binary_modes(self):
        with open(BytesIO(COMPRESSED_100_PLUS_32KB), "rb") as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)
        with BytesIO() as bio:
            with open(bio, "wb") as f:
                f.write(DECOMPRESSED_100_PLUS_32KB)
            file_data = decompress(bio.getvalue())
            self.assertEqual(file_data, DECOMPRESSED_100_PLUS_32KB)
            with open(bio, "ab") as f:
                f.write(DECOMPRESSED_100_PLUS_32KB)
            file_data = decompress(bio.getvalue())
            self.assertEqual(file_data, DECOMPRESSED_100_PLUS_32KB * 2)

    def test_text_modes(self):
        uncompressed = THIS_FILE_STR.replace(os.linesep, "\n")

        with open(BytesIO(COMPRESSED_THIS_FILE), "rt") as f:
            self.assertEqual(f.read(), uncompressed)

        with BytesIO() as bio:
            with open(bio, "wt") as f:
                f.write(uncompressed)
            file_data = decompress(bio.getvalue()).decode("utf-8")
            self.assertEqual(file_data.replace(os.linesep, "\n"), uncompressed)

            with open(bio, "at") as f:
                f.write(uncompressed)
            file_data = decompress(bio.getvalue()).decode("utf-8")
            self.assertEqual(file_data.replace(os.linesep, "\n"), uncompressed * 2)

    def test_bad_params(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            TESTFN = pathlib.Path(tmp_f.name)

        with self.assertRaises(ValueError):
            open(TESTFN, "")
        with self.assertRaises(ValueError):
            open(TESTFN, "rbt")
        with self.assertRaises(ValueError):
            open(TESTFN, "rb", encoding="utf-8")
        with self.assertRaises(ValueError):
            open(TESTFN, "rb", errors="ignore")
        with self.assertRaises(ValueError):
            open(TESTFN, "rb", newline="\n")

        os.remove(TESTFN)

    def test_option(self):
        option = {DParameter.windowLogMax:25}
        with open(BytesIO(COMPRESSED_100_PLUS_32KB), "rb", level_or_option=option) as f:
            self.assertEqual(f.read(), DECOMPRESSED_100_PLUS_32KB)

        option = {CParameter.compressionLevel:12}
        with BytesIO() as bio:
            with open(bio, "wb", level_or_option=option) as f:
                f.write(DECOMPRESSED_100_PLUS_32KB)
            file_data = decompress(bio.getvalue())
            self.assertEqual(file_data, DECOMPRESSED_100_PLUS_32KB)

    def test_encoding(self):
        uncompressed = THIS_FILE_STR.replace(os.linesep, "\n")

        with BytesIO() as bio:
            with open(bio, "wt", encoding="utf-16-le") as f:
                f.write(uncompressed)
            file_data = decompress(bio.getvalue()).decode("utf-16-le")
            self.assertEqual(file_data.replace(os.linesep, "\n"), uncompressed)
            bio.seek(0)
            with open(bio, "rt", encoding="utf-16-le") as f:
                self.assertEqual(f.read().replace(os.linesep, "\n"), uncompressed)

    def test_encoding_error_handler(self):
        with BytesIO(compress(b"foo\xffbar")) as bio:
            with open(bio, "rt", encoding="ascii", errors="ignore") as f:
                self.assertEqual(f.read(), "foobar")

    def test_newline(self):
        # Test with explicit newline (universal newline mode disabled).
        text = THIS_FILE_STR.replace(os.linesep, "\n")
        with BytesIO() as bio:
            with open(bio, "wt", newline="\n") as f:
                f.write(text)
            bio.seek(0)
            with open(bio, "rt", newline="\r") as f:
                self.assertEqual(f.readlines(), [text])

    def test_x_mode(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            TESTFN = pathlib.Path(tmp_f.name)

        for mode in ("x", "xb", "xt"):
            os.remove(TESTFN)

            with open(TESTFN, mode):
                pass
            with self.assertRaises(FileExistsError):
                with open(TESTFN, mode):
                    pass

        os.remove(TESTFN)

    def test_open_dict(self):
        bi = BytesIO()
        with open(bi, 'w', zstd_dict=TRAINED_DICT) as f:
            f.write(SAMPLES[0])

        bi.seek(0)
        with open(bi, zstd_dict=TRAINED_DICT) as f:
            dat = f.read()

        self.assertEqual(dat, SAMPLES[0])

class StreamFunctionsTestCase(unittest.TestCase):

    def test_compress_stream(self):
        bi = BytesIO(THIS_FILE_BYTES)
        bo = BytesIO()
        ret = compress_stream(bi, bo,
                              level_or_option=1, zstd_dict=TRAINED_DICT,
                              pledged_input_size=2**64-1, # backward compatible
                              read_size=200_000, write_size=200_000)
        output = bo.getvalue()
        self.assertEqual(ret, (len(THIS_FILE_BYTES), len(output)))
        self.assertEqual(decompress(output, TRAINED_DICT), THIS_FILE_BYTES)
        bi.close()
        bo.close()

        # empty input
        bi = BytesIO()
        bo = BytesIO()
        ret = compress_stream(bi, bo, pledged_input_size=None)
        self.assertEqual(ret, (0, 0))
        self.assertEqual(bo.getvalue(), b'')
        bi.close()
        bo.close()

        # wrong pledged_input_size size
        bi = BytesIO(THIS_FILE_BYTES)
        bo = BytesIO()
        with self.assertRaises(ZstdError):
            compress_stream(bi, bo, pledged_input_size=len(THIS_FILE_BYTES)-1)
        bi.close()
        bo.close()

        bi = BytesIO(THIS_FILE_BYTES)
        bo = BytesIO()
        with self.assertRaises(ZstdError):
            compress_stream(bi, bo, pledged_input_size=len(THIS_FILE_BYTES)+1)
        bi.close()
        bo.close()

        # wrong arguments
        b1 = BytesIO()
        b2 = BytesIO()
        with self.assertRaisesRegex(TypeError, r'input_stream'):
            compress_stream(123, b1)
        with self.assertRaisesRegex(TypeError, r'output_stream'):
            compress_stream(b1, 123)
        with self.assertRaisesRegex(TypeError, r'level_or_option'):
            compress_stream(b1, b2, level_or_option='3')
        with self.assertRaisesRegex(TypeError, r'zstd_dict'):
            compress_stream(b1, b2, zstd_dict={})
        with self.assertRaisesRegex(ValueError, r'pledged_input_size'):
            compress_stream(b1, b2, pledged_input_size=-1)
        with self.assertRaisesRegex(ValueError, r'pledged_input_size'):
            compress_stream(b1, b2, pledged_input_size=2**64+1)
        with self.assertRaisesRegex(ValueError, r'read_size'):
            compress_stream(b1, b2, read_size=-1)
        with self.assertRaises(OverflowError):
            compress_stream(b1, b2, write_size=2**64+1)
        with self.assertRaisesRegex(TypeError, r'callback'):
            compress_stream(b1, None, callback=None)
        b1.close()
        b2.close()

    def test_compress_stream_callback(self):
        in_lst = []
        out_lst = []
        def func(total_input, total_output, read_data, write_data):
            in_lst.append(read_data.tobytes())
            out_lst.append(write_data.tobytes())

        bi = BytesIO(THIS_FILE_BYTES)
        bo = BytesIO()

        option = {CParameter.compressionLevel : 1,
                  CParameter.checksumFlag : 1}
        ret = compress_stream(bi, bo, level_or_option=option,
                              read_size=701, write_size=101,
                              callback=func)
        bi.close()
        bo.close()

        in_dat = b''.join(in_lst)
        out_dat = b''.join(out_lst)

        self.assertEqual(ret, (len(in_dat), len(out_dat)))
        self.assertEqual(in_dat, THIS_FILE_BYTES)
        self.assertEqual(decompress(out_dat), THIS_FILE_BYTES)

    @skipIf(CParameter.nbWorkers.bounds() == (0, 0),
            "zstd build doesn't support multi-threaded compression")
    def test_compress_stream_multi_thread(self):
        size = 40*1024*1024
        b = THIS_FILE_BYTES * (size // len(THIS_FILE_BYTES))
        option = {CParameter.compressionLevel : 1,
                  CParameter.checksumFlag : 1,
                  CParameter.nbWorkers : 2}

        bi = BytesIO(b)
        bo = BytesIO()
        ret = compress_stream(bi, bo, level_or_option=option,
                              pledged_input_size=len(b))
        output = bo.getvalue()
        self.assertEqual(ret, (len(b), len(output)))
        self.assertEqual(decompress(output), b)
        bi.close()
        bo.close()

    def test_decompress_stream(self):
        bi = BytesIO(COMPRESSED_THIS_FILE)
        bo = BytesIO()
        ret = decompress_stream(bi, bo,
                                option={DParameter.windowLogMax:26},
                                read_size=200_000, write_size=200_000)
        self.assertEqual(ret, (len(COMPRESSED_THIS_FILE), len(THIS_FILE_BYTES)))
        self.assertEqual(bo.getvalue(), THIS_FILE_BYTES)
        bi.close()
        bo.close()

        # empty input
        bi = BytesIO()
        bo = BytesIO()
        ret = decompress_stream(bi, bo)
        self.assertEqual(ret, (0, 0))
        self.assertEqual(bo.getvalue(), b'')
        bi.close()
        bo.close()

        # wrong arguments
        b1 = BytesIO()
        b2 = BytesIO()
        with self.assertRaisesRegex(TypeError, r'input_stream'):
            decompress_stream(123, b1)
        with self.assertRaisesRegex(TypeError, r'output_stream'):
            decompress_stream(b1, 123)
        with self.assertRaisesRegex(TypeError, r'zstd_dict'):
            decompress_stream(b1, b2, zstd_dict={})
        with self.assertRaisesRegex(TypeError, r'option'):
            decompress_stream(b1, b2, option=3)
        with self.assertRaisesRegex(ValueError, r'read_size'):
            decompress_stream(b1, b2, read_size=-1)
        with self.assertRaises(OverflowError):
            decompress_stream(b1, b2, write_size=2**64+1)
        with self.assertRaisesRegex(TypeError, r'callback'):
            decompress_stream(b1, None, callback=None)
        b1.close()
        b2.close()

    def test_decompress_stream_callback(self):
        in_lst = []
        out_lst = []
        def func(total_input, total_output, read_data, write_data):
            in_lst.append(read_data.tobytes())
            out_lst.append(write_data.tobytes())

        bi = BytesIO(COMPRESSED_THIS_FILE)
        bo = BytesIO()

        option = {DParameter.windowLogMax : 26}
        ret = decompress_stream(bi, bo, option=option,
                                read_size=701, write_size=401,
                                callback=func)
        bi.close()
        bo.close()

        in_dat = b''.join(in_lst)
        out_dat = b''.join(out_lst)

        self.assertEqual(ret, (len(in_dat), len(out_dat)))
        self.assertEqual(in_dat, COMPRESSED_THIS_FILE)
        self.assertEqual(out_dat, THIS_FILE_BYTES)

    def test_decompress_stream_multi_frames(self):
        dat = (COMPRESSED_100_PLUS_32KB + SKIPPABLE_FRAME) * 2
        bi = BytesIO(dat)
        bo = BytesIO()
        ret = decompress_stream(bi, bo, read_size=200_000, write_size=50_000)
        output = bo.getvalue()
        self.assertEqual(ret, (len(dat), len(output)))
        self.assertEqual(output, DECOMPRESSED_100_PLUS_32KB + DECOMPRESSED_100_PLUS_32KB)
        bi.close()
        bo.close()

        # incomplete frame
        bi = BytesIO(dat[:-1])
        bo = BytesIO()
        with self.assertRaisesRegex(ZstdError, 'incomplete'):
            decompress_stream(bi, bo)
        bi.close()
        bo.close()

def test_main():
    run_unittest(
        FunctionsTestCase,
        ClassShapeTestCase,
        CompressorDecompressorTestCase,
        DecompressorFlagsTestCase,
        ZstdDictTestCase,
        OutputBufferTestCase,
        FileTestCase,
        OpenTestCase,
        StreamFunctionsTestCase,
    )

# uncompressed size 130KB, more than a zstd block.
# with a frame epilogue, 4 bytes checksum.
TEST_DAT_130KB = (b'(\xb5/\xfd\xa4\x00\x08\x02\x00\xcc\x87\x03:\xaaYN4pf\xc8\xae\x06b\x02'
 b"\x8b\xee\xc6\xd0\x16o\xd6\xfd\xc5\x0bIi\x15}+&\x83'\xc7\xe9\xcd-\x869"
 b'\x05\xbexe\xa5E\xb8\xb0 \x9c\xb5\x81\x92\xb5\x81 {\x92c`\x02\xb9\x04\xd7'
 b'\x04\xdb\x04\xfe\xe0\n\x14(pK\xe2\x17\x9fYk \xc2\x8c\xbb\xaf\xc0\x1d\xca\xaa'
 b'6L\xcd\x8a\xd8}E\xe8\xa9\x16,\xdf=7u\xc6\x9a\xb4\xef\x9fq\xe7\xf2\xda'
 b'\xa8\xd0\x9b\xddwO\xff\xef\xb66\xf4\xf0_\x17\xc7\xe4\xedY~\xcd'
 b'\xac\xad\xf7\xcb\xaa\xa8\xb4\xa8\x8c\xb7\xfbv\xfb4\xcb\xbbMA\x0c='
 b'\x0f\xf9\xba\xb4(g\x1ah\x16\x13\x7f1u\xbc\xb1h\xf2k\xa2*b\xc7\t='
 b'\xbb\xdb\xa6\x95\xd3~\x14w{~y\xebm4\xa2W\x931\x92\x9f5\x08d\x821\x18]D'
 b'8\x83\xd1\xc5\xc8!\xe8\x8d\x18\x8dF\xa5\xa7\x97\x9a\x88\x11\xef\xf8\x17'
 b'GJe\x84xUY\x16e\xf9\xc5\xe1`P/ \x1e\xe1\xd5\xb7O\xc3`\x95\xe5\x9e[?'
 b'+\xbd\xd5\xc2\x9e\xfd\x07\x10\x12\xa8\xcc\xc4C\xf3\xc8\xb4/?\xcd\xf8'
 b'\xd2\x9c\x88a\x98\xea\x10\x13L3\xb9XNu\xa6\xfd\xd2p\x87\xe35\xb7\xb1\xd6'
 b'pKB\xf5\x05\xe2Tc \x90\xea\x10\x11\xd5!\xb2K\xa5\xa8\xa6\xd8\xc4C;\x7f\xdb6n'
 b'I\xaa\xf5:\x8c[\x92K\x84w\x95\xde\t\x0f\xad\x95\x15\xac\xb9\xde\x1aj>1'
 b'\r\xady\xeb\x0b\x06s\x06\xf5\xc2\x1f\xaa\xeb\xadk\xe9\x1ds\xb9Dx\xa6\x909'
 b'\xc6+\x8a%9M\xed\xf9Q\x9c=\xbfx5qKR\xbbJ\xfd\xa2Z\x7f\xf8\x13\xd5}\xb1'
 b'\xe6\xca\xbc3\x9e\xd0\x9c\x88\x900\xab_\x95E=\x1e\xf4s\xfd\x1c|\xfeQ\xb5'
 b"\x98\xfe\x1dj.'\xf7\x8b\xe6i\x9e\x16I\xbb\xf9E\xfa\nZ\xfb\x0fd\x11\x05"
 b'\xf7\x8c7\xe7x2\x98\xc6\xe3\xa6a0\xcar=q\xf6\x18\x88d\xaf+\xe9\xb2U\x82\xd2u'
 b'\xcd\xbfm\x9f\xb6_4\xf9l\xfc\x19\xe7\x89\xf8\x14\xcfz\x13\xec\x1b\xfe\xc8/l'
 b'\xf9\xdb\xa7\x95e_"f\\Q\xdd\x19{\xdec:\xbd\x06\xaa\xfc\x9a\xdejR'
 b'\xd7\xbf\x16\x95\xc3/\xca\xc9{g2\xb4\xac63k\xfe\xfb\x07\xa2\xa3\xb2\xf2\xd6'
 b'\x8e\xb5\xeb\xf7B\x12\xb6V\xeaJ}\x7f\x9a_\x0c\xf6\xad\x17\xaf\xe5t\x97H\xf6'
 b'\x8b\xa2\xd6\xd2\xce\xd03=t\x96Q"\x05<\xb4i\xaa>M0\xbf\x84?\xca\xafu_\''
 b'\x86?\xd2\x9d\xd6]\x01\x1a\xd4\xef\xba\xbd\x9a\xa7\xd6>\x1d\xbd.\xfc'
 b'\x91\x0e\x7f\xd4\xfd\xe6\xec?\x10\xa9\xfd0\xa7\xbd\xa2\x04\x90\x01\xd2\x99'
 b"k\xd2Y6\x89\x14\xe0\x1b_\xbf\xf2\x8b^\xf3\xad\xbf\xce'\xd1\xc5\x14\xa1\xa7A"
 b"\xff\xad\xd7q6\xee\xc4\xd0\xb3\x91\x88\xa1G\x943\xb8\x13)'\xf48\xfc\xc2\x94"
 b'\x95u\xbe\x07\xf2\xbe\x11\xc6\x19\xaf\xedg\xf9V\x93\xa1\x9f\x9b[Vl2\x8f\xd0'
 b'\x9f1\xf5\xd9p&8\xa1\xceF"\xea\xcf\xbe\xed\xa7?[~\xed[\x11 $D&\x98\xae'
 b'\xdc\xf6\xfc\xdc\xc6\xde\xcf\xd2\xfb\x95\xce\xedJrm\xab\xdc\\[+\xa7?\xf6\xbf'
 b'\xd8#\xf4u\xdd\xf6\x93\xdbS\x7fn;\xbd\x1f\xde|?\xeeg\xd9\xf9k\xccm'
 b'\xdf8\x1e\x89\xdc\x16e\xec\xee1\xc6\x08\xf6\x0e\xe7\xcd\xff\xb3\x12\xf4'
 b'\x07\xeb\x96\xa2\xbf\xd8\xc5\xd7\xa5\xeby\xbf\xcd\xf7\xad\x9cs[\xf4\\'
 b'\xc8-\x89\xd7a\xb0\xee\xc1\x03\xaf\xa8\xfb\x14Z"\x88\x08\t\xfbV\xff[\xb7\xa7'
 b'\x04P\xc4\xed\xe9\xfd\x08\x10\xdd\xeay\xb2"\xf4\xdc\xb7\x95?x\xe0\x99_0\xd4'
 b'\xce\xaf\xb5\xbc\xf8}\xeb\xdc\x16\xdd\xb7\xd1\x81\xc6`\x9d;\x1c\xde\xe9'
 b'\xa8\xa5_\xbc\x9b`\x9d\xe5\x9abn\x7f\xc5\xcf\xfb\x9f\x83\x07aT\xd0\x8e\x8fQ'
 b'\xb5\x8e\xa1\x07\x04\xa9\x89\xcdG\xd3\xe1\xc4\xd0S\xf9\xc5\xc1\xcb\xc51'
 b'\x04\x88-\xa7\xb0_\xec\xfa\xe2\xbae~\xcf\xc2-I\xc6\xf4\xb7\xee\x0fg\xb7\xf2'
 b'\xd6}\xbf\xfbDY\xfa\xd4\xfd\xd6!Htk\xde\xa0\xfd \xaf\xaa\xd8\xa0|\xab'
 b'\x17\xffm9\xad\x18\xb4\xf6\xbb\x19\x08\t\x10\x14\x14\t:\x10\xd5w\xf2Foc'
 b'0j\xe3\x19@(\xfa\xb5y/\x0c\xc5Y\xda\x84\x1ej\xcb.\xe3\t\x84\x04\x03 $T\r'
 b'4|\x89tgy\x96\xdc\xf4\xad/\x9eTDH\xb0B\x8f\xcf\xea\xb7\xca\x9d\x7f'
 b'\xfa\xcd\xdf\xfeL3\xe6@nI\x10\x12\xb2\xf7y\xdf*\xba\xd8N\x1b\xde\xaf\xb7'
 b'\r\xbbD\xe2\x18.\xb2=\xa5[c\xb8\xc8{\xe1\x9e\x11\xa1\xcd\x81\x08\xa2\xf23'
 b'\x17\xfa-\xb7\xa6\x9f\xf37\xa7E\xccy\xa33\xce\xf9C\xcfZ\xa9y\xb0\xea\xfc'
 b"\xcd\xffl\xa2\x95\xe0\xcf\x8a\x1a\xcd\xe74\xb1\xf4\xf4rBOt\x89\xc4'.~"
 b'\xc63\xf4&.r1\xb7C\xcf\xe4O?;o%\x00!\x01!Abyu\xf1\xb6\xdf\x84w\x15\x00\x8e'
 b'\xb7\xeb\xd1\x95\xdc\xf6\xf0\xca\x8e\xf2\x9fr\xcb\xbf/\xc7=\xe3\x96$'
 b'\xf3\x02\x13\x06\x85\xc9D!S\xa0P(\xd9dF\xf6\x94ykM\x16\xc8\xb2\x02Yn\xfd\x15'
 b'\xa8x\x81\x8c\xb2\xc0\x90e\x05,\x15JV\xa9T\x14\x18\x14&\x05\xb2\x02\x0c\x0c'
 b'\x0c\xd9B\x96\x15\x90\xe8=\xbf\x81f\x11\x07D\xb7V[3,UU]]\x1f\xa0\x7f\xfd\xc2'
 b'\xf7^\xec[\xd5\xd11\xc6\x9f\x7f\xf8kY\xfeV\xf1~\x92cP\xc4\xaf\x04%\x17E\xf7='
 b'\xbf\xfe4Ui\xad\xd1\x15\x85\xaf_\x93\xd4Zk\xad\xb5\x9eU"\xf4\xe8\xabd'
 b'\x994\xf8Ey\x98\xdc\xdd2\xc9&\r\xfe\xe0\x81S\xa8\x86\x96\x9a\xefk\x00\x87'
 b'\xb0\xccd\x11,\xb1\xa10\x90\xc0B"\x822V\x82\n\r\x0e\x16J%FtV\x89\x140'
 b'Y\xed\xc3t\x82\x82\xa7\x8arP\xf4f$F\x91\xa0\xe3Y\x0e\ne\xce\x19L'
 b'\x1d\xe8\x802WV\x8fJ\x96\x95\x168<\xa8,\xed7\xeb\xce\xd2\xf3\x8b-\xa7DwK\x99'
 b"w\xe9\x1dS\x03\xa1'\x9b\xf8\x85o}mj\xe8JD\xdd\x92l\xcc\xcdk\xeb\xcf\xb1\xc6-"
 b'\xc9\x1b\xc0q\x9c\xf7\xcb\x1b!\x81b\xb8n\xf9\xf5#\xffg\x05\x99\x0e\xa7"\x86'
 b'\xe2\x86\x00\x1c\x10(\x0e\xc0\xe3\x97+\xaa\xa0\xa8a\xfa\xb7v\xf9\xf7'
 b'S\x9c\x1f\xc3\xdd\xe5\xe7\xe0\xaf\xd4ok\xc6\xcf5\xbe\xce\xbam\x9fv]\xab\x9d'
 b'~\xf5S\xec>X\x0f\xdc\xaf\xf4E\xf2\xca\x0e\xc3\xbc\xc1\xe9F\xc6'
 b'\xfb\xc3\x9f\x1f\x9f@\xce\x7f\xbf\x9c\xf3o\xb5\n=|\x856\xa0\xb8\xa7\xcc\x88`'
 b'\x9d\x1f\xf4\xcf\xdf\xfe6\x97 \xee>\x87\xb2\x9bf\rw\xb5U\x93\x93G&\x9f'
 b'\xbd\x97\xb8Y&\xb0\xe1\xc7\xe3fI\xf2\x07\x0bC\x85aB\x80\xff\xa75\xc7-'
 b'I\xe5\x94\xc7\x18\xa7i\x9a\x1a\xa5\xa7\xa5\x97\x9f\xbd\xfcW\xce-?'
 b"\xdb\x95[\xcb+5\xddo\x89\xb5&\xe5\xfe2\x07\xa8\xe0\xe5@\xbc\xaa\xb1'\xe2"
 b'\x07\xec\x93\xda\xd4I\xe0\x16X\xc0\xe4\x07XN\xbf\xce-\xcd\xb7\xdc'
 b'\xb8\xe3\x96dk\x90H x\xd9\x1a\xdb\xb6M~\xb9\x1c0a09\x7fd\xe9r\xab\xe7r'
 b'b\xad\x1bM\x86\xc2\xd3\xe1\xd4Z+\xbdu\xe4\xdfI-\xa5\x87\xf6\xdf\xd2+\x11'
 b'\xcc\xbaU\x8a\xbb\x8b\x13\xd5l\xe5{\x9f\xeb\xc7\xae~\xf3{\xcfa'
 b'\x10\xfa\xd6\x99\x1fO\xc7\x1d\xf7\x08gm\xddB\xbfj\xf6p\xf6<\xa9%\xc7\xf9'
 b'\xde0w\x8f\xf8\xad\xd7\xc5\xf7a\xefc4\xa5\xb6q\xd6\xc3n\xf50\xfc\xc2 '
 b'aO\x01\x99\xde*\xbb\xff\xfc\x97\xf7\x7f9$\x91<\xad[\x95\xc8\x18\xdb\x89\xe9'
 b'\x80\xc9\xafR\xcd[Z\xa0_$\x12\xa9\xeb\xfc\x02+\xa8\xca\xa2\xfc\x9a|\x9b<'
 b'\xb4^\xdd\xf6\xeb,\xee\xbd\x1f\x9e\xd7\xc1k\x17eIm\xf9\xde\xe7\x08\x992\xac'
 b'-\xe7\xc5\x13\x02\xa4\x94\xd2\x8a\x9a(\xc5\x1dX%\xb0Ic0\xf9\x13\x111Y'
 b'\n\xc7$\xa3v3\x05\x98JQ\xbb\n\xaa\xe9\xc1\x145\x8b\x08Qy\xd8\x00^Q\x9aN\x82'
 b'\x898\x80O\xa6\xc31\x80q\x81\x15E\xc2\x9ee\xfd\xc5\xc0\xc0\xc0'
 b'\xc0\xc0\xc0\xc0\xc0\xc0\xe80\xfc"\x81\x1d\x89\xd4\x81\x1d\x06\xa9\x84A'
 b'\xea,\xbf\xc0\xcer\x8c\x8b\x84\x81q\x81$\x03\xa6\x05\x15\xa6\x93\x9f'
 b'\xb7\x8e\xfb\xf3\xf6\x87#.o\xeb6]\x98\x17I\xad\xbf\x8b\xa0\x16'
 b'\xf8\x95\xdf\xf9\x87C\xa7U\xc2#\xd3\xbe5{\x93\xdb\x0e\x83\xd9.v\x18\xac\x02'
 b'+\xca\xebf\xde\x1a\xd4\x84\x9e\xbdUN\xe7\xa8\xdd\tiz\xa84\xfd\xfbM\xd8'
 b'\xf2\xe8\xe1[5\x89M\xa8\xb3\xa9\xd8Px*8!\x8bN\xec|\x12\x846\x9f\x18zH$'
 b'pW\xc7rV\xa5\x12\xc9/\x90"y\xa9"i\x1fHs"\t\x04/$\x12\xa9\x02A\x8d'
 b'\x8b\x04\x96\xa2\x87I\xe0\xc4\xc3\x11\xdc\xb0\xcb\x8aT\x91\xc0\xfb\x1c\xc9'
 b'\x9d\x81uq\x81~1\xb0.*\xd2\x05R\x1e\x8e\x90\xaa\xf4\xfan\xeb\xbe\x9f\xd3'
 b'\xafy[<hN_\x7f\x9fM\xa8bpQU\xee\xa0*K\xa3,\xca\xab\x8d\xad\xee\xa2v'
 b')\x8fE\x87c\xa0*\xf9U\x95\xa8\x90\x05\x05(\x1a\xe8`\x0f\xb3\xbc\xd5\x80['
 b'\x92-\xb1\xdd\xb6v1\xd8\x9dvuK\xef{ah\xf2\xaa\xa1\xdd\x8f\xaa\x13\x97'
 b'+\xa3H\xdf\x11]\xfd\xd1\n\xe2\xec9\xbe\xbeq\xf6\x9e\xb2\xb4\xa9\x10\x84\x0et'
 b'6\x141\xb49p\x89\xe8\x8b\xbb\x0eOnK\xcf\xb7\x96\x13nI(\xa2+\xf3'
 b'\xd7\xad\xfa\xe4p\x84\xdb\xeb\xfe=\x1d\xab\xacy\x9a\x07\xdaHp>!\x10\xe5\xf0'
 b'\x8bKt$:\x93\x81)\x94\xa9\xf8XL\\\xbc\x81\x861X\xa4f\x92\xc5\x84'
 b"\xaa6\x14\x062!\xce'\x01\xa7\xf6[\xac\xb5\xcb\xe5!\xb4\x17S\x89\xb7\xcb\x81"
 b'\xa0Z?\xb5\xb6Nd\\\x9a\xd2X\x06\xe8*\xa7\x8fF\x19\r\x12\xb6[~\x10\xcf\x87\nc'
 b'WR\xc6\xf7R\n\x14(\x88T\x8f\x89\tw8\xfc\xa2\xe4\x96\xf4\xe7g\xc7\x9d'
 b"v\\\xa7\x88\x08\xf5Z\xbe\xfd\x8f\xc5':&\xe2D\x02\x03\xa1\xc7\xe1\x97^0"
 b'\xfd\xcc\x1f\xd6N\xaf\xf4[\xa7\x86\xb6\xe8\xcc:\xce\xac\xb7~*\xb7\x94\x08=L'
 b'\xfd\xe7\x89\xeb\xba\xf2\xf6\xb6G\xf9\xdb\xca\x91$~\xf1\xc8[\xadj\x8d=\xff,'
 b'1jW\xb7\x87\xdd\xca\xfc\xe0kj3&\xd1\xad\xe5\xf6\x9a\xe8V,\n\x05\x13'
 b'\xc9\xa00\x19\x18\xb4\x8aB\xa5\x92i\x0b\x9a\xe5+\xff\n\xd2AA\xd2\xcb\xfe\xbc'
 b'\x07\x06\x1b!arL>M\x8e\x90\xc0`\x7f\xde\xadv^\x94\x9e\xcb[\x87\x9e\xeexEa'
 b'`\xa0X\x14,\n\x0b\x15\n\xc3\x82e\x81B\xf9\x1dN&\x99\x1b\x00D\xaf\x16]\xfdwV'
 b'\x9d\xa7\xae\xd4\xdb\x8e\xfd\xa2\x91|\x127k\x96y\xd3\x10E\x82\xcc\xc4F"\x82'
 b'\x0ed(&<\x1a\x8b4\xa7%\xe7\xb8\xa1\x96QK\x1d3\xde\xf3\xc1\x89\xad%'
 b"\xc9\xa2o\xf8\xa2B\x9c\x0e'Jd6\x08b\x96\x02\x08=\x8d\x8c\x0c\xe6\xd7\x9f"
 b'K7_\xd9\xc5\x0b\xe0\xd7\x03\xbf\x1cN_\xef\xe7B\x11\xbfJ\xae\x11\x12\x16\xdc'
 b'\x05\x18\x0c!\xe1\x9a\x98F\xea\x93\x11\xc0\xc4\x12\xb3\x00\xa5\xd2\x83\x8c'
 b'\xb1F\xb9\xc3%\xe5\x97\x0ci\xb2\xa1\xc9+#\xdfq\xbb\xe6\xcc\x08\x8fp\xa9\xe4'
 b'\xf0k\xe2W\xe6\x97\x1eM\xe9\xdd\x04\x8d\x89\xd24cR\xf8\x08\xe0N\x14\xe5\x0c'
 b'%\x8dDY\x92\xfe\x92\xfeB\x8c0\x15z\\jm\x00u3e\xc0\x97\x11\x12\xa6ib\xf2'
 b"\xec\x7f1L\x18\x16,\n\x95If1\xd6B,\xd1\xb8t\xc6\xe7OfC\xa1\x89\xa1'\xeb"
 b'\xccD\x8c\x90\xd9@\xadp\x0b\x89\x9b\x9f\xf6l\xe2\x1eY\xb0\xbc\xa5\xd2`ij'
 b'\xeb\xa7\xf9\xae\x1a\xb6`\xf1[).?(;n\xca\xcf\xf8Ey\x99+\xf3\xcb/\xfeWF'
 b'N\x7fv\xc3`s\xca\x8a!)\xdc\x92Li\xf9\xae\x97\x13\xb7\xf7\xdaR\xb7b'
 b'\x00L\x93\xf7\xda{ME\x1e\x0fm\xbfx+n\x80\x90 \xab\xfd\xbaoN\x06\xcbB6\xc9'
 b'\nd\x14J\x85![\xa0,P\xb2J\x96}s"$dT\x16\x83\x0b\x8d[\x16\x95\x9f\''
 b'6\x84\x04\xbf\xae\x86\xc3\xaf\x0c\xddD\xb7J,\x88K\xbc\xaa,\xdf0\xe5\x94('
 b'\xcbyY\x9b}\xed\x96\x87C\x96\xe5\x9e,9M\xa8\xe5-\x04JPA+\xf0>(\xca\xf2'
 b'\xe1+eIjI\xd7\xb8t\xac+j\xc3[\xda\x89\x0cw8*\x8b\x92\xd8\x8d\xb6r\xab\xf6'
 b'\xeb\xadR\x1c\x0foP\x98\xff\xcb\xd6V\x92W\x91K[\x8e]\xfa;M\xa6\x8c\xf7\xe4xo'
 b'\x9e-\xb7\xf2?\xa0\xf0r\xf3zh5\xa9\xe1\xeci\xfcD\x99L\x15\x85\x90\xa0'
 b'9\xd1\x92\x8c\xbe\x1c\xd2\x9c\x11\xce\xff\xa0|\x8a\x8c\xdd\x92T\x08d'
 b'\x9a"\x9bJ|\xdf\xc3V\x8a\\\xba\x17~\x02nI\xba\xfa\x05\xc0-\xc9O:c\x8aO\x8d'
 b'\xeaUu\xf8UYN\xed\xcfv\xd6\xf8X\xc2-IF\xbe\xaaz\xe0\xde:y\xee\xe6{\xb9'
 b'<\x8c/\xdf~\xeb\xddAX\xf9\xf7&-\xff\xe9\xe1L\x15H:\xfc\xa0\xab\x825?\xb5\xbc'
 b'!\xd1\xd9D\x87\xc7\xaac\xc1\x01}\x12h6\x9f\x98\x80\x05\x05E&\x86\x1e;]vx\xeb'
 b'o\xba~\xe0\x9d\x80?\xad\xf3\xe9u\xbc\xe7{\xa5\x7f)\x92nI\x92?Ir!\xf7.\xdd'
 b'8\xfb5\xbe\x0f\xda\xfav\xd5\x8eI;t\x0c\xban\x95"\xe9\xd7\xfa\xb69\xd2'
 b'\xb2\xd34\xbc\x19\xffl\xcd\xaf\x98\x02\x01n\xb1\xa0@\xd9\x9fV\xbd'
 b'z\xc4\x18\x1f~i;\xa9\xbc\xb7\x8cL\xdc\xf2_\xf0\xb0\x8a\xb0\x8d\x96\x84\xd2U'
 b"W\x1d\xfe\xe8\xa2('b\xf4\x13\x14\x10\xa1\x1ck\xa5\x06\xef\x1a\xf7"
 b'}\xca\x89\xd8F-#\xc5\x9a^\xad\xc3G\xc0\xb3\xcf\xb9\xb4\xb2r\xbck\xb7\xeb'
 b'\xe7`r |\x04\xb4D\x90A\xa0\x8ceeI0\xc6\x18c\x9dA\xe2\xdc\xba\xa5\xa7i\x96'
 b'\xa4\xd1\x94\x06B\xa0\x8c\xa6\x93\x80\x85D\xdcLd@\x1av\xa0\xdd\xe1p\xf0\x0e'
 b'\xb4\x86\xf5\xad\xb2r\xbc\x9f\xea\x04ne\x0e\xa1\x91\xe0D\x1f\xce\xdc'
 b'\xb6$%\x7f\xa8JT\xa41A\xa0\xc9l>\x9d\x041\xf4\\\t\x08D3qsW\x92\xc6\x04`\x13/'
 b'\x8b\xb1\x81\xcf\xd2\xeb\xb0\x86\x9b\xf5\x13\xe7\x84\x80\xa0\x1c\xbcv\xf0:'
 b"K\xbf\xbe]\xf4=Of\x92s3\xcb\x07Ad\x0f\xa0\x0e'\x13\xeaXhB\xac\xadt\x88"
 b'\xeb\xfb\xb5C`\xdf:\xd7\xcd7\x8ce\xee\x0f\n6\x12\x1d\xce\xad\r\xb4\xae\x12'
 b'\xe0\xfe\x10\xea$\xb0\xd0D\x04\x9aOf\x03\xfa\x0c\xc0\xf3\x1f\xf7\xc8'
 b'\xfb\x05\x82]\xde\xba\xc6\x9c\x81\xbb\xb4\xb1$`~@H\xd8\r\xaeGx\x03Q'
 b'\x96\xd61&m\xf5\xf3\xab\x01U\xb1\tqbh\x03\xba\x0e\xea?\xb1\xba\x14\xc7'
 b'`\xbe\xac\x80\n\xc5)\x95\xbf=\xd4.\x0cr\xa7\xf7\xb7\xef\xaa\xb4\xf33\x86]'
 b'\xd9\xe5\xf7t\xbd\x9f\x9c\xaf\xe5]I8\x8b<\x14\xfd\xc6\xaa\x1dI\x7f}\xc7\xdb'
 b"\xa0R\xbb\xf4\x9d\x98\x7fs\x1a@ \x0e\xe1\r\xa8*'@\xe9\xe9\x9a\xeb\x96\xf9"
 b'\x0f\xe8\xcc\xd6\x95\xe2>\xfe\x92#\xd9\xb9\x0e%I\xe6\xcf\xcf\xb9v\\?s~'
 b'\xe9\x8aiiY\xd2\xdd\x7f\x93\x9a\xe4$|G$0\x9c\x7f\xe9\xd7\xb2Z\x0cl'
 b'\xe0\xfb\x13\xb9%\x81\xb8\x15X!v\x05\xad\xf7\x85\xecKh\x90\xd6'
 b'\xba\xea\xfb\xb9\xae\rJ\xa58\xda\xeb<\xed\xe9\x86G\xa9\x93Y-h\x7f\xcfm'
 b'\xf7h\x9f\xa6.~?\xad}\xda\xbb\xb4{e\x81\x95\x02\xa5\xb2i\x93\x85\xcd\xc1'
 b'b\xa14l\x0b\x14\xba\x90I\x07ZiP\xd8&\xe5\x15\x14\x1a<\x1d\xc1\xb4$;w\xd7\xe4'
 b'\xfc\xad\xbbH\x17\xf5\x9b\xc3\xd1\x802~\xb1\xe3\x9dqW\xed\xd3\x8b'
 b'\xbd\xd7\x17\xb5\xb8\xb2\\\xdb\x18&\x83\x82\xa5\xa1\xc1\x81:0(H))\x93\x05'
 b'\x87\xca\xa4\x0bs\xa1\xa1\xc1A\x81ZL/j\xb1\xa4|\x82u_WK\xb2\xe2\x81\xf4\x97Z'
 b'\x8c75\xa9L6M\xdb(t\xd2 +\x14\x87\xcaW&\x9a\xa5\xb298P\x06\x0be\xa3'
 b'\x13\xbc\xbb\xbcY\xb8\xc3\xdb\xb7t\xdc\xe5\x8d\x14\xd2\x1f\xde]>\x00'
 b'!\xc1>\xc5Ju\xa2b0\'VYn\xa9P\xe6\x05\x04B!\x00\xcaT|2\x08\x1c"\xc30\x87\xc0'
 b'\x0e\x87}\x1a\xa9,K\x852ed<\x05\xfd\x02-\x15\xcaE\xbc\xf1\xaa\xd1\xf2'
 b'\xcb\xd2\x1c$\x03eB\x17\xa8\xa5\xe2\xb0m\x9bea\xe1\x17\x18$eN\xb2\xad'
 b'AZ\xb4\x8f|\xb6\x12\xeb=\xa5?\x1e\x9aO\x978)\x1d\xb1T(\x1b\xd6\xa1'
 b'\xdf\xd2^\x0e\x9ae\xa3h\xd9\xa4\xe1\x19(\r\x93I\x15\x1c\x18\x9e:0L\x8d'
 b'\x82\x90Pa\x0f\x17\x18\xc4/L\x8c\x14\x0b\x85\xd2\x97\r\n\x92J\xd9`q\xc8'
 b'\x9e\x92U6\x86\xaf4T\xa6&\xa7\xc5\xca[E5c\x8f0x\xa8.8[\x15I\x1eJ'
 b'\x95\x9b9\xbf\x83\x94sj\x93lf\x1a\x83C\xc5BQ\x98\xcc\x85\x86\x05\xfa\xdb'
 b'\xd4\xb6\xd9`\t=l\xc0\xbd\xd0\xc3\x9b\xce\xc2\x94\x0c\x0b\x0bO\x1d'
 b'^\xd2\xb7\xd0\x9f\x96\x8aC\xf6\xf4\xa5\xe57\xca\xac4Dt\xf7\t\xb7\x9aE\xb8'
 b'\xd3\xb3ZOo\x92\x04\x15!MF\xc1&"\xa0\xd9 \xd0\xc4G.Q\x14\x02\x99\xcd\xc7\xc0'
 b'\xa6\xc3\xa1\xd8h2\x1e\x10\x88\x93\xc0\xa6\xf3\t\x81:\x1b\x8a\xc9\x84'
 b"\xc5'\x83@\x13'\x08  j\xd5V\x13\x94\x01\x0e\x85\x0e\x812\x13\x18\xe5\x99"
 b'2\xf0\xe6\x93\xf1TXh\x10h8\x1f\xed\xff\xfb\xca,?\x91W\x97\xc6-@'
 b'\x1c\xa7\xbc\x8e\xba\xf4\xc3\xfef\x8c\r\xc7?i\xbf\xb6\xe9\x04`\x13'
 b'\xf3\xcc\x0e\xbf\xfcb]\xdd#\xfe\xe1\xf5\xcb\xeb\xa6\x8e\x1e\xae\xack'
 b'\xd2\x1b\xd1\xad\x11\x83U\x94\xa8n\x17k\xf6\x1f\xf0\xf0\xd6~\x81\x93'
 b'\x85*\xdbJ\x99;|R\x17zWQ\xa5\xa5\xe7b\xe8)m\x0c%\x7fxD\xf6(=r\xbew?\xf6'
 b'c\xc1\x82\xc7\x82\xc7c\xc1\x9c\x95\x8ar\xcc\xb1\x9d.=9\xf5{\xa9\xc38o'
 b'\xfd\xc8 \x10\xcf\xb2\xa6\xc7\x82\xe9\x01\xd9Y>2\xc4\xebOT-~\x81,\xb8'
 b'\xc4+\xcc-\x8e\xb9[~Y\xa4\xbf\x13\nu\xdf\xe6\xad-nI\xaa\xad\xb1FMu\xfb\xec'
 b'\xc5PGN\xbf\xf1\xe7\xa0\xd3S\xae\x1e\x9e\x1ac\x15!a~\xda\xfb&\xd8\x04r1iP'
 b'\xae?\xc9\xdd\xcf/\xee\x97\xae\x16529D\xd5\xd8\xfa\xb5\xbc\xe9_Tg\xfc'
 b'^\xf2\xd6U$+\xe8/\xcar\x9a&\x03\x1e<\xa8\x1a\x1b\xa5\\\xef\xfb\xbb\xb2'
 b'\xa8\xea\xa01\xd0\xed\x9fB\x990\xc8\xc9\xc2d\xa2\xa05l\x94\xe9\xb0`Y\xc8'
 b'\x14&?\x17\xa2~\xc0\xf3\xbe(\xc7\xb8kdr\x8aQ\x80{\xdd\x14aU;\x8e\xee\xc7M'
 b'\xff\n\xe2\x8aj!\x8ea\x8e\xb1\x10\x98c\x98\x05\xc1\x14w\x1e\x83\x89\xa0(\x95'
 b'\x9d?\x12\x89P\x1e*\x17\x9a\xce\xd0\x9e\xb1vT\x94\xce\xf2\xaaV\x82\x8d\t\xa4'
 b'\xfaUk\x85\xe1\xb0\xe5\xb0m0\xa8\xdc\x03\xb6\x17\x9a[\x92\xca]\xf9\x7fta'
 b'\x1e\xf1@R*GX\x85qjI \xf2\xb3w+\xde\xbaFF\xf7\xcb\x9cv\xc7V\xdb\x1b'
 b'\xe9\x9b^\x99\xdd8\xf9\xc3\x15\x94\xdcS,\xf16\x1c\xcd\x9aw\xf5'
 b'\xee\xa1\x81\xa1\xe2\x00\xe1\x1cs\x88;\xc4\xb1\xed\xbe\xc3\x91\xf47\xc3'
 b'`\x1b\xc3`\x18\x86a\x11\x0f\xdc\xfd\x01\xb5\xd8\xb1u\xf7\xcc\xdd/'
 b'\x98\xeb]\xe7\x95 \x95\x1ej\xa3[3\x87-\xe6\xd61\xaf\x9c_\xbcr\xd8\xde'
 b'j\xe3~\xad5\x83\xfc\xcd\x0b\xc87/1\xeeK\xc4\xd6_\x03\x9aq8\x1c\xf9'
 b'\xbb\xb6\xde\xda\xafZ\x19\xd4\x8a\xa2j7\xd9>m\xfb\xb4zY\x95Avq\xbd'
 b'\xee\xbe\xb3.\x12\xc7x\xd8e\x0c\xf1\x0c\\a\x8c18k\xb4[\xbb\xd6\x1a\x9a'
 b'|pM\xca\x88\xde\xea\xc3V\xb7\xfd$\x12\x08\xe6R\xc3\xfb\xa1iRj\xa0\x04'
 b'A\xbf\xa4&/\x8fT\xe8\xb9\xb4\xc5\x1f\\\xc1\rp\x07\x8f\xc0` \x0e\xe1}'
 b'\xfe\x14W(\x93\x8b\xaa\xf4\x0en\xcd\x80\xb8$L=\xe3\x06\xb2\xc2-\x89\xc4#'
 b'\\c\xce\xf1\xbe\xef9O\x1c\x02i\x84~\x89\xc0(\xdf\xb1\xaa((P(.'
 b'\x92\xf7\xb3\xb6\xa2\xb4\xe5\x91\xfe\xd6\xff\xc9\xd8\xd9\xf2\xcb'
 b'\xad2\x87\x1e\xd9\x82\xc7\x85\xbe07j\xf8\xde\td\xbf\x06\xdf\xf3\xe9jp\xa8'
 b'Q}^\xae\x12>\xa1\x9f\x1f6S\xberb\x98.}l\xa0\xe1\xaa\x81VY\x95W\x96O'
 b'\xd4\x8b\xae\xcc~+\xde\xd3R\xa1\xf8\x05\x13a9\xfc\xa27\xb3\x89\x10L\xd3\x85'
 b'\xe8\xd6\x98\xbd\xc3$\xa6\x9a\xa8T\xb8v9\xc9\x14\xcd\x00\x00 \x00'
 b"$\xd3\x10\xc0 00 \x93\xcb%\x13\xc2\xac\n?\x14\x001+\x1f\x16:'$!\xcc\x04"
 b'\xb2,\tr\x18E)\x83\x8c1\xc6\x10B\x08234D\x83\x01\x90H\x12\xf3\x84\x19\ru'
 b'Xi(\xd5/\x98\x9a\x08\x87aZ\xd8\x07.\xd2\x15\x9eS\x92o \xd5\x8a\x03'
 b'\x0cS\xf5\xdcH\x16Lk2\x07P_\x12R\xdfs_\xd3\xffB\x8b\x1f\xc1\xe3m\x8b\xd8\xce'
 b'\xec\x08\x9a\x8a\x00#\xd0\'\xb0o\xf5\xc0\xaa\xcf\x0e\xdb\xa8$\xf7b\xeb?\xf6"'
 b'7\xf96\xb2\xe3\x0c\x99\x84q\xec\xd6?\x01\xb2Mi\xec\xab\xa9\xd1`6 Q\xd7Xl)'
 b'*\x17\xc6\\;~\x86\x9c\x8c\xbat\xc1+Wj\xa1\x80\xbb\x8e\xbd\x9f\x96\xc2\xe1'
 b'\xef\x8d\x8bk\x94\x0f\xbf\x17\xc7\x0f\xd2T\x8b\\\x94\x9a\xa2\xf47z\xc1N~\x11'
 b'\xe5\x18T\xae\xf3\xfb\x05i\xe2$>\x1b\xf8\xd4\xb7\xaf\nW\xa7R\xd5\xd7r\xe9'
 b'\xdd\xca\\]k\x84\x92\x1cpW=WL\xc5|\xa9\xe6<\x00\xf6\x022\xd4&\xaa\xc0L\r'
 b'N\xad\xef\x00\xfa\x7fC\xdb\xb3\x80\x18\xb5;\xd9`\xa0q\xc3s\xa2\xfb-,\x94'
 b'\xc5l\x8c\xe0\x96!\x90hs\x1f?\x15\xb5\x08+\x04\x9a]K\x03zJ\xce\xb8'
 b'\xb2\x1dD\xe6vs"\x1e\x98xmX-\xc6|w\xe5A\x96\x0c\x9c\x10\xbd\x81\xe32Y$'
 b'Yz\xaa\x19\x8b\x89\xb0qi\x16\xc4\xf4\xd8\x99 \xfc\xc9Oz\xa0I\xae\xef\xdf'
 b'?gb\n\xfe\xa3`\xf3\xc8\xf7Z\xb9\xd6]m%\xfb\xa8\xc5\xeeiq\xd5\xcb'
 b'\x96\xf7\x9d)\x0f"\xd6/\x98])\xe8\x1el\x16=\xd4\xfe\x9dq-\x99\x9d\x15'
 b'\xb9\xe8\x7f.6}\xee;\x0fA\xf8\x03\xd7+\x1c\xd0\xc7)[\x1a(\xb7\xd8\x88K \xb5Q'
 b'bYl\xe3c\xd3\x8a\xbb\xf73\xe9R\xdey\xa9\x87;\xca\xb35Z\xbc\xeb\xd9\xe0<E\x1d'
 b'\xf1ZX\x87\xac{\xaa\xb1\xebuDY\xc3GN=y\x91\xe2\x0b\xe3\xdf\x9f\x95'
 b'\xd1\xf3\xde\xf7I\x1e#\x11.iLq\x14Gx\xc6\xa4\xa7n\x04\x12\xba^\xd6\x04}\x87^'
 b'g\xd4!\x89/\xaa\x1f\x11)\x96\xb75.^\x08\x1b\n\x97^\x17\x83\x1b\x03\xfc'
 b'\xbd\xa1\x172{\x01M\xef\x1d\x957L\xb3-\xa9\xf9S\x9aw\x18\xf0\x84\xa2\xc2'
 b'\xa2v:\xc2\x82\x96P#\x1e\x12\x99\xf9\x1eP\x9a\xf3b\x88E\xb8\x08(N\xdb'
 b'i\x1fo\x85\x01\xcex\xe2\xe7N\x87*\xe1\xe8\xaf\x9c\xc9\x08q\xca\xdbS?3'
 b'\x8e\x1f\xabXL7\xdc\xf2\x89\xf3^\xf2\xdd\x1a3\xeaD\x04k\xfa"/\x97\xbf\xe69GP'
 b'\x8bf&\xc4\xea\x85\x96\x12\xdd\x86\xe5\xc3}P\xef\x0b\t7\xed\x8e\xf1\xcdQ\x01'
 b'y\xa4\xa7\x88\x82\xb9Cy\xdc\xb7\x10\xdcM\xea\xa0\xe5fA\xadZBO\x92h5l\x0b!'
 b'W\xa1\xe5_\xf8\x130c\xe4C\xd6o\x108\x91x\x16\xe7t\xa5\xf4\xbe\xd17(\xf3x\xf4'
 b'3\x89o\x81C\x9c\\|8\xb5-\xc6/v\x0b\xab\xe8_\x83X\x98\xe7\n\xe2\xb9;\xe0\xf1'
 b"\xe9g\xa5\x0c>\xe0\x81U\x1a\xc3\xcf7*\x8e\xf6R\xd1B'\xfa\x99\xdb\x88\xfa"
 b')I\xdc\xa7\x8a|\xb9\xf8c\xaf9/3\x8f\x97\xb5\n\xb6&lHc\xd4J\xd9\x80\x045'
 b'\xf6L\xcb\xa2\xc7\x9d\xa40\xf2U\x88\xba\xa3s\x0bZfevgev\xa3f\xbe]\xc8\xce'
 b'\xfa\xb7t\xccn\x15\x88\xdaC\xff\xa8\xcb\xfd\xf5~\x8f~\xff&-\xcf\xd4\xb0R'
 b"\x84\x18g\xa0\xf7]\xf9\x96\x87\xc3F\x95(U\xd0\xd7:nUR\x81b\xbc\xd8\xb45S'"
 b"\xa1\xb7O\x80\x7f\xd6\xd6;h\xee3/\xf5tQq\xc4\xb9'\xaf^,\x02\xab\xf6\x87\xd7/"
 b'\xd1oqg\x07\xd6\xdd<\xfc\xad?xZ\xaaP\xc9@6\xd1xvZ\xc4\xd0\x0ft\xc1d'
 b'\xc7|P\x05\xde\xe9\xc0\x7fZn\x17\x06y\xcal\xfb0a5\xb8K\x8b\x9d\xdb'
 b't\xdc\x1f\x1b\xcd1i\xf8\x1d\xce\xe9\x9a\xc6:\x03mO\xef\x86\x98\xa5\x0c\xd4D'
 b"9\xec\x02\xe9:\xfe{r\xcdc\x18'\xe8\xb7\xa5\xdcC}\x8fYp\xcb\xc3C"
 b'\xcb\x83\xb4\xeaJ\xaam\xbb\xae\xd2\x12r\xc5&\x03\xd3u\xa4\xf0u\x02\x99\xf3|'
 b'T\xf0a\xc7k\xcao3\xc2:u\xee+\xa22\xf1\xe2\x0e\xcd\x9f\xf7\xb8\xee\xad'
 b'\x9a\x0e\xebT0k- !\t\\\xe1j$\xa4@\x92q\xd6j\xca),\xaa\xbaO\x18\x07\xff\x0e&]'
 b'#`\x1cn\xa8a<A\xaf"p\x07Hn\x89A~#\xac\xc5J$\xc49\xc4\xb5\xe7\x1fK\x02\xc1k'
 b'\xb6TR,\xc3\x7f5\xa1\xcc\x07\x02\xf4\x02\x0bc7|3\xdd1\xee\xca\x8cA'
 b'F\x06\xa6\xf9r\x90~\x1bS\xa6eJ5\xbd\xa3\xc1\xaa\x85+d\x9701\xfe\x04\xa0\x803'
 b'[\x18\xb83\xf1\xa4\xba\xca~~\xa2\xd6r\x1a9v\xd2_\xbf~\xa4f4kY7\x06\x11'
 b'\x98W\x953&\xc3\xc1(%\xa56e\xb7\xd2,\x8cH\xf1>\xdf\xb7\x0c\xa81,)\x1bz'
 b'Op\x02\x0c\x92\xdceG"\x1e\x1f>\xd1\xb8R\xe3\xea.\xad)\xa3\xbf6\xdd'
 b'\xfe\x9a\xc9\xbeRBS\xaf%\xdb^\xa4\x04r\xa1q\xdaS\x96\x99\xbf\xb1\xc7\xb0'
 b'\xe88\xcd\x80N\xb8{n\x80(iA\xa8\xad\xce\xff\x046`\x19\xf6v;^O-\xd5\xe5'
 b'o\x83\xf8\xd7}\xc51\xe4\x1dp\xe00)8\x96]a\xcc\xe5\xe1\xafEJ\xf4'
 b'\xe6\xd8\xed\xaekm\x8b!\xd5n\x16\xfb-\x15Y\xfa\xc01\xe9\x06)2J;n\x98\x80\xc4'
 b'%RQiA\x8a\xfc<\xf3\xfe\xdeO\xd77\xbd\xe9\x0b\xa1\xc0%j\x08X/RN\xc9<'
 b'J\x97\x07&M\xd1|h\x0b\xce,P\xaa7"\xc3T\xccZ\x9b\x86\xf7\xf1\x93'
 b'\xfa\xf9\xd7\x8b\x136<\xc3\xcd\xb31[\x81\xbc\x8c\x06\xdd\x94b\xc3\x1ab\xcdi'
 b'h>\x1cZ\xc3\xfa\xfb=B\xa3\xba4\xab03\xeb\xa4\x82\xda\xb1\xaaz6\x0e\x96\x05RI'
 b'ec\xf8\x818\x97\x91\xc8\xf4r\xcb\x86\x81\xe4w\x14\xfd_\x02\xfb'
 b'\xcc\x94\x8c\xad\x18\xbd\xc6\x8d\x89BUV\xee\xc4\n\xe0%9\xb6\xd0'
 b'\x9e\xa5\xc8\xcb\xcbA\x91\xd04d\x8b\xb6\xac4\x89jt\x0bX\xb4#\x89\x90\x8e'
 b'[VW\x05\xc7U\xa4>\xd1\x12\x0eG)%\xa9\x03\x07\x91b$1\xfd\xc4?\xd9\xdb7\xcc'
 b'\xbd\xdd \x88\x1b_W@\xfd\xe9\xc1\xc26*\xf2{c\x10\xd3\xa9\x05j^\x01'
 b'\xf9\xf4S\xa8\x8e\x0b#\x8aO6\x130\x84G\x8d\x83\xcd\x10\x04\xd0q\xd6\xcb\xde'
 b'!O\xd0[\x98\xbb\xef\x00\xfc\x06\xe0\xb0\x1aB\x12\x00v\xcdC:t\x10\xab\xd4'
 b'\xb79\xf4j\x93ZZA\x85\xb2|x\xe3\xe6)\xe1\\\t\xe0s\x9c\\r\x192\xfb\x02\x1f'
 b'u\x99&\x81F\xf3\x99\x05]\x14\x92\x81\t\x82\xa4\x93;\xd1\xfd\xc7W\xa1\x10C'
 b'\xc2\x01^HCj\xa52K,aR\x9a\x01\xb5\xf3\xad\x05_\x87\x9f\xf4\xa1\xbe'
 b'\xf8-\xba\xa0\xeb\x95#L\xc43\x97&p\x9b@S\xfb\xd8\xc7 \x9d\x02\x84\rp\xfeBZ'
 b'\x8a\xf4\xbd\x98\x90\xa6\x18P\xd7\xa4^\x1b\x9dM\xdb\x08\xff)s\x94'
 b'\x05\xab\xa8\x1f^\xeb\xa22Noc\x97\x91ik\x16\xdbc_\xbfQPxw\xc9)G\\d\x14\xac_'
 b'\xc0\x91\xf7\xbc\x84\x83\x17\xcc\x9a\x85\x92V\x00\xe7K\xa4\x9b+,\x10'
 b'q\xda\xd8I9"\xa4Q\x81\x9e6s\xab(\x0ei\xf8\x14z\xd9H\xcf.\xd8\xece\\\xbb'
 b'h\xf5&\xc6VL\xb4\x9cj1\xb4\xa7\xa4\xb0UE[\x82zx\xdal~\xe8Q\xfc\xe3J\xd0Vnz'
 b'Y\x88\x9e\x0b\x0f\xc2/Mq\xc2\x95#\xbb\xed\xb4\xf6\xb1/K\x98\r\xa0\xa7\xa8'
 b'\x9e\x9ae\x19\xca\xf0\xeed\xa6Ha\x95@\xdf\x07C\xea\xaed\x01\xed\xd6KC'
 b'\xc0\x0cI\xb3=\x14t\tT\xfc\x82^\rFRa\xea\xea\xf8\x02>\x8a\xf1\xfe\xe7&s\xd7'
 b'\x13\xff>\r\xe6\xa3\xb7\xbd\xaa\xecM\xe3e\xac7\x12<\xd2w\x9dY\xe7\xf1\xab'
 b'+5\xb4\x826%\xc0\xbe\xee\xca.\xb5\xb6\xa1\xdd\xd0a\x1f\xbeCGxpc>\xf3\x92\xca'
 b"\xda\x1f\x16\x97\xde\x96\xd9N\xe4'\xb5\xd9Xt\x90\xd3\x9d$\xc1\x81\x8c\x91gd"
 b'\xc7y}V\x92\xfc\xfdX\x93\x1a\x88PgI\xd1@=v\x1f\xb3PS^Q\x8a\x91\x1c\xa1'
 b'\xc7\xe4\xdd.c2+\xe8\xe7E\t:\xae\xb2H\xd61o[\xb2Y\\\x81R\xa5\x91\x82\xe5'
 b'$>/\xcf\x02|\x9f1x\xcd<\xb8\xeeZ9+\xa59\x12>\x03\x8d\xe7\xa6\x12\xa0`\x0b'
 b'\xf4\xabp~eS\xf9\xd2\x98\xb52\xc9#\xa0\r\x08pd\x9c\xd5\r`\xad\xc71\xe0\xedE'
 b'\x87\xd4q\xf3H\x0e\xc9\xc4\x180\xa3\x15\x96v\xb1\r\x92\xe9ZH\x14)\x9a\xbb'
 b'\xba\x1e\x88\xf1\xb6\xaa\xb0\xcc_\xa6K\x08\x99f\xf6\xf52\xdc\xb1\x1eYfy\xba'
 b'\xa48\xe8\xaf\xf8\x15)lQ\xc0J\xa7c\xec\xc6\xfe\xbe\xd3\xfdA\xd7\x89z!'
 b':\x1a\xbet\x9b\xb7\xe8\xad\x12\x88\x83\xd8\x84\x97\x8c\xac\xa53\x16k'
 b'\xab\x01\x9a\x93\x80\xa4<\xde\xb7\xe3\xf2\xb6\x02j\x956eo\xb9\x08'
 b'\xb1\xec\x1c\x14\xa1R\xbf@z \xb7\x85\xefJz\xf1\x95S\x9a[\xe5\x7f_\x8e'
 b'\x11\xee\xa0\xb6z\x83\xdfI\x03\xcf\x89\xf7\xday\x1f*\xa9n&\xcb\xccJ \xb9rx80'
 b'\xf9\x86;\x8d\xe4\x19\xdd2\x85u#O\xe9w4\xc6Uh\xc0K\xa6\x04~\x00\x05\t7\xe0'
 b'\xf0\x04\xf7\x0bIH\xb4\xb8a\x90\x1b\xaaM\xe5\x13\x17Y~\x978Q\xcbR\xd6'
 b'T%\\\xb2\xa6DQ\xf4\x97\x13\x869A;XF{R\x02\x81,\xd9\xe3\xbf\xec\xe0\xca\xb8'
 b'\x13\x1b\x85\xd4\xa8\xf3\xc6e\xbb\xbe\x9b,\xcc9v\xb5P\xbf\xc6\x9e'
 b's\xe9\x05\xf0xF\xeb\xd1\xa3[I\xcba\xcb\xb3\t\x89\xe1\x1f\xc1\x81\xad}\x91'
 b'\xd1\xe4\xae;`\xe6\\\xa2\xea\x03\x84\xae\x1e6\x9cf\xe1\x12\xfa`\xa1\x96\x00s'
 b'\n\x92\xb7J{i\xc6\xbc\xbc\x0e\x83\xd7\x85\xd3\xd2\xbb7\x80\xce\x91'
 b'2\x8c\xa0\x9dTU\xaa\xd1\xc5\x8f\xd0\x0c\x8aV\xa6(\xc7\xc5\xab\xd4`\xd3\xad,'
 b'\x99\xef)\x1f\xe5\x92{\xd9\xc4\xdel\x05\xbcA\x0f(\xd4\xc9\xe6\xf3'
 b'\xaa\x12\x0f4\xe7\x9cb\x9br0_\x0f\x0bp\xa3\xd2z\xe4\xef2e9L|\x98z8\xae'
 b'\xad=\xc5&$\xc6\xf8M@\xbf\xdcD\xe0\xe7\x97?\xdb\xd1\x8fPDK\xa2\xd82=\xfa\xa9'
 b'\x9c\xfdl\xf2l%\xecg\xdd\xa5\xaf6#\xbc)\xac\xc9g[\x8a\x18j\\\xb2/"A\xbe'
 b'\xf9\xabBpT\x9a*5\x1c\xe5\x0f|\x18\xaa\x81\x91\x00eU\x0e\x87\xc0\x95f'
 b'\xf5V\x8dR\x03\x95[\x18\xccL\x95l\x9f\xe2i\xdeBBQ\xc7Dy\xd0\x16\xd1S\x8d\xe3'
 b"1\xdb-\x1b\xb5&e\xb4P=\xf7>\xb0\xbaq\xacL\xc94\xe5'\xe3u\x04\xcc\x19\x04x"
 b'\xb2\xbf\xe4\x95:1\x858w\xd0\xcd4\xc6\x96^SE\xbdP?\x1f;\xb8C\x8c\xaek\x83'
 b'FL\xf4!R\x90\x8b2\x82\xec\xe1\x98\xcc+Q\xf5/\x0c\x97\xa8\xa9OK\xd9)7w\xca'
 b'\xbc<\x19\x98\xae$\xd9\x11\xb7\xb1\x0c\xefu\xb2d 8O\xf5\xf4\xe9h\x8a('
 b'\x08~L\x0c,\x07\xaa^C4\xf2@A\xdf\xcevN\x14\x8cS\\\x9d\xceJ\xfa\x04\xd7m'
 b'\xcfm\x03[:\n\xf9L\xd9i\x87\xb0U\t\xa8\x0e}\x1a\xf2?\x14p\xb7\xde6\xe0\xfd8'
 b'[T[!\x95\xee\xff\xe8\x18e<\x90[#"\xd0\x980D5Q\xf0\xc4V\xd0\xf06P'
 b'f\xe0\xff\xa6\x92\xe1m\xeaO\x9d1p\xe6\xc0\t\x0b\x87\x89G\xd6\xcbP\xf7\xc1'
 b'Q\xc3\x1do\x7f\xefJ`\xfb\x8e\xc0\xc8\xa1yP\x94\x80~\x97\xce_\x8aY\xb1'
 b'\x1f\x87\xc7\xf9\x1c]\xddi\x17\xd4\xe46\xb1\x1e\x94\xae,&\xdeQn\xcdg\xa2'
 b'\x10\x00qN,@\xd3?\xbe\xb6\x10\xf1M\x0fir9\xf5\x9d\x99\xe2\xd3/\x10\xc5IL\xa0'
 b'\xc8\rk\xcfx/N\xdai\xf5\x8c\xd7\xaej\xdb8\xf7-\xf8\xdaf \x028\xe3\xe1d1'
 b'o\x1e\xd3:\x93\x04\r\xa0"\xc3\xb9\tQ\xd6\xf6f\xad\xdc\x10\xfdQ\xd5\x8f>'
 b'\xce\x89\xca\xd9;\xc2\x91d)l\xc6\xbb\xa0\xba\xcd\x81\xc6(\xce\x85\xc1\xc2L?'
 b'\xd2\xc4\x0e\xe2\xf0\x8b\x15\x91\x8f8`j\x1f1\xcd\x10\xff\x8d\x96\xa5&Ga\xff'
 b"S'\x8a\xd3\xbd\x8bZ\x94\x11\xcc\x9d-\x1a\x11J\x8b#7\xac\xb0\xfcW\xd5\xa9"
 b'\x0e\x10^3\xcc\\\xf9\x87\xd2\x83\xab\xc8P[\xbbO=\xb5,\xf4\xaa\xf2\xcd\x07'
 b'\xa9,t\xca\xfd\xc81\xf6\xc0,\xf9\xdb{\xa4\x8fO\xd6{\xe8;\x0fz\x16['
 b'\xd7\xae\x85\xd8qc\xf0f\x03\xea\xf0\x04D\xfd\x90u*9\x19\xf9\x89\xd9\x87\xd2'
 b'\xe7`\x1a\xbe\x05C\xb1\x0fi\xe6\xe6\xa1\x90\x8c\x01\xc7\xc4\x06\xb4\xa3'
 b'X\x12\x91\xdbQ7\xae\x94#GE\x1a\xa4\xa9\xc7\xe8\x04\x08\xe0\xa7'
 b'\xc5\xcd\xe8\xdd\xcf\xe7\x80\x8bw^\xadh6u\xdeb\x1a\xec0W)\x9b\x7f\xc1'
 b'w\x0f7\x14t\x02B\xbd\x82\xacWQ}5\xb7r\x83\xb4w\xde\x1fl2\x02I\xd3T\x8e'
 b'\x93\xf4$\x97\x9e\x13U\x1ctMWwH8\x01}\x86s\xd7q\x16\xb1\xd3\xfb#.U\x86'
 b"5O\x01\xefOdf\t\x7f\xe2Z'0\x16\x9c\xed\xfc\xba\xca\x03\x89\xde\xe3\x95"
 b'-Xr\xa0\xbe8\x9b\x07\xc76\xcb\xfd\xb6\x99IB\xd4\x11\x812r^\xabN\x87C\x97E'
 b'\x16\x12\xe7\r:\xcf\xc6\xdbb/\xd7"7\x1a7\x17\xba\\>\xdbF\x88\xfb\r\xcbuP\x83'
 b'W\xecc\xef\xbc\r2\tq\xa1\x95\xa6LK\x98\xebWu\x19\xd9\xc2\xc3x\x04'
 b'%\xb4\xc0\x9dH\xe5\xfc\xc7\xb968\x11j\xc2f\xcc\xf3\x98\n\x83\x83\xa3\x148'
 b'l\xf6\x86\xfa\xf3\xe5\x9a\xebR;\x97\xec\x80u_\xb7~a\x1b8\xacA\xb5\xe8'
 b'\xb4\x91\xba\xf5\xd4f\xf0}[\x06\x07\xf4iG\xd2\x83\xea^\xf3\x108O\x18\x87'
 b'k\xf5\xcfR\xf3\x92\xe9jP\x9b\xf4F\xebHi1\x001\x1ar\xc8s\xb8d\x89\xd1C6'
 b'\x13\xf8\xf8|O\xc3\xbb!\x10\xbe\xb6\xd7\xaf\xb0!3\xc8\xfa-\x1fs\\\x0f\x01'
 b'\x1f\x8b\x94\x99\xd7\xeaX\xac8]\xdc\xf4\xad|\xb0\xe2\x9c\x027\x04'
 b'\x1a\x8f\xd6\x00Ps|\xe9p\x933?n\xfe66\xe7\xf1F\x8e^}"\x83\xa7=\x1f\x03'
 b'\x13\x16FrV\xff`T\xaa\xadm\x15\x1b\xaaeh\x1f\xf9\xdbuv\xfe\\\xfe'
 b'\x1f\xd8 \xc0*\x10\x7f\x9a\x9d\x0cB\xef\xd2\xedH\x87\xf4\x8d\x96O'
 b"\xdc\xeb\x0b\x9es\xa7P-}x\xdc\x92\xeccQR\xff~`;\xfe\xe1\xc6\xd7'\x8f\xf9\x17"
 b'\xce4\x18\xcd|\xd4\x12vJ\xba\x17#B\xa6m,#\xa9\xd6dB\xaar\xc5\xd3\xbb\x9b\x1e'
 b'U\xd4EV\xe2\x1f\xd3Z\xc6]\x84^L\xc7\x94\x8c\xe2\xc2\x8e\xd9\xe2\x00\x8fH'
 b'\xc1\xce\xb7 u/\xf4]q\x82\x89\x17K\xf0$,\xf2A/\x8e\xfaP>\x90\xc0\x1f\xe7\xf0'
 b'\xb4^\xdc\x96W\x19<\x049\xd9\xd8\x17\xc5\x17\xc2Y\x84ZU=I|\x06N\x8d\x0exv'
 b'\xeby-YP\xaf\xbd\xc2\xe0h\x06\x0c\x98\xe2\xa5b^\xdf\x8b\x01\x91\xf6xF'
 b'\xc6\t\xb6`\x91\xdf\x08\xa4\xee{\x83\xc8F\xa9pq\xbb\xef\x0f\x1cQ\xe5m\xc1'
 b'1\xec\xc5\xd1\x01\x92q\rk,\x95`-\xdcE*\x86\xb3\x01\xab\xeclVT\xd6\x8brB'
 b'r{\xd0\xe5:\x9f\x05\xa5\xc2\x92\xce\xefZ\xa6\x96"y\xa9\xe7\x8c'
 b'\x1e\xd3\xa8\x12\r$\x91\xec\x85\x8f<\x98\xb5\xa5Cf\xc7\xec\xb0\xe9'
 b'\x8c\xe8\xb0\xe1\x99\xfb\xd481\xf0\xe3q\x15\xe1Gy\x8f\xa0\xd2\x1d'
 b'\x98\x85\x10\xa85[\xd9\\\xc8\xce}\xaa0!\xf8fC\xbc\x85\x18\xa6\xde\x9d\x0c'
 b'\x80K\xae\xb8C[\xc5\xba\xf4\xe7\xac\x9d\x06+B\x1d\r^(\xfb.,\xb42'
 b'X\xf9\xdb\x030\xfe\x07(\xb3\x0b\xb4\xdb\x03\xe2\x91\xa9|\x81[\xff'
 b'r\xb1\x17\x1cT\xfd\xe8\x8a\x8f\xe0\x83]\xb5\x95\x90\r\xe5\xd1VI\x88i\xa0\xea'
 b'w\xf3j)\xa0\xe9\x06\x12\x07I\x10\xe5\\\xe0\xb5\xd9dD\xe0\xc8#\xa3`\xa3'
 b"\x80\x03P\xa6H\x9c\xe6\xc5\x9a\x8a\xee+^\xe5h'\x8eo\x1d'\xb3z\x13\xf5"
 b'\xfb\x96\x9b\x83\xd0\x99\xff\x07]\x9d\xdd4DrJ\x01W\x8be~9\x94\xe5\x16'
 b'\xf4J\x07\x19\xa5\xa3E%[Uv\xe5\xc3\x8b\xfe\x99\x96\x96\xc1H\xe8w\xe3\xfc'
 b'\xac\xae\xb3g1\x92\xa7\xd0\x04\x0f$s\xc4\x16\xf0\x8f=\x8e2y\xa1-\xd2_'
 b'\x82\xf9\xc5\xfb\xe1\xc4\xa01\xe613\x7f\xea\xde\xe9\x87 \xbcs"p)bS8\x010\xbc'
 b'+\xf6\x1e\x81\xb8\xee\x96\xb5;\x1f\x0c5\x03\x7f\xed\xc8\x87W`[\xa2&\xe4Q'
 b'n\xea\x06l\x1ej\x87\x06\xe7i\x9c\xab\xe8\rx\xbfT\xe9\xd3\x14\xd1\x1b\xf3\x9f'
 b'$m\xe5}\xa7\xc8`8\x96\xb6\xeb -\x0b\xd4c\xdb!\xd8&\x1a\xa0~\xc6'
 b'\x0e\xbc\xf0\xac\xfc\xd9\xa5\xe9j\x17I\xd2\xce\x1f7\x9erV*w\xf2\x9by\xb1'
 b'J\x8b\x1fZ\xe1\xc0\x08\t\xb1c\xd8\xfb!\xff\x9e\x999a\x1a\xb1\xe2\xad\x94y'
 b'\xee\xfa\xb5\xbf\x0b\x08\xa8\x9a\xd1\xdf\x88\xfe\x07\xd4\r\x94\xe6<\x03\x94'
 b'\xbd8\xc465J\xa3`(\xd68\xac\xba\xe3\x01\xea\x82\xa4\xfa#\xe0\xc1\x13j'
 b'K(\xd1\xca\x01?\xcf3\x11\x8a\x7f%Q\xbd\xf7}\x8dA\x84o=.\x02H\xb8~\xd4R'
 b'$y\x98\xb9\xe1\x98:Ir\xabl\xca%\xbf\xe1\xc2\x8e\xb9S(0\xa89\xd5\x89\x93\x81/'
 b'|m\xfeBk\x99\x95\xe3\xaf\xe1A\xf4)S\xc2W*&6\xd2\x10\xfd\x9dH\xa4\xa0E1'
 b'\x9fM\xdca\xc4\x03\xb6I^\x17\x95!&\xa4-\x88_\xae\xa3\xe2fMM\x942 DT'
 b'\xb8\xc4E\x1b\xb9\xadkg\x80\x99\xd9\x87\xa4\xa4\x0e\x15\x1b\x0b`\n'
 b'\x1f-\x13\xb3\x0f\xf0|S\n\xae\xc1j\xda\xac\x15\x9e\xccf%\xffG\xabW\xd7'
 b'\xee\x93z.\xea*\xa1N\xfb\x82\nG@\xa8\x12\xf8\x87\x0e5V\x03M\xeb\xdd'
 b'\t\x0b\xa0D\x8a\xfc\x8dL\xc2\xa7\xcc\xde`\x87\xc7)5\x1ciM&\x02\xd4\xe4'
 b'.\x85\xaeC\xc6\xa2\x82k>\xbd\xffP\xe7\xe0\xec\x86\xc5\xe2\x06\xffy\xa0\xad?'
 b'\x87\xcfd&S\xd4\xbfy\xe1\xa2p.M\xfd\x9a\x93N\x9bJb\x19\x8e\x8925\x8c\xcfK'
 b's\xc4\xea\x85\x8d\x91!\x1aQ}\x1eC\xde\xe1z\xd7\xef\x93\xe7\xdf)\xdc\xf3\xff'
 b'\xdeS\x87\t\xba\xb1\x12\xc4M\xa0\xcc<f\xb0v\xe4\x08\x02\x93\x05c\xc0\xda\xac'
 b'i@ \xb5\xed,\xf4\xf4\xf8C\xfaP@\xcc\xcb\x00bpxyz\x1a\x03t\t#\x1f\x0eA~oA'
 b'\x98\xe6\x8c*aZ\x19\x81\xa8O\xa3U\x90\xd9\xca\x1c]\xe2!\xb7\xe3\xdd)\xbf'
 b'\x04J\x8e\xb0=|\xbf;pS\xbc\xe4=*\xbam\xb7M\xf7#\xf0\xf7\xdc\xa2\xe0l\x02\xfb'
 b'0\xc7tgF\x99\x0f\x83<|+\x18f\xbe\x1e\xed}\x8c\x03\x84\xd2j\xc8D\xa0\xec\xf54'
 b'\xf4\x1d\xca\x93\xc1y\x8c\x93\xcf\x1b/\x132W\x99\x08\x85^\xa66\xfc\xd7\xd0$'
 b'\xf2X\xb0\xe4Z\xad\xdb\xfd\xd9\x85b\x83b65\xf9g\xdd\x16\xc5\xd2|\xdf\x1f'
 b'\xc7\xa9\xed\x10\xf1\xad[\x80\xa2h\xe10D\x8a\xf2\x97\xe7. \xae'
 b'\xf6\xb5\xb7\xbd\x0f3\xd2\xa8\x98/n1\xda:O\xb6\xfe\x92\x84\xe0\tJ\x86\x9c'
 b';\x820\xe2\xd7d}d\x86\xd7R,\xc2x\xf1\xb1S\xd0\x8d\x14\x94F\xeb\xb8\xf6;\xder'
 b'Xk\xf0V\xd8k|\x9e\x1b\x03\xd4A+y\xc1\x13J\xb5E\x16z\xd0\xe0U\xcf\x1e\xf8\xe0'
 b'\xec\x8f\xec\xa9\xa1ot\xe9\xdah\xf9,\x08{v\xe0W\x88`V\x04\xc9\xd5\xbb/5\x81I'
 b'(\x98\xe8\xacr\x87g\xa2\xe7\xf2h\x8e\xb2\x90\xf9\x83\xfc6\xba\x84\xcde_\x82'
 b'\x18d\x98J\xf0\x8e\x92p\xeb\x9d0Y\x8c\xe8lF\xd6\x97\x8c\x80J\xc2V\xaa'
 b'\xb6e,\x90.\xb78\xdc\x19\x06s\x99\x1e\xbc\xdc\x9e\xce\xb1\xb3\xc3ij\x89L'
 b'\xbc\x18L.23\xdb\xc9\xe3\xdf\x03\xcb\x13\x92\xf1B\xc0q3\xae5\xbe\xb8\x0b'
 b'\x83jp\xf2\xc9?\x9e\xdd\xd7\xea\xed0\x02\xe9\x97\x83\xbeJ\xc7\x02'
 b'\xbc\x02\xbf?\xe3\x9c\x11\xb9\xfd\xe0e\xfa\xdf\x10^t\xe4\xc3\xae\xadIun\x01'
 b'\xb8w(\xfc\xf9Fs\xed\x9d\xbajK\xa9YO4\xa4\xad9\xaeI\x83\xe2l\x19\xd4\xa5}'
 b'H\xcb\xda\xcb\xae\x98\xd7=\x8d \xfe\x921\xad\x95;0\xda\xdd\x05'
 b'\xe7\xb1\xf1\xb6\x81\xf1\x85\xed\x12\x9dLB\xc3\x969\x85\xb4\xa0\x1b!'
 b'D\x7f\xcdj\\\xd9\xc5\x04J\x9e\x12\xed\x82\xe8n\xad\xb2\xab\x01\xaa'
 b"\xf0\xa2\xb3\x05^\x12s\xa81(\xf9ve\xa7Qzh'(\xd1BiZ\x96Q\xe1\xa5\x06"
 b'\xc4\xa7\xf8&9\xad\x13\x00\xa8(\xb2\xae7]\xdc\xa23\xfeip(\x98!!\x10\x19A\x90'
 b"\x80\xe8\x9b\x08\x91&5\xe6J\x1cE&:\x0e\xbd\xf2\x89='\xfa0EC?\x1f\xd370"
 b'\xac2Y\xfa\x9e#\xc8|@$\x10\xd4L\x95:\xe6~\x06\xf7\xd2\x08\xacD\x10Ov\xa0\x94'
 b'|\x88`\x9ez\xa3X\xe0\xa56\xc4\x97\x15Go\xd6\xd9\xbd\xbfxIl6W\xb2\xdd\xdcG'
 b'\xee\x95\xc8\xf2d\xd7\xaf\xb8\x9cc\xb2\r&`\x00n\xbb\x8b^L6\x18N\x17'
 b"u\x82\x04\xe2\x05~\xa0@W\xf0\x06\xec\xe9\x0cY\x0c\xe9\xc8l:;\xa0'\xc7"
 b'n$\x08\xf3\xa4H\xa0\xa9\x07\x9f\x9cP\x1fc\xab7\xc3\xfek\x01W\x88\xb4\xb3'
 b'\xc0x\x03r.\xc9\xef\x15\xb8pL\xfb\x1f\x97\xdf\xcay5R\x12{\x87\xb0oi3\xe6\x0b'
 b'n\x0c~\x1e2G\xf8_\xaa\xe0\x16T\x00yn\xf6\x19\x8c\x87\x01\x82\x17\x1c6'
 b'\xa0Y\x7f+\x19\x99\x05%\xac\x97\x8b\xf7\x18\x98(dF\x1b%V\xa9\x9b\xdbN'
 b'\xad@\n\xad\xd6\x04\x9bUR<\x02\x03\x9d^Mc\xfa\x04\nK\xaa\x05E(\xdd\x1c9\xdb'
 b'\\\xac\x11_\xf2\x86\xeb\xa3\xe9k\xa7h\xa2J5\xfaG\xa49rk\xb3\x04-T\x8b^\x88'
 b"\x1cget\t\xd2\x1b\x94\xdb\xa9'S\x0e\n\\\xe0\xa7\xa5\x80(\xbd\xb3\xa4\x17"
 b'h\xb1ms\x07\xe0\xaa\x91?\xad\xd1Dou\\\x1b$\xcd\xd4/v\x85\xce\x8e\x92\\|\\'
 b'\xa2/\x05\x17q\xd4\x14\xb5toC:\xd6d\x11wF\xa1d/\rQ&\x9f\xe5)\xca\xa4'
 b'm\x97\xa8\xf8\x9a\xc5\xe0\xe8\xc5d4\x81{\xffF \xf3`\x0b\x9a\xce(\x84\xde'
 b'\xaf\xdb\r\x94\xf0\x81\xd2\xf4\x0cx\xfeo\xdd&\xb3\xe4\x8ca\\\x1e\xc72\x04O'
 b'l\xbd\xfa\xdf1\xfc0\xb1\xda\x93\xfa\x82(\xb9\x9b>n\x80\x99\xf1\x91\xa5\\\x87'
 b'\xdfI_0I\x01/\x04l\xda<\xfe\tZT?y6\xcd\x15\xd1\x84b4\xbcn\xc1{H\x05\xc7\t'
 b' j\x14\xf0a\xdfs\x9c\x13r\xb5H\xd3\xa9\xf8\x97\xa0\xc8\x1f=\xb9\xe0I\x0c'
 b'h?\x07_\xd2C\xec\x82o\x99\xf17QM\xe6[\x14n\xbf\xb5\xccR\x13=\xf8\x07\x02R'
 b'R<|\xb6\x95\xe5\x9e\x81\xd2$v\xa1N:T=\x87\x88\x14\xdfU\x99\xd5$\x00\x0bH\xbe'
 b'\x88\xf2/p\xafc\x9f|\x11t\xc8\x17\x11\x9e>\x10\xec\x1e\xa2\xd3\x8aC\x80\xca'
 b"\xa8\x14yQ'\x93\x92\xbf.\xcf\xbb&\xael\xe7\xb3\xc4/E\xfdiH\x92\xcf\xeem-\xfa"
 b'\xc2!fV\xda8\xfe\xe3\xf9\xba\x96\xea0%6\x88\xf5\x1b\x9d\xf5{Z\x9b)'
 b'\x8c\x9f\xa6\xa4]\xc7\rTe\xb8.\xe62\x98\xa9\xac\x12"i\x19\x81\xa3\x1b\xf8'
 b'u\xe2\xb3\x0f\x01x\xf6~\xed\xaa\x9b\xfc\x89\x8bR3G\xbe\xfbW\xa3\x9e)\x1c'
 b'v\xdfDD\xcf\xed\xc1\x96G\xe1\x00ad\xb4\xac\x02Z+\x05\x1al\xc3\x8do'
 b'\x80n\xca\xa3\xb0\x08\xa6\xad7\x00Sc\xcb\xdc\xce\x87\xe7=<.\x8a\xe7WE'
 b'\xb3\xea\x8a\x90@1\xef\xe0a>mY\x89,\xe9W(\x1e\xff$ U\x17j=\xd0\xc9\x9e'
 b'R\xc1\x1b\x13\xf2w(Q\xb44\x93\n\xe8u\x02(\x8aB\x83\xfd\xfe\xcb4\x16'
 b'\xc8\xa8\xc2\x1d\xd2R\x9a\x82l \xda\xa3\xfe\xf6\x1ek+\xec\xb7\x94'
 b'\x89\xbe\xe0H\xbe\xa5f\x03\xa3\xff\xb5\xdb06m\xa2\x1ci\xa6\xbc\\4\xb7M'
 b'\xa1\x1d#\x05\xee\x0f~7\xa8E\xcc\xfe\xcc1\xc3\xed\xc7\xeb:%\x851\xb4\xca'
 b'\xfe\x04\x15;\xdf\x06\xf4\x00bG\xb0\xd5=\xda\x18\x138[\xdfJ\xbd\x07\x88\x1d'
 b'\xaaFC\xbb-\xa3\xf4\xdf\xabAB\xf9"Q\xeb\xdb*v>\xc9\r\xddv\x02\xde\xb7B\xc2'
 b'\x9f\xb6u\xbd\xfdC\x02\x02\xe5i\xe6vF\x03`\xc1\x94P\xebq\xdd"\xa7I'
 b'\xe7J\x16\x82\xf1\xb5\x8b\xdd\xa8\x14\x94R\xa0\xf9+\xd6\xaf\x9f\x81\xa6'
 b'6E<\x81Z\xb8\xed\x8bD\xca\x9f\xa6\x91\x1d\xday\xc6=\x9b`\xbf\xd8<\xac'
 b'\x807\xcd\x1a \xd0\x93w,\xff\xde[L~P/\xd4JIP\x88\x14r\xc0\x82\x1f\x1c\xdb'
 b'-\xe9\x99\xcc0\x124W}\x16\x01\xb0U\x96<O\xc8\x8az\x11\xd3KX\x0b\x02\x82n\x1c'
 b'\xbb\xabc\x16\xd3x\xbb\x95k\x128:uE\xd5\xa3Q\xac\xba\x1d\xb9\xb3\xf6\xa1'
 b'\x7f\x032f\xa8zy\xd5\x90\xaf0\x8f\xd30\xa4\x8b\xadc(\x8d\x14P(O'
 b'\x0b\x85\xa0\x9f\x94\x04\x90\x9bA\xa9\xe7\xe3\xa6\x0fr\xf7\x95\xd0\x84\xa8'
 b'\xbb\xf1=]$\xd9\n\xce\xc24\xb7\x8b\xec#\x8d^\xe7\xd0\xd7\xf96gST'
 b'\xcf\x87\xae\x0b\x0e\xda#\xe8`\x82\xbaT\x97oHmF\xd1\x17\xd7K^p\xeb'
 b'R\xaa\xc2\x9a\x12\xa7\xa98;8\x94\xa6\x14u\xad;\xa0\xb3\x06\xc5\xa0\xd0| '
 b'\xf3\xa5\x83\xa32\x14\xa9xKs\xcd,0X\x02Ck\x80\xae\xea\xab\xc7\xf8\x0f'
 b'J\xd0h\xf1-H\x87\x1f\xa4\x19\x14\xf7\xc6B\x9cV\xd0\x1b\xd8oW\xe8m\xaaAo>\xcc'
 b'\x95^:\xd0\x0b\xe0\x81k\xed\xe5\xa9\x98\xe6\xed!Y\xe2A\xa5%\x959\xef\x1b'
 b'(\xdd\x08\xb3\xaeK\xd3\xbb\xf2m\xc6\xe7\x98 z\xe2\xa7*8\xe7\xd5\xe7\x81\x0c'
 b'u4@\xb2b\x8d\x92j\t\xb2\x86\x19\x07\xd3\x1c\xf5\x12\xb9\xb6\x81\xd9`\xc3\xab'
 b'\xa7\xd3\xc5\xeb\x85n\x9b?\xc5i\x87.4\r\xba\x1e\xf5\x88?\xd1\x9cA\x07\x8c'
 b'\xd2V\xd0\xe5\xb8\xa0\x9b\xc3\xfe\xff\xcc\xcd\tO}\x06z\xf9\x87[\x06\x0e\nt'
 b'\xf1-\x00\xc1\x1f\xa6j\x0f\xbcA\x05B\tR#w\x1a\x99\x1e\xcf*R[\x02\xda\xf7za'
 b'\xf5\xf1\xcd>\x14:A:\xd6;\xf1R9M\xb8-\x96\x02\x92Rt\xe4\xc8\x1bgz\xe2\xd4'
 b'\xb5"\x83\xfa\xc0z\x1e\xa9\xec\xac\x9f2G\x03\xaf\xb6\r\\\xfeGf\xef\xba\x81'
 b'YuT\xefw\xf9\xc6\xe7I\xbf+\xd7lj\x97\x0f\x04\xd3A\x17Z\xbb\x94\xe9\xd6Z\xabv'
 b'\x99\xaf\xe0\xf9\xe8\x13\x9d\xc4_\x8e\xb1\xe5\xe7o\x15\xe99H\xc58~\xa3n\x18'
 b"\x83\xbcD\xe1.{\n\xc7k\xebo\x98H\xbc\x1d\xfcf\xeb\xfa\xc8\x82'\x0e\xe6"
 b'\x8b\xc9\xa4a\xa3\\x\xf8&&Z\x95\xff\x1dr\xba\xdf\xa2\x8b22\t>\x10\xb3fM\xf0'
 b'\xc2o&\xa2I\xec\x1b\xea\xb45\x04n\x0b}t\xfcX\xb3k\xc2\xdf\xcc|\xf6G\xa7$\xbc'
 b"\xe9\x11\xd6\xb8\x064\xeck\xa5\xc5\xfb\xd8\xf6\x86\\PE\xc4Jj\x91\x10'\xa6"
 b'q\x05\t\xe6\xd1\x90V/Tg\x94$\xee\xf3O\n\xfb\xb6\xc7\xbf\xf3\xaf\xa05'
 b'\xa8\xe4!!\xba\x02}\xdf\xb4;\x10\x01u-\xecwk\x9bmj<,\xd9A\x07i\xb6\x9b'
 b'\x06\x15ob\x84\xa5nX\xd9\x0f5\xc5\x00E\xf1(Zu\x1a\xaa\tH/?\x11\xd7{\xdd'
 b'\xc9\xfa\x9d\x8a4\x8b\x8d\xe3X*\x14\x0f\x1d\xf6-\x81\x1bv\x96G\xf8A\xf0('
 b'tx\xca\x81\xc5\xb4\x9f\xaf\x11\x9c\xef\xe7\t\xfe\xe7N\x11v\x01\x03'
 b'\xdb}\x80\x14U\xc5\xb8S",\x16\x96@u\xfc\x01\x89\xd2\x05N\xf3\xe1Em'
 b'0\x03\x89\xb3b{P\xbb\x8c\xbc\x8b\xc9\x8e\xb3*z\xf0\x7f\xb2\xfcpP\x1eK'
 b'\xcb\x12\xae\xd98]\x16\xb1\xf3\xeb\x87\x1a\xad\rw\x1a\x04\xe8P:\x89.\x9f\xe1'
 b"H\x91\x0f4\xb1\xb3\xaf\xae\xcd'\xc6\x9c\x8b\xda\xce\x90=!P\x80\xa4*\xf2\x9a"
 b'\xe3\xe2\xb1\xe0\xaa\xfbp\x0f\xc4Y\xbcn.\x1d_\x0c\x81 \x11)\xcf\x9fC\xc3'
 b'T\x80\xa8i\xde\x10\x1dC\xf8\x11?\xbcF\xf0E\xe4\xear\x19=8\nR\xbb'
 b'\x90\xdf-\x83\xc1\xb1j\x82\x81\xff]\x81\x02\xa9\x01\xa0\x88=\xd2\x1cg\x0c6I'
 b'I\x03\x86>_1\x9eD\xf4\xd2$ja}\x1e\xe9=S@X\x07\xcf4\x9d*\x07\xf7\xce'
 b'\x83\xab\xce\x9f\x90\x82:\xa8N(?\xa4\xf6\xf6\x03\xe6\x07\x9fg\xb6'
 b"\xe6F\xcf\x07s\x845!s\x00.0Y\xee'x\x1a\xfd\xf6Bb\xbb\xbc\xb5\xdeD\x91\x11"
 b'F\xbc\xf9\x83Q\xb1\xe4\xcb\xbab\x8d\xf0\xa8?\x85\x92\xf8\x8d\x8a\xbc'
 b'rJ\x8b\xa8\x05J\xc1P\xe2W\xcf\x95\x16H\x05,M\xd8]\x14\x12\x1f\xa3\x88'
 b'y\x9dp\xf4.\xd6\xc30\x03\x0c\x93XRU\xdfN\x8a\x06\xb4)\xb0\x82xf\xafI\xe6\x82'
 b'fpr\x13\xad}\xdb\\{\xcb\x1e\xb7\xc6\x900\x10\x88X\x9aWL\xb1\x7f(~\x9eqo'
 b'\x14}a\xf09+\x06<<w\x9c\x07\xbe\xa1\xf4\xa9\xad\xb6\x17\x1dX\xc1\x19\xc5'
 b'\x90F\xee\xd9b\xbe\x8a\xeaBE\x95\x0c\xbf\x1f\x82\x8e\x07\xd4\x87\x98'
 b'\xfc\xd1\xbb\xa8B\xe8@*\xee\xd0\x99\xa7\xbf0\x7f\x1f \xad\x83\xfbT6?\x87'
 b'\x14]I\xfbAB\x8f\xe7K~n)\x1b=Ji\xb8\x14\x9eS\x88\x93\xe96\xd0\xbd\xdc\x13'
 b'\xe6B\x0e\xf0\xca\x90\xdd\x8a\xe7\xaa\x05\x9f3\xad\x1b\x00\xd6e(\xb3'
 b'\xac\x9bFI\xa1\xa3=\xe1\x18\x1d\x91gN=\x14\x9cf04\x8b\x9c\xbd\xef1\x9cR+\xf7'
 b"\xb86\x86\x12\x88\x86L'fL\xcdl\x11T\xcd\\\x16\x97\x1f\xde\xf9i\xa44"
 b'\x89&\xcd\xad!\xa68\x00\x1fj\x04\x1d\xc1\xf12\xa4\xd8g\x10\x13\xa2s\xc1\x83'
 b'\xc0\x15\xb8\x06O\x1as\x99\xf3\x88y\x1f9\x8e\xcc\xb0\x10\xbb~\t?\xae\t\xdb'
 b'\xf4\x0e\x98~\xad\xb0\x03\xd9h\x1b\x00\xd1\xb7\x16\xf8#\xa1\x01%\x15'
 b'\x1c\xb9\xb1\x05\xfbn\x19\x0b\x86\x0f\tuut\xb4&SY&x\x81\xe7q\xae'
 b'\xe2\x87\x83K\x05|H\xfb\xf7=\xd4\xfa\xbd\xfa\xa4\x16S\xf1\x89\xceY\xa4\xae='
 b'\xbc\x9d\xef\x1dWqeR\xad\xeap\xe0Nk\x88SOv\x07\xf2}\x9d7X\xd4\x81v\xa2'
 b'F\x99\x19\xf5\xe8\x05\x04\xbb\x06\x8eA\xc9w%\xa6\x06\x02\xedQ\xdeT7\x9c!'
 b'\x07\x81\x87)\xc7/\xfb\xb7\x1a\x8a\x9b\x8as\xfd\nfpk/\xaa\xb8\xb4\xcc\xaa'
 b'\xd5\xedq\x18\xe47\xe7j\x87\x98r\xd8\x9f=\xc8}_\xbc\xc6\xd9\x1cf%\xe5>_\xf61'
 b' \xab(`KP\x8b6\x08 nIpB=\x0fr\x03\x91`k\xe0\xd7\xab\xbal\xa9X'
 b'\x95\x02\x0f\xed \xccD\xb5\x199\x7f\x9d\x84\xbf\xdbMF\xc4T\xae]=#\xde'
 b'{\xa54\xfb\xd7j\x05[4.\xaf\x83\xbd\xebBu\x8a\xce\x9dl\x9aYk\x11r\xce}y'
 b'Q\xcdR\xc7W\xf2\xab\x9a\x89^W\xed\x15\xc0\xfb\xd4\xae8\xb3\xa7]\x93aOQghx'
 b'\x93\xc7\x05\xcbW&\x86"t\x082\xc9o\xaf\x8dwG\xf9\xbb\xbd\xe5{#j\x8e\x11\xa0$'
 b'\x91\xbaj\x89\x19hvB!qe\xaaN\xd5\xe3C\xc9\x9cm\x01\xed\xa0\xb3H'
 b'\xf1\xc2\x96\x90\x89X)\xe4&\x0b<\xec\xa6\xc9?E+\xf0\xb1\x95\x07"\x0cU'
 b'\xe9\x8a\x91\x1a1\xd9\x97K=g\x10\xdaj\xf7\x95\x12\x02\x8c\xa0\x18h~\xd0#'
 b"nZ\xc9\x0f\xc0H\x00*\xba\xdb\x95\x13W&Z\xd8\xf1\x964\xe8\xe7-o\xce\x16\x83'q"
 b'\xcf\x14\xd1,\xd11\xc3o\x17\x82\x1a\x04PY\xa2_\x02\x89a\x1a\x95\xe9\xd0H'
 b'\xb0\x14\xb6\x10z\x9e"\xc1\xd9oA&\x98&\xac\xc8>p0\xd0\xd6\x01\x11<\xf4wMp'
 b'\x07\xf2\xf8\xfe3qLE\x9e\xd9\xb6pQY\x15\xcf\x13\xaf\xc7\xb7\x17i\xd6\xce'
 b'_\xc3xYV_\x89\x0cb\xcf\x8fN\x89jVU$\x8c\xb1\x13\x82\xc0\xe7\x08c\x1eT\xa8'
 b"\xb6 \x87\n\x91q|\xa6\xf1\xfaX\t,_u'@^\xcb\xdd\xfb\xab\xd0q'\xb6\x08Y"
 b'\xb0-\x85\xf0jk\xd7\x1bxHlS\xfd\xed\xc7\xc7\xcd\xd3A\xe5\xd9\xccH\xbe'
 b'\xd2\xbb\xafZ\x08\x9b\xc0[?\xc8-)\x089>\xee\xa4\x9c\x18+\x883\x9f\xe2hP^\x9c'
 b'@\x17\x85S\xe6\xb3r\xbe\x18\n\x9b\xee\xf8\xefh\x14/\x07\xbc\x05\x06\xb8\xe8X'
 b"`Z\x15\xfdX\xcc\xa5'\xc1\xcc[\x0e@\x03\x114\xe1b\xe3\x86Z\x06E\xf4BH\xe6\xa4"
 b'[\xccO}\x15@\x86\xcc\x7f\x1b\xae\xa9\xa6d\x88\xb2\xaf\xfa/\x97\x84(\x08\x0c'
 b'Ls\xd7\xfc,A\xb10%\xc4\x06Q\xb9q\x1dy\xd4\xa0\x15\xb4\x96\x90M]L\x06\xefD'
 b'V\x7fJ6\x90\xb0\xbb\x05\x84\xde\xe2\xd7\xba\xfbGK\\H\xbeh\x15\x12\xa0<'
 b'&\xfe\xd3\x1a\xf4c\xd8\xbb\xd1\xc4\x92\x89\x12\x95E\x81\x9fK\xa20L\x9eS\xfd'
 b'\x9c%\x9e\xf50Y]\xe53\xfc\x88\xb0\x9c\x88\xe0(\xc8e\xc28\xad\xa0I\xa5'
 b'CY\xf5\x87@\xfa}\xb0(\x1aG3\x0c\x80 \x87o\x81\x18\xa9\x12B\x7ff'
 b'\x8b\xcd\x03\xda\xa1\xde|Q4Yt\x01\xce\x93\xd6\x1b\x817\x98|\xcf\xc5\x03\xd0'
 b'\x13Q\xaf`\xfd\xc1\x9a\r3\x14G\x9bY\xab<\x1f\xe3N\x9eJu \xbfQ\xf0\x9e!&'
 b'w\xde\x14\x94\xcb\xc6\x8f\xa2\xd5\xa2\xe4}\xf9\xf8\x9cn@5\x1d\xc3'
 b'\xf1\xf8%\xaf\xcc\xd51\xf2\xef0u\x01\xe6J\xdbD\x13Z\xe9\x18\xd0H94'
 b' \n\x1f\xe6"\xbf<\x98\n]\xf8\xbehP\x0f\xf8\xe0b\xf2\x97^\x9c\xc7jAW\x02`'
 b"P\xf7h\x0cs\xda=\r'\xc9\xe8yp?\xc8\xe0q\xbcA'B\xc02L\xc7\x9b\xf1\x9b"
 b'-\x9d\x0f\x93p,\x1cW+\x17]\\\x95\x1a\xa9&b\xb0\xf0\x85\x81}\xccKr\xff\x9e~'
 b'\x88P\x8c\xc3\x0b\xd4\t\xfa\x9ct<\x93\x92#u\t\x98\x03\xe31\xc7.\xdd&'
 b'\x18w\xc4H\xab\xff\x00\x17v=\x9c\xf3\xad?Qu\x1b|I-\x87\xf4\xa0\x17\xa5TA\xa1'
 b'\x87\xb09\x04 \x15\xcc\xf3\x8c\x83\x13s\x9bE~\\\xf5\xc0^\\S\xf6\x16 '
 b'<{\xd5\x0e\xf6\xd7\x93\xed43\xc3\xf9\xa6\x9a7\xca&\xff\xb5\r\x15C"\x0b'
 b'q\x92\x0cs\x18/S\xafK\xa2\x04\x1aP_\xf8\x0e\xb6\x16c\xf59\xb4Q\xb4I\x18\xaf$'
 b'\xd7\x80D\xf3/9\xa7\xa5`9\x995\x01\x9c\xb4\x89\xd7\x16\x12\x17\xd3X8P'
 b'-n\xe0\x15\x9d\x855\xaaMb_R\xc6\x0b\xc4j^r\xb4\xd4\xe3x\x7f\xf8\xb2\x83u/'
 b'\x86\x954\xd8\x92!\xef\xe7\x8e\xb1\xcb\x9f\xf1o\x9a\xb1\xf10\xab\xd4\xf0?L0'
 b'\x15a5\x1d\xc90\xc3Fmy1:\xef2\x93\x12\x84\xf1Pm\tn\x06\xd2C\xbb\x9d\x14'
 b'Q\xa7\x1aN\x0e\x9d\xbdi\xf4\xc9F\xd6J\x82\xf31\x93S\xa2\xdc#fv\x1e\xfetdx'
 b'a\xed\xb9c\xdb4\xec\x84\xe6\xea\xb64V|\x13\xd3\xd2%;\xf8M\xd2\xd4\x0e'
 b'&\xd6\x8b\x82\xe9\x96\xd9w\xfd\xda\xbc\x9aw\xf0\xf2\x99\x18\x0bA\x9f'
 b'\x01QC\xd5\xe7@\xd5\x95/q\x11MbHZ\xaa\xbfI\xb6\t\x02\x03\x17\xa8'
 b'\xe7\xd6\x10\xddVTw\x1a\xed,\xcc\xa6\xfb\x01\x16\xa2g\xce\x80\x034 8\xff'
 b'\xc2jP\x03\xae\xe8\xe9\xea^,\xce\xf1;l\x19s\x96~\xa4t(\x18\x8f\xa45\x08T\x1a'
 b'\x88\x13!f\x06\xc3C\xcc\xbc-\x9dAc\x9e\xc8\x92y\x08\x12\xce\x03K\xc4\x8d'
 b'\xffKc\xc32\xcb\xda\x0f[\xbd\xa2\xac\xda9TF\xd2L;\xd6H\x9a]&9\xbe\x8d]'
 b'.\x81\x85\xcc\xaf\x84>\x1f\x04*\xc9\xdb\xefW|\xc4\x8a\xc2W\xd0B\x15\xdf\xd3'
 b't\x1c\xa0\xe4\xcd\xa5\xd43\xae\x10zj\x8a\x0c\x12KQc\x87\x0e\x0b{\x00\x17'
 b'I\x11_\xf2p\xa7x\xe4\x96\x86\x04\x8bI\r\xb7\xa6\xdd\x89\x91\xbeF\r\x98\xe8'
 b'(j\xa3\xee\x87\xd4\x84\xb8\xecW\xbbS8\xfc\xefN\xd8\x84\x85B\xc6\x12\xb4\xaa'
 b'_\xb1\x91\x84\x02\x81X\xf4\x82h\x8b[8`\x8akNY\xce\xf9w\xb7`\xe0~\x86MR'
 b'\xcc\r\x99.OI!\xc4\n\x90\xf7Lr5\x88\xc26\x85\xe8\x1bo\x0b\x1do\xcb\xc0\x16J'
 b'\x05)\x88Z\xea\x14\x98"i\xb48i\x92\xcc\xd2(\x82\x8ch\xda\x82^\xd1\xe2'
 b'F\xd1k\xe4\x94w<f\x03:\x10\xf9\xb6M\xa8\x85\xd9v\xf6)\x18#B\x8b\xe7g\x94\xc8'
 b'\xc0\x10\xaf\xf8FPP\xd8\x07\xe3\x19L\xf9~\xd6\x8b\xa6\x18\x11\x86'
 b'\xb7\x82\x1dB$Q\x02\xde\x943I?B\xddo\xad+:\x9f\x1dr{\x07\x84\xcc\x0b\xeaM'
 b'\xa8K\x04\xf4eh\xe0\xacr\xc2\n\rM\xdb/\xd7\xb8\x99#\xf7\xcc\x9b8f\xb3=\x92('
 b'\x85\x0b\xb8\n\xcd\x8e8Qi\xcb\x927E\xd0C\x81\x06\xfb\x0c-\x8b\xc7\xb4\x95'
 b'\xe8_\xb5w\xf9\xf0\xad\xfaY\x01\xf9\xc9\xf0\x94~\x1f\xd60\xeb\xffa\x13\\\xd5'
 b'\xcb\xc8\xad\xeba\x87\xd8\x1b3dN\xbdcW\xe0\xba3\xaa\xd1\x90\xe5\xf1%\x84'
 b'\x8c \xaf\x10U\x9e\xf1\xad\xaf\xb2\x98\x0f\x11\x8c\xcb\xf3\xbf\xac\xc5%'
 b'\xb5\x9f\xcb\xb8^\x17\x0f\xf1\xed\xe8/\xe39\x92\x17i\x03\x18\xb8\xf3w@!\xa9'
 b'~\x05\x8e$\xfd\xb7\x05c\xde\x9e\xca\x00Y\xff;\x82X\x98G\xb0\xea\x98\xe4\xf1'
 b'A|\x08\r\xe3\xd4\xb5\x0e\xd7S\xab\xca\x00X\xcf\x1dB&6u\x0fC)fP"\xa6\r'
 b'6\xdf\x1f\x12\x8b\x8f\x94p\xe7\x0b\xd6\xe0Y\xc7\x13\xc5\xc5\xb6z\x1c'
 b'\x1d\xcb\x84\x0b\\\xa0\x0f(M{\xab+\x08\xe3\x054\xc26\xa2R1}\xc2\x94'
 b'\x9d\x07\x06s\xf8\x87 \xfd\x8a\x1fi\xe9\xe8 \xddv\x97\x0e\x07\x86Gdr\xd0'
 b'[Q\x97\x15IS\x0c"\xa9\xf7.\xb8_K.\xfc!\xd3\x16\xf4^\xb5:\xcc\xe4Auh\x9coL>'
 b' \x1c-`\x9c\x03Y@\xf0L\x02\xa3\xc0\x01\x0bB\xa4o\x8f!\x13Z\xf3\xd3'
 b'\x81\\\x0c\x08\xc3\x8e\xf7\x98\x04/\xae\x04\xd8Wm\xc1f\x06\x95\x1e'
 b'\xcb\xc9\x0bL\x8f|M\xb7\x08Hg(\x85lV\xff*\xb9\x8a2\xa2\xcf\xcc\xe3\x11Qf\xda'
 b'S\n\x9b\xb3!ygc\x06\x9dQtRd<\xa0V\xa4\xb9\xb2\xb5\xce\xcc\x9aN\xd0\xf6\x07'
 b'i\xc7c\xc71\x94\xcbLGs\x18\x14\xc2\xb2\x15f\xad1\x10\\\xd4\xf4U\xf6'
 b"\xa4\xed\x9bB\x10 \xa3'\xd6\xb4\xcc\x9c\x9eo\xcd\x7f\xfb\xb6\x8d\xc2"
 b'q\x1a\xd4P\xe8\xa5\xd3Ea5\x80aB\xa2IXy\xbc\xccD\x91\xa6\x19\x06\xa1\x98n\\'
 b'\x1a\xca\x8b\x15\xb1\xa3\xbbQ\xd8\xf4\xda\xe1\x87\xd1\xa4\xcc\n\xa5y:'
 b'\xa9\xefI\xaf\xa4F\xc5\xa1=\xfd\xa77e\xff\xda(\xb8\x17\x13\to\xa5Q\x9c'
 b'\x1a?Z\xab\x88e\xa2\x81#x\xf7\xc5\xb7$\x7fm[\x936\x15\xbb*\xee\xa7\x11dOj'
 b'\x11\xe1\x10\xd8\x96\xff\xfd\x073\x83\xcf/\xe9\xdb\x0b\xad\xc9*i\xf4\xeai{<'
 b'\xeas\xc6\xe0<\xa5\xd3\xe6\xb8d\xdb\xd4k\x066`A\x92\xc9\xe5\xca\xe2%\xb0'
 b'D\x01\xd8\x8c\xa1\x13q\xcc\x1b\x83U\x82\xb0,\x9c\x02(^\t\x84\xa2\xa0\x9c\xc3'
 b'\xa3\xf9K\x97\xdbz%\xaf\xf7\xda\x8az&\x04\xd2\xe1d(\x87o\x13Ko6\xe1\xea\xffg'
 b"E\xb4n\x14\xd4\xa7N\xdc\xa9\xcf\x81\xf3\xc3e:\xa3\x9dN\xa8_'\xdb\x0b\x92"
 b'-;Y\x8f\t\x02ff\xa2\xaa\xba\x9dM"4H\xeb\xf1aB/G\x9a\xa3\x1ar\xf5,(\x8b\xecF'
 b'3\xcc\xd1\x81\xe1t\xf9\xc6O\x0c\xc8\xb7jX\xc5A\xb7\xae|l+\x90?\xea'
 b'\xfbd\x0f\xad\xb6\xae\x83\xdf\x18\xc3\x18\x90\x10\x8d\xc6F\x17|i^'
 b'\x1e\xc0\x97\x98F\x88c\xe4\x8cg\xaf@|\xb1\xf5\xcec5Q\x9d\xccF\xcf\n'
 b'/\x036\x0e\x94\x17\xd8\x94\x1e\x98\xa8\x0f\x18Dd\xd5^{\xa8\x8a]"<\xce'
 b'\x1b}\xd8D\x81\x02\x0c\xc6\x03\x9e\xa9.\xa4Q\xedS\xcb\x1aI\t\x93\xb4\\\t'
 b'\x7fpr\xa1\xe2\xb4\x1e\xfe\xcal\xf8u\x17\xed\xa5\x0b\xa2\xf0N\xcf'
 b'\xf1\xb2\xac\xe1\xde\xddiz\x04\x90\xa6\xf5+m\xe6\xf6\xafS#\x91v|?\x9a'
 b'\xcd\x91\r\xe8\xab\x88\x97\x11\xdaoJ\x96\xef3\x9a\xbe\xc0\xdfK\x8e<\xf7;m'
 b"\xc5\x06b\\\xaf\xb1(\x05\xa7\xf2\x179!\x1ah(\x021\xee\x9d\xb2\xf5'\xae"
 b'\x9f\x04\xb0S\xbd]e7#\xdc\xda\x08\xe3\t\xbe\xe8\xd2\x16\x82\xcd<\x9d\x84R'
 b'(+q\xd9\x12O\xec\x06\x9d>sU\xb9\xc6+\x1fo\xd0\x8e:\xb78\xc2 iP-h\x91ne\x94'
 b'\xfb\xe7\x9b\x88hC\xadPL-\xc4\xc8D\\\xca\x83\xdd\xf9\xa9\xd8~\x01\x98\x90'
 b'\xd6B\x19\x14H\xc9\x08|\xf0\x84t\x1a\x9aD%{\t\xcb\x87X\r1\xd5<@x\xd2\xc1'
 b'0\xbf\x82\x02\xe8O\xc0end\xee\xed\xa0[\xf5xd\x14\xb0\x10=\x85^\xf5'
 b'\xc3G\xd5\xa8\xa7\xcc\xcc\x85f`\xf3\xa9\xa1\xfa\xcb\xef\xf4\n\xb5\xcc'
 b'\x04\xb1\x85\x0e\xff\xa1\x11)\xc5.U}:\x98\x17\xba\xe1\xc8\x1b8\xe0\xd0\x03('
 b"P\xfa'\x00\xee\xd1\x04\xddA\xb0q\x05\xc9\x8c\xd6\x98\x8d\x13\x9f8\x02\xf57v"
 b'\xd2R\xae\xa9\x0c\x9b~\x15\x1dZ\xc0\xde\xeb\xe6\xe4T\xf5\xab\xc8\xc8'
 b'\xb9\xb3\xa5#\xf6z\xa2\xfd;\xaaY\x88\xacuOh%\x99|Wd\x9dM0\xd5O\x05\x1a'
 b'\xcd\x03\x99\xdd:\xb0\x9b)\xe4f8\xed\xdb\xd5b\x89\xc4\xceN\xe9Gg!\t'
 b'M\x83\xd3N\xb4\xa1S\xde\xf4\xf3\xf9Gu^d\x0e\xde\xf2\xad\xb3\x05\x90\xe9:'
 b'\xb1 Ro\xf8o|"9L^\xe9\xf9\xc7 \x99_\xc8@\xb5\xffd\xbc\xd9|p(\x19\xc6>3\x13'
 b'sg;\x95\xd4\xd1\x05\x82\xcc\x15\x8b\x0b\xf7\xbf\xc6\xcf\xd9s]iH\xc3\x17\x7f'
 b'\x17,\xca\xd5O\xc9\xbb*:;\xf6\x07/V1\x11*\xbeX\xe0:\xf7\x0b\x84&\xf2I\xfc'
 b'}5W\xf5o\xea\x92\xe7\xe4}L\x17\x1e\xa3\xaf\xca2\x0f\x04\x83\xbc\xd0o\xa7'
 b'\xb2\x10+0\x00\xe92m\xb1dQ\x0csd`\xc5\xfei\xf8\xa115\x00\xda\x82ZM\xb4'
 b'\xf1\x91Q0\xdd\xdc\x04\x94\x8f\t=\xfb~\xa2\x07\xabI\x14\x923\xb8_\xe0\x86'
 b'\xaf\xdf]\x0b\x89\xf2g\xc1\xed\xcc\xaa\x1f\x9e\x04\x99:\xfeO\xdc\x0f'
 b'\xa0tO\xafA\xbd\x0b\xa0\x98\xd4\xc7\x02\xfc\xd9:T\xc4.\xc4\\\xce\x12.`'
 b'\xdf\x07v\xf7zi1uG\xf5.\xde\xc0\xf2\xc9d8g)\x85u\xe2\xaei\x8ej^\xee'
 b'\x10\rB\xba%\x90=Q\xdch-G}\x8f|"{\xbbX\xa5\xbe\x18\x9e\xa9\xa2B\x90\xe4'
 b'\xaa\x1f\xcc\xf71H\x94\x0c3\xc3o\xbc\xb6\x80\x11[\x0c\xb8\xef8\xc5\x14{\x0c'
 b'\xd7Z\x06\xf1cX\xd7\xc2\xf0\xb6\xe5\xa2\x92\xc4\xfd\x1f\x1ckG\xc7'
 b'\x10z\x06\x89\t\xe5/\xb8\x1c\x0cM\xb2[:\x81fqc\xbd\xf8V\xac\xb3U'
 b'\x1aS\x11\xa6\xb0J\xce\xc4\xe6\xf7r\xa2G\x993\xf1\x01\x8b}\xeb\x1cD}t'
 b"\xac?\xc4\xc0'D\x12\x90\x80`\xaf\xda'\xb8\x13\xa6\x06\xf7\x13!\xaa+\x16\xfa"
 b'\x19\xdf\xa1\xc8\xb0\x81\xf1O\xe8m\xbf\xf7y$D\x11\x0b\x00\xa1t'
 b'\xf8\xdc\xa8\x87m>\xfc\x84\x89\x83\x87\xb9^\x99\xdd\x05\xfc\xde\x03\xae'
 b')+6\xc70\x05\x8a&\x0c\x10\xbb\x14\xbf\x8bw\xaf\x84\x11<~\x80u\x82\xe4'
 b'\xdf\x1f\xc1\xfa\xd9\xd2\x9b\xc4\xb2\xec\x85\xdcZs#\x93X\xb5\xf6\x94'
 b'c\xd2\xae\x07\x8e\xb6\x1bU\x8b\x7f\xc9\xd7\x83\xe8\x0e\xc5c\x0c\x18\x16'
 b'\x84\xf1\x10\x06 \x80f\xed\xae\x07\x9fQ\xe73zM\x18.\x88A"}U\xea\x87\xe5@\x88'
 b'/\xee,\xcf\x95O\xef!\x9es\xe5\xcc(\xc71b\xad\xb1\xe6\x14\xed\xb2B\xc0vzN\xc2'
 b'\xa1\xd1:}Ud\x06\xb6Vu\x17\x90Z\xcb\x13\xe0\xc0\xc9\xbb\x18\x89\xf3\xe73'
 b'\xe2!V\x84O\xf3\x01;\xe6\xd24R\xd1w(!7\xc3\x88\xcf\xbd\x94\xab\x13v`\xcbB'
 b'Q\xa3\r|\xc7\x86A\xca\xe9\nZ\xf9\xf3\x11qD\xae;S7%\xbf\\\x89\x9d\xa0\x07\x07'
 b'R\x8c\xd1M\xc9\x87\xf6\xa0\x07\xee\xf7HjQ\xd2\x9f\xf6\xfb\xe5\\2B\xc4\x90'
 b'vhQ\xd1\xc4[\x90y\xb3!\t\x02\x9c\x1e\x85\x03.\xffm\xa6?s\x9e%'
 b"\x01\xcf\xc6\xc7\xcd^\xc9\x14a\xb1f'\x93\x8c\x05\x86[\xdfMG\xefKFo\x96\xc0H]"
 b'\xef\xf6m\x1dk\x90\xec\xa5s\xac3.\x8bI\xbd\xc4=\xdcr5\xf3$G\x1f'
 b'\xff\t\x98\x84r\xc3\x97\x81\xa8\xcb\xf4\x18\xc5B\x1e\x92%?\x02\xf5'
 b'\xe6\x16\xca:\x1b;K\xc1$@\x81\x02&5\xd1\xa1\xe8a\xa0\x8cr\xcb_\xff\xb2\xf0A{'
 b'\xc60\xc6c4NY\x02\\\xd4\x92\x988\xb4+\xf6~\xac\xbedu\xa3\x0cr@\xe1G\xb8'
 b'h\xdc\xcc\xc57\xcb\x936\x9e\x9f\xbc\xba2>?\x1d"\xecZ\xfc\x92\xbax$'
 b'\x90M\xec\x89\x10B\xf6`\xc8F\x8e\xf4\xb3H\t\x92\x1bD\xf0\xac""y;'
 b'\x04\xce\x03\xdc\xa0\xfc1q\x1a>u\nx\xd77\x14\x95n,\xc8\xdbY\xc0\x93'
 b"'\xd7\xf4\xbc\x1a\x91\x08\x8e\xf7\xfb\xba\r\xea\xa2\xc0&]\xd6\x8f\xaa"
 b'\x9e\xeclU\xedL\xa7\x8d\xd0\xb1!\xfc\xc9\xbe\x8b\xd4\xd9iw\xc7\xddU\x1aC'
 b'\x12\xbe\xae\x924]Z\xcdK\xfa\xed\xa5C\xad\xecB\xbe\xea\xf8?\x17\x0e\xc4='
 b'\xa4\x9dNm\xa0\xc1\x05EU\tW\xfc\x9a\x89i\xc8A\x9e\x05\xd6\xa8A\x8f\x00\tt<h'
 b"\x12\xa7\xb3\xf1\x0b\x16\xf7{/p'\xd9a(V\\\x0fO\xa9@\x80?Us\xb4\xa0\x10("
 b'kN\x04\xcc\x17\x13\x9e9\xd0D8\xc3\xc0W^GW\xdc\xe9,x\x90\xe8\xae\xd4H\x12\xf4'
 b'\x9d\x0e\xa1\xd1)6e\xc2\x8a\x80\x80H\x8bI&\xee\xa3J\\~x\xd2\xb3\xc1'
 b'\x99b0\xe9\x929\x1b\x88Z\x14\xfb\x89\xed\r\xb5\xcf\xfb`G\x16\x17\xea\x00\x1a'
 b'\xade\xac\x9f\x8e\xccn\x85?h1\xdfsP\x1a2:\xc5T\xd8\x1f\xe4\x18\x8b'
 b'\xf1\xdaR\x95RA\xce\x85\xab\xd1b?\xff\x12DW\xaa\xc9G\xd06&D\xa2\xa8t0\xe0'
 b'\x83\x1e/\xd8\x95\xee\xbcn\x85} \xfd\x82\xc6Y2\x8e\xf1\xba3\x13\xfb\xef\x8b'
 b'\x8c\xd0?+\xa4\xca\xd4\x85\x988Vv\x059N\x11>\xed]\x03yQ\xd75\xf2\x02GT'
 b'T$\x8f.\xc0\xde\xf1G\x18KZ\xf8\x8f\x14\xc8\\*\xe0~\x80[\x8e.\xc1\x10\x8b-`'
 b' a\xcc\xf6\xc8\xc0H\xcc\xd9\xaej1\xec\xa1\xb4o\xa0:\xc6\x9f\xect\x18\xcf'
 b'\xfe\xd7 N\xbc}\xca\x88\xdd\xe4\xb4\x13\xd0\xfd\xb0\xfd\x86*\x93D'
 b'S\x12\xc7\xebjU\x85J\x124\xf1)\x91\xc9\xa1g\xa5&\xa3\xc7\xec\xd6=['
 b'\x10\xab\xd6I\xf6\xc2\xab\xe2\x1e\x9f\xc7\xa9\x92\xc9\xbd\x06\xd7C\xdc\xb3'
 b'%\x1e\xbd\xaa\xcf$\x06\xd4\x16&\xe2h\x92;B\x8d\xa6T\t\xc4\x8c}\xaa\xd9'
 b'J\xf5Y\xb7\xb88\x058Cm\x7f\xc4%!h\x0b\x93\x0edDT\x82\xa4{\xf7"\xe6\xf7'
 b'c!<\x1f4}\x9fQ\xe1\xe7\xabgT1\x88W%\xbeK\x0f\x13\xf2\xc3\xda\xf8\xd5b`'
 b'$;\xc5?/\xa0\x98\x967\xbd\xeec%\x87R\xb6\xa5\xfa\x19\xec|\xf0F\x1e'
 b'\x86\xa4\x1cU\xeb\xe1\xa3`=\x94?\xd2B\xb6\tk\xf2\xf1\xc8\xc2\xc5\xcc\x87\x9b'
 b'hxld\x1c\x98\x10J\xaa\xae%b\xc2\x16\xa5Tk\x93\xc7u\xc3\x8fVI}\xd6\x92\x1c'
 b'H+\xc1y\x0b\xe3\x8c\xd8\x97z2\xcf\x814\xd0B\xf8\x9f\x94j \xf9h\x1d'
 b'\xe0\x93\xe0+2*\x99/\xad5\x8a\xd5B\xfc\x05\xb4\xe4)\xf7\x9cx\xbf\x00\xac'
 b'_yK\x01\xa4\xd0\xf8\xb2\xd4\x1af\xa1n\x1a\x04\xe6\xdaC\xa8\xa1\xcaGK\x7f'
 b'yh\x1bkE\x9dI.\x90\x1a`a\xed\x1f\xe4F\x1f\x93~\xfb\xe7\xc3\xab\x00Xt4\xf3'
 b'\xe2\x9e\x866\xb2_\xe2\xa3\x89VS\x7f\x8b\xbd\xf8>2\xdc1\x9c\x87t\xe8h'
 b'C\xc9a\xed[sa8\x19\xc3_\x0f\xd9\x94_[\xe3\x0c\x1fdN;\xb3\xb6\x13\xf0\x89\t'
 b'83\xb0\x1d\xaa\xc6\xa6\xa0\xd2\xec\x99\xf9\xcc\x06q\x03v\xe9\xb4\xc6'
 b'\x9b&\x1aU.\xb3\xa60\x99Q>\x95\x80P\xdd\x16a$i_F\x01\xb7\xac\x055\xdc\xbb'
 b'\x91\x0fDE.h\xd0\x93\xa1\x93\x9f\x96\xe5V^\x89\xdad\x12C\xc3\xb8\xf7Z'
 b'\xc179\xef;y7\x03t\xc4\xc0r^\xacF\xa9vAk\xde.\xdf\xa5\xc9\xaa\xd07@\x1d8E8'
 b'\xfb$\x9cG\xdc\x0bs\xc8\xe5\x9f\xf3\x9b0*\xb2EHY<n3\xf1,KXkz:\xa7N\xe7\x90'
 b'\xfdiu\xfe\xcc\xba\xa4\xfd\x80a\xb0C\xa8!R~\t\x1eh\xdf\xcf\xf9\xee\xd2'
 b'\xe2\xb6D\xec\x8c\xd5uv\xbd&tM\xf9\x0bq,\xa4G\x1d\n:mS\xbaA7\x0eJ2\xfa\xe3?'
 b'>\xcb}V\xe4,K\x87\x8a\x82\x90\x8eL\xb8\x7fJa\x95\x01\x96%N6\xb1\xf4v\xa2\xfc'
 b'-\xa7\xdd2\x1bgp\xb2X\xaf|\xfd\xf4\xd23\xe6\xe1Q\xe6~\xf4\xa0\xad\x90'
 b'X\xd9\x08\xa0\x7f\x97\x9e\x88\x89/\x18\xd0\x8f\xaf\x07\xc1F\xf7)$'
 b'\x82\x84\x15O\xbb\x1aJ\xb7\xe4Y\x00\xeb\x19\xff\xab\xb6\xad`\xa5 '
 b'\xc0D\x9e\xdc\xb6\x00J\x95=AP\xafnfm\xc3\x90\x95\xa8\xe9\xef>p\xbaG+/\xd6'
 b'\xa9SI\x08\xabSdC\xd9\x1a\x83j\xa89\\az\xa5\xbf\x1b\xd4UL\xd1nC{t\x83\rt\x06'
 b'\xb4\xf5\xd3z\xe3\t\x81\x9bw\n\xc3\xb1AncMGi\x18,\xae\x16\xa6S\xea\x1f\x96m'
 b"5'\xb0{\xd6|\xe5\x12\x0f\x13d\n\xa0\xa6h_\xe6gt\xbc\xafk0;\x87\xc6\xf7\xc9"
 b'\xed\x86\xd9\x06T\xd9\x9e\x99\xc5\x9fn\x0e#\x01n\x01&\x88\xc3;Y\xbc\xbb\xc3'
 b'\x9ez\xdf\x06\x9b0\xa7\x87\x8e\xce\xd0\xb8\xb3C\xc0C\x08\xc0\xc0\xcdFK;M'
 b'm{\x9e\xce\x9c\xa2M\x08D\xb0I\xdf<\xd8\xe5H\x8e\xa8\x90\xe1,\xca\xcd\x8f'
 b'\xd6\xda25\xfa\x80\x93\xae\x87\x1e\xde\xb5\xecJ\xe2\x93:<H\xe6UA\xb2\xb6'
 b'\xab\x9c\x16\xe7\r\xec\x96\x13|\xe1\xd9@Y\xc0>\xa1t\xed\x08\x90L\xa6\xea\xb8'
 b'S\xf5\x80\x96h\xf9\xfaK\xdaY!{\xa0@C-{X\x8d\xf5\x15K=\xcc\xc4-7\xdc'
 b'\xbc\xe1\x8c\x00\x1cQ4\xdc;\x8c\xff\x11\xc5\xaaZ1(\xc9^\x9a\x0b\xd6|w_=\xf0T'
 b'\x86hU\xf7\x14\x06I[s\xcd\x9b\xd3\xa1\xc3\xc9\xda$\x84\x83\x99I\xf4\xfa\xa5'
 b'\xfd\xf9I\x82%\xb1(X\x14\x8c\xb0_\xad\xc3|\xd1\xc1\x98\xd9\x18\xad`\xc06'
 b'\x01\x00\\\x83\xcf@<\x99\x9f&\x81\xbe\x90\n\xff\xf5xT%\x81\x9bQ\x0f]'
 b'\xe0f\xecZ!\x97\xb26\t\xd6F\x01\xa2\x18\xab\x8f\x05\xc8\xaf\x8e\x8c\xee\xb16'
 b'\x00\x0f\x04\x8dD\xc8\xae$<\xc1\xc0\x90\x1fK\xd1Ei\x17\x19\x16\x0f\xb4+\x96'
 b'\x1cx\xeaG!\xf4!\x81\xd0\xae\xf2\xd5T4}\xea\xfb\xc26:b\xb8fI"r\xc2\xa9'
 b'\x92\xc7)Nk\x88q\xc9E\x8a\x0c\xb2j\x8e\x11z\xe5\xa8,X\xfesK\x8b\x12\x0c\xcc2'
 b'\xa2I\x08\x15\xb1\\\x04\xe3@\xa0\x8b2!\x03:A\xd7\xb8\x9a4%\x90@\xd5\r\x88+.'
 b'%\xdcu\x003[\xd1k{0\xda!Q(\xd5?\xfdqy\x96\xec{T\xf1=Z\x1b\xf0Q\xa6\xbe\xa7'
 b'3\x9a{\xe0w\xdd\xbe_\x02\xd9v\xfa\x87vR\x12\xf3i\xdc\x1b\xe4\x80\x85 '
 b'nS\x80\xac4\xc1\x89\x8e>\xbe\xdb\xbf:\x0c\x99R[\x9e\x1f=\xe7z\x9eY'
 b'o\x82\xfe\xc7\x91\x1f\xeb\xe9\n5\xb6\x9e\x97\x9f5\xb8\x18\xb4\xe4\xad'
 b'\xe3\x05\tg\xc7\x1bp\xcf\x0f\x84C_\xd6Lq.|h#\xa1\xddU&\xdd\xd487\xc0'
 b'wd\x19\x96\xacb\x83\xe8}Rv\x9f\x0f\x85e\xe8\n\xe1$\x85\xcbfi\x06\xc1pcQ'
 b'\xae\x91\x899\x80\x06\x8f;\xc5d\xcc\xc4b\x11;\xcb<sop:\xa0\xb1\xc6'
 b'\x8e\x15\xfb\xe7\x17\xce\xde\x8a-\xb6\xef\x8aL\xca6\xbb\xa2s:\xd1\xdbFTv'
 b'\xaa\x14QuB\xd3\x9d\x9b\xd7\x897\x00t\xcfj0\x14j&\xb9\xbfz\x9b\xc1#2W\xcd'
 b'W\xea\xa9\x84+UH\x96\x9f\x99\t\x06=\x9b\xd6\xef\x83g"\n]\x10\x0eb'
 b'\x1a\x06\x7f"\xca\x11\xdc\x01\xbdB\x02\x93u0A\\%\x9dG\xf4H\xc1\xca\xff'
 b'5\x1dh\xfb+\xc1L\x0f\xbb\xdb\x81\xaa\xcd\xf8H[\xfc\x9eD=\x1f\xaf\x18\x84'
 b'xZ\xbfd\xbe?\xf5\xed\x80\xfa\xc0\x9eU\xea\xa3\x1e\xb7H\x10\x97\xed\xe25D'
 b'\x88\x18\x99r\xbdnN\xa5\xa6\xd7~\t\xa9\xf5\xd5\xfb\xc2\x02\xb9\x07'
 b'\x80\xa2\xb8l\x90\xe5\x9f\xd9\x04\x87d`\xca\xf2\x8e\xd4\xef\x12q\x06'
 b"R\xe1\x9c\x00ia\xe8T\xc2\x8d)\x86\x04l6\x99\xc7.q=\x10\xa4\x1d\xfa\x1eO\x97'"
 b"\x14\xc9\xcb)\xc4\x0cD\x8ex\xcdC\\U\xaa\x95gL\xa3\xe5'5>\x96\\\x10_b \xe4VMi"
 b'8:q.x\xcc\x16\xe6\xd0\x9a\x8d*\xb8\xb0\xd9x\xb9\x9c\x8d\x83\xb1}\x05\xd5'
 b'\xdf\xb4\x1ea"\x89E7\xb1\x9cuN\x12\xf8\x0b\xd3,\xf9\x838\x04\xa9\xe5\xc1b5B)'
 b'\xa2r>x \xc1j#8\xbaOn\xe8\xd7\x17A5y\xdf\x11\xae\xa1\x11\x8b\x04[\x86\xf9'
 b')R\x7f\xe1x\x80\xdf\xac\x00\xe2\xd9\xea\x12ZTL\xcd"\x8c\r\xef\x9e\x07\x89'
 b' \x12\xbeA\x1e\xdd\xa4\xe5\xdcK%~\x90\xd6\xcc\x8f\xfa\xa1\x8c\xeb'
 b'w\x9c\xc0\x1c\xfa&t\x1f\x04\xf4`\xe0-6\x0e\xdf\xd8\xbe\xe9p\xa6\x8e\xf3\xab'
 b'\x9aJi\xadL\xfc \xa6\x81N\xc0\x18ik/x`u\xb8\xc2\xe6\x98\x14\x9b\x02"\xcf-'
 b'\xc9^\xe4\xfc\xd0\xa6m\xa0?\xb9r\x13=\x1b\xa4Y\xbe\xa7&\xeb\x8a\x813{'
 b'\xa1\xe9\xd0\xc5\x9d\x0c\xe4\xe9~L\xdb\xd4\xa0\x0e\x18zF(Q!\xf8\xc94\xcf'
 b'xVU\xef\xe14`\xa9\xb4\xa2\x19Ej\xd3E7\xaaG\xbeU\x89\xd0z>\x02\xd8\xc6\xf7'
 b'\x92\x13\x8d$[\x02\x19n\xfa\x11\x1b&c\xe8-\x93\x90HU\xcb\xa0|\xb0\x9d'
 b'MQ\x84\x1a\x0c6\r\xc6\x96\xf6\xd0\xe2\x89#\xad\xe5n\x96Y\xf2\xde\x9a(E'
 b'*&\xdfY\xca4\xe7\xed\xbcY\\s\xe2\x90\xe2\xae#\x8ec\xaa\xd5\x1e\xc5\x93'
 b'\x0be\xd2\x04z\x0b\x11wt\xa7\xc9zZ\xf1@\xd0\xfe\x07C\x0c\xfe\xb3\xcc\x95'
 b"\x0e\xc2\xa5#\xd4\xfc\xe8:\x95\xa0\xe6\x97\x18\x00\x03'\xca\x10x&"
 b'\xea\xd8.\xf6\xc4\tpI\xe7K,\x1b\xed(\x05\xd4i\xb4H\xf9!$\xab\x9b'
 b'"\x84\x13\x06\xd56\x11\x9c-"\xeeZ\xff\x99\x9e\xb69\xb9\xf3.\x01\xe9Y\xa6'
 b'\xc1\x9c\x00\x02\xe6v\x04\x1e\xf4N\x82<\x10\x8e\x13\x05\xe9^D\xae'
 b"\xab\xa8\xf9\xab\xf1n\xd4k\xc6V'q\x92m)f\xf9\x16=7\x0bs\x8e\x8e\x83mN\x15"
 b'\xa5y\xe4}\xcf\x9f\x8b|f\xfd1\r\xba\tb\x1b\x82ekd\xa4/\x10\xfa'
 b'\xe0\xaa\x88\x8cf\xb5\x0e\xe9:*\xb6\xc7\xe6sU}p\xb7\x03R\xd1iW\x97'
 b'8\xaf\x0f\xf5\xcd\x15\xbe{^\xb1\xd5%\x1e\x1d\xb7\xd0t>\xcc>\x02\\\xddr'
 b"#Z.\xad\x14\xfe\xb3'\xady\xc9\t\x81>,\x81\xbbn}\xd8\xe8\xc86\x8a\x92$\xdbV"
 b'\x04\x94\xec\xe9\x0bq\x1e\x18\xd9\xe0,S$r@\x04\xf1N\xb6\x9d<\x98`\\'
 b'\x07e\xebm\xd4+\xb3Q\xb3d\xdc\x01/\x8ab\xa9\xf38\xb72"tB\x17%bFX\xe0d_\xc0'
 b"\x9d\x04\xde\xc3\x19\x0e\\\xcb\xd2\x92\x95~m\x8d''\xfe\xda\x07?(\x1bT>"
 b'k\xde3ap\x10\xfcv\x1f\n\xde\xf9\xed\x9c\x87\x92\xd5[0\xe8J\xb0"\x82'
 b'i\xdeZ\xebJ(>\x07\xf2\xb1\x8d\xe9?s\xddJ\xd7\xad\x15\x91\x03\xd9u\x85'
 b'k\xad\x93&Kws8w\xd7\xbdJb\xf8dO\x0f\n\xabN\xa5\t\x92\x0c\xe0\xdd\x8b\xdd'
 b'\xec\xf3\xa7al\x8a\xabcq\xc6\xd6]\x14j\xec\x0f\x0f\xcb&s\x19<52\xc2\xc7\x07K'
 b'\x98\x11L\xa1\x85\xae\xc15;\xae\xa5d\xd8\x00T\xa8\xb80\xba\xa3\xc4EI\xea'
 b'\xa9)\xbbw\x93\xb42\xa1F\x1dL#\x8b\xffYr\x1b/\x03\xf7\xa9\x0cr\xa9'
 b'\xcf\x90\xe2\x8f\x96\x9d\x89\x13\xc9,\x89Z\xa4\x8c\x12\x08 \xce\xf1\xaa'
 b'\xc4s\xfd\x01\xbe\x8bT/\xc5\x16\xc4\x00 :\xbb\xe3\xff;\xfd\xc4`d\x1a\xb3'
 b'-"\xa6\xc9-\xc3$\x13\xe9SIN\xe5\xdc\x01\x98\xdb\x01\xfd\x03\x83p\xd1\x1e'
 b'\xbd(\x9f\xbb\x87aa\x9c\x8en\xb9e\xfaP\xce0`\xedV\xa8S\x08\xfbk}\x99U\x9a'
 b'jF\xcd\x04o\xf3\xc2\xc6\x0f\x9d\x1cR\x99\xbfh\xd8\xe7\x90w%\xd8^\xb2\xc7'
 b'Fh\x83\xf1l\x19)\x08\x84\x8c\x9a\x17s\x11\x97\x8e\xf7\x8b\x12+\xe5@\xbaf'
 b'\xec\xce\x85R\x17Z\xc4V\xc5y\xc7\x98Z\xc4c/\xb4\xc4\xa0D\x1eV&\x89Pe\x17\xaa'
 b'\x17\xa39\xf5Oj\xe0\xad_&\xec\xcc\xf1\x11\xa8\xd8\xa8\xb1\xf6\xc0'
 b'&\xd7\x08\x00\xedH\xb0\xfa\xcd\xdf\xaa=s\xc16\xdb\xa6M\xc3K\xc1ZP\x1a'
 b'85\x83\xe2og\xd0\\\xc8E<x\xde-s\xd17\xa4\xcf\xfe\x8e=x\xde\xcaO\xf5\n'
 b'\xc9aT\xcc-\x12\xd2\xa1\x04]\xc6"J\xd8\xeb\x14\x19\xa6\x009\xaa~G\xe3q]m\xce'
 b'\xd2V\x13{\xf21J@\xe2\x01C1E\x93V\xfe\x90z\x01I\xe4\x03t\x82\xc9:4\xc2'
 b'\xa4`\xa7\xd1&\xb5\xe61\xa6\xcf\x02\xb5\x03\xeb\xc9.!9\xd1q\xf6\xc3P\xbf'
 b'dm\xc3dP\xab1T\xd4#\x85\x9819\xdbfQ}?_\xd0\xdc\x8f)s\x1c\x16\xd1\x18j7\x8f'
 b'T\xa4Q\xb4\xb87!\x92\xec\x15\xc6\\\xe8p\x8f\xa0\x13\x81\x0c[\x88\xd9\x17\xc0'
 b'\xf4r\xcc\xf8\xa0v\t\x16\xca\xb0\x153\xfa\x98\xfb\x1b\x11]\x8ee\x8d\xd9\x1e"'
 b'\xaf[\xb5)\xc2M\xf6\x1b\xcb\xbe\x05}\xeem\xf7\xebm\x12\x81\x9b\xcc}S\t'
 b'z\n\xc3\xa3\xa2\xf5|\xf6\xf6f\xcc\x83\xd1\xd9I*V\x84\xeb\xe9XU\x1c\xbd'
 b'\x19q-Ao`v\x13.`\xf7\xde\x98\x14\xeeb\xa6d-\xbc\x86\r\x05\xbbo>\xe8\x1d'
 b'\x7f\xab\xf7rx\x8e\xc9\xf4(\xcb\x00\xe6\xc2\xa2\x98e\xb4\xcb\xc6\xa2'
 b'q\xdd{\xf3\xe9\xc6\xec\xc3j\xa8\x93\x88\x99\x1d\xc9\xd5\xc7\x8a\xbb\xbe'
 b'\xcf)\x9d\x99C\xd9&G\xa8\xb3\r\\\xaf\x14<\x14\xa5\xa2\xe0\xc1\t\xdd\xbc\xc4'
 b'\x19\xe7\xfcZm#\xda&\x11\x89\xe3\xfe\xac6\x9aM\xdcG\x80:rbY\x9a;?f\xe3'
 b'\x9cX\x9bP\xb6B\x132\x02\rxg\xd1\xe0iy\xac\xbf\xb5\x9e\xa4\xc8\x06s6Kshbsli'
 b'\x05\x8e;\x90\xb1\xa1\xd7\xda>m\xec\xd0\x1c\xde\x9f\xd8b\x98\x9e\x04'
 b'\xf8\xe3-i\x87p\xa2\x96{\\8\x91\xcfEG+\x96h\xa5\xf8~*\x03\xa3J\xecT\xed'
 b'Xe\x1b\xd1U\xf8)\xf4/\x1e#(\xfa\xb0\xb3\x00O\xda\xa2!\xdd\xd3\xe1R'
 b'\xf0\x80\x82\xe5/\xf0\xa4\xe5\xf0\xd0\x95\x8f\x1c:C\x1d\xe8\xd1WH\xd3\x99he'
 b'\x81\x17\x87\x92d\xa5L\xe5D\x90\xb3>o\x11\xd8\xc4\tC\xc8]%\x0c#n\xbd\x7f$\t'
 b'v\xa2>|m\x90\x14\x90H\xd2\x9b\xb2\x19\xfd\xfa\x96I\x1a\xbbMh5\xfa`IT;\xe2'
 b'\xe4|\x1c\x0b\x97@hP\x15}\xee%}\xcdD\xaf\t\xfb\xbe\x95\x19W\xaa\x8a'
 b'\x08.\x8b}\xb2\xf6\xdb\x8e\x13\xcb8H\xb9\xa7FSJ\x10\xcd$\x1f\x9e"_'
 b'\xc7\xe3\xc8\xbb\xab\xc9\x8f\xf3=-^N\xfd\xc9\x0bR\x8am\x1e[dI_A~j\x14\x8f'
 b'\xd9\x05\x0be\xbeo\xc6\xa15C\xc1\x14O\xf6\x10\xd4\xacFz*x\\\xfc\xbe,*\xe3h'
 b'Z\x0bK\xf7\\AD\xbd.\xe5d\x92J\xf7cW!i\xb8\x07\xcc\xd2^ `\x8d\\\xe5'
 b'\x8f\xe6\xc8\xb2\x15\xc7\x1f\x0b`\x8e\x92\xde\xb6=!\x0c\xa1\x90(0'
 b'\xae\x11\x8c\x83\xc3\x0c\x99\x055~\x00\x03=c<\xf3\xc2\xcb\x8f\xfc'
 b'\x0c\xdf\xb3:\xfe\xa9\xa0\xbb{\x1a2\x82R\t\xb9Z#\xb4\xd6\n\x17J\x9d\xa2'
 b'\x00\x029<?\xd53\xe6\x00\xb0\x15\x04\x9a\xb4\xda\xb0?\x1b\xe0\xc9?iaG'
 b'\r\xb0\xdb\xd4\xfe\nX\x16\xcc\x02\xb4DX\x15S\xb1a\xc2\xa8\xceh\x04\xc0\x90'
 b'\xb0\x8c\xb2\xa5\xddM\x90\x99a\xc60K(e9\xbd\x86\xb5\x9e\xf9\xe7\x0e\ng'
 b'\x13\x80\x99\xd3\xd0reqq0\xfb\x97\xeb\x8d\x98\xb6Nb\xc4\xda\xa1\xc6QT'
 b'2\xaf3\x043$\xae\x05\xa6\xa4\xc4\xffc8o\x8c\x15Dm\x1e^\x80wN\x1a\xca\x94\xca'
 b'\xd9\x94\x15\x86\xf9M`\xa0\x14?N\x1du\x9cy$#!\x87E?Q\xdb\x96\xc9\x07\x8e\xf1'
 b'&5\x11X97\xc2\xaf\x07\x06D\xfc\x07\xc8\xb5g\xf03\xf8\x08\x88TR\xc8'
 b'\xf1\xab\r\xe1\xe5\xd2\xa7\x9cA\x02=H\x85\xae\x00\xc3m\xbd\xbc\x06'
 b'\xf7\xf6\x9c\x89\x19a\xddN\x0b\x1b\x18\xcc\xdcv\x80\xff\xaa\x10\xae\xa4'
 b'd\x11\xe4\x86\xce`\x8e\xce\x80\xbc\xb2\x01\xb4\xab\xeb\x97w\xaa$F\x15*\xd1s'
 b'&\x84\xde\xaeE\rfc\x91\xd0&Z\xc3\x85\x88\xdbv\xdb+Q\xce7\n#6\x8e\xf4\xdd'
 b'\nca~6\xe8A\xa6V\x8c\x0fF\xbc\xec\x8a\xd2_\xb1\xf5F\xc4\xaf\xc5\xfd'
 b'\xc2\x9f\x98;A$\x7fe\x06Y\xb4\x15j\x82\xbf\x04\x00o\xf5\xb8\xb86\xee*'
 b' t\xac\x08\xdaB|\xf38a_Nc\x02\xee\x8e\xfeD\xdd\xda\xcb\x10\x17\xa8'
 b'\x88\xc3\x17n\xe8\xfbK3\xe7\x89\x8a\x97b\xc8S\x1e\x03\xc0w\x8c^\xde\x17\x90'
 b'\xf3t\xfe\xcc\x1bl,!\xdb\xb9\x06\x805\xf6\xa8$X;\x87\x18\xd0:\x8e\xaa'
 b'\x07\xfa\x1c-\xb3\xbb\xf1\xcd}\xab\xf8\xdf\xbb0\xac\x03\x05\x91\xab\xff'
 b'\x10J\x01\x92\x80\xf7\xe3\xa5\xea\x9b#(\xd4\r.\xb3%\x16\xecCu\x9b\xc1]'
 b'\xf1ZB\xf3\x99\xb6\xfdk\x9d\x91m\xa7\xae\x7f1\xa0\xcd\xdc\xca-\xfet[\x9a'
 b'\xa5\xd51\xd9%\x08H\xd0\x82;\x1dG\x154\x05k\xe5\xd5\x92!+a\xe0\xe8\x1f\x03{]'
 b'\xd8\x12\x1aC\xd2+\xbbV~\xc4\xa7>\xd1=\xa9\xa7\x18\xc4,\x14\x02\xc4\x7f\x00'
 b'\xf1)\xd6\x1d\x82\x90\xa8\x0f\xd1\xc0\xf8p?\xd5\x12V\x04\xf8\x926'
 b'\x9c|\x1b\xbarZI$\xcf,\xf6\xd8:A\x11\x8b\xce\x07\xd7\xfe\xc3p\xc5D\xd1@UL'
 b'\x8b\'m\x11\xc2\x8a\x1a\xca\xd7\x13\xed\x1dr\x05\x89Q\xe9\xd5D\xb0*\x1d"m'
 b'\x84\xd9P\xdf\xc2|NT\xe2@\xac\xa09\x01\xa9\xc0({\xb4CD\xe4\xa6$\xa8\x9a\xc2F'
 b'\xc5\xc2\xdeD\xff\xa3P\xef\x1aD@\x01R\xff\x06\x00\xf7\xff\xd7\x1f'
 b'\xd5\xe6\x9e\x92\x8a\x8c\xc3\x06\x97\x03\x05\xc1\xc0C\xfc\x19az\xb7\n'
 b'\xb4!\xf8q\xab\x14\xb3f\xda)\x0c\xbd-\xef\x10L\x96%\xac\xd8|\x94p<\t<\x83t'
 b"\xc9\xf4\x9f'\x11\x02Q\x16]\x18\xe4N\x15Dk\xa0\x90t`|\xe1\xff\x0e\xa159uA"
 b'(}\x13\\|\xa0n\xd4\x8aH\xd0\xdb\xb9D\xda\x07\xef\x95S\xc4\xdc:\xac\xa9'
 b'^w\x8f\xaf\x0f\xcc\xa66\x10w\xc2\xb8\x01~\x13\xa8.\x14&\x9f\x9f\xf8\x92\xcf'
 b'A\x0f\xe0=\xb73\x84\x1a\x0f\xb3e\xff\xc2\xfe\xf3.\xa3\xa92\x92\xa5n\x9b\x96'
 b'\xcb.\xfc\x11\xd6B\xd0K\x1a\x1d+\x86F\xb4\x9f\xee\x91\xf7\xa6D\xb6:\x8aQ'
 b'\x0c\xf8\xf8.\xc2\xab\x93\x9b\xc6\x82^cZL\xffF<*\xca3\x16\xba\x06\x90'
 b'\x1f\x87\x9d\xe2\xc3i.\xf9\x1b!\x80||S\xd7\x1eX\xca IzEfOY(@\x14H\xd5P<'
 b':G\xf7\x0c\xb5\x05\xd6\xbd\x84(\x89\x01\x80\xceW\xd2\xca\xcd\x06\xb8'
 b'\xf3\xfa\x08Ww\xbfjYC\x96\xb3\x8d>\xdd\x8d\xa3\x9fKM\xc1\x8e\xd4a\xa6'
 b'g\xad;\xe9D\x051S\nY\x80\xa7\x00\xa63\xf2\xe9\xd8\xc2\x9a-u\xf6&YO\x1d\x89'
 b'\x1c\x8e\x04\xba\x07\x8f\x00\xc9\x83\xe6\x16\ny\xa9\xd4\xe1\xbc\x07t\xe5'
 b'`!\xf7fR\xb2\xf8q\xf07\n.:\x0b\x19\xa3\xb8\xfc\xbc)\x030\xa7@Rb*!@\xca\xd8)'
 b'&\x87\xa3\xba\xb3\x85\x80\xc5\xa8\x16\xa9\x98\x01\x84F\x7fs\x1c\x1f '
 b'Q\xa1\xdf\x8b\x0b|\x92\xc9\\\xa5\xbe\x97\xab\xfc\x12\xb2]\xd1\x98\x8f'
 b'{\xcaH\x1bvN\xb0}\x95Xp\xcd\xecJ\xfd\xf0)\x7fOf~\xbb\xf3\x82D\xed\xdb='
 b'\x1b\r\x19~\x86\xad+`R\x9c\xfa1<Vv\xb9x\xbdL\x87\x1e\x9f\xabV\xc2b\x1eD'
 b'\xa6O\xa5\xe4\xf0S\xe0\x9c>#\xd8\x18v\xdc\xf3\x12+\x9b\x9a\xf2\xd7\xb2\x9c{'
 b'\xf00R\x83\x86\x94(z\xe0\x8f0\x98\xdf\x1e8\x06/\x02\x9a\xbe\xe2]\xf3#'
 b'\x10"\x06\x9e\xfdt\xee\x14\xd4\xd4\x84\x07\x17\x89/p;>A\xe5kh++\x1bM\xfdr'
 b'\xd0`C\xd9D\x0e\xa4\x7f\x8e\x82\x84W) \x06b\xae\x1fL\xb5\x80\xe0\xc3\xab'
 b'A\x9c\x91\xe5?5!H^Ej\x8bQ\x98\xe5\x16\x11Q\xca2\xfe9\xe3\xad\xb3x0Z??F\x9a'
 b'\xbbH\xe2\xd4fkv\x11s;\xdd\x123\xe3\x98C\x95\xe1>\xb0E\xd9\x85\xb2\x88v2\xd8'
 b'7\xfa6B\x99\xf0\xd5\x1c\x08\x88\xb5\xc5\xaa\x0ed\x06n\x1d,\xa4\xac\xaeK\x7f'
 b'\xb6\x8f`LP\xd5\x06\x9e\x15\xb7\xb0Z\n(R\xce\x01o.B\xee\xd3\xc4\xdc'
 b"\x80U\xea\xd7'\x87 \x8b\x06\x89wGo\xbc\xb3jq\xd3\xeb\xe2\x87\xaaw/\x02<\xeeK"
 b'\xe5g9\xda\xac\x07\xfd\x81\xba\xbd_\x9fUd\xc3\xc5\xf0|\x92a#\xe3"\x0e'
 b'\xda]f\xde\xd68a&8\xd9s\x04\xa9\x10\xb5\xbb\xc5U[\x19z4\xed\x8c\xb5\xe86d'
 b'b\xd0\x10\xc9\x8eh\xa68\x02\xba\x8a\xc4\x88\xd2&\x9a\xb4v\x80?4\x15g\xc9'
 b'\x95\xa6K\xd9)\x17\xff\x0b@/\xc2@/\x00G6\xaa+\xc0\xa7\xe9\xa5\xd9\x99>(/@'
 b'\x0f\x86\x9cp\xbe\x04\xc0\x19K\xa3\xe9H:\xf3\x13\xdf\xd6\xeaU\xf0'
 b'\x7f\xca\xff\xe1\x9bn$\xeb-\x1d\x1c\xe2\x9c\xce >\xe2\t\xfcxb\xafL\x88'
 b'\xa0\x12\xbf9v\xc2\xb7\x03\xb9\x04\xe0\xf9DEs%\xa9\x07\xec\xb8|-\xa7\xd3'
 b'\x16\xad\x96\xc3\x90\x81j\xa5\xa5O\xa8\xfe\x00\xdc\xdcq\xc9\xad\xa2:'
 b'\t\xed\xe1\xaer\xc1\xd1v\x15S\x87x\x84\x84$M\\\xbc\xe5\xe3\xeen\x95\xb3\\e9}'
 b"\x13| \xf3\x9a\x803\xd18\xe0\xf0\xa5\xf7\x94\x84U\x05|<\x1ch(\xb3'\xcd\x9d&<"
 b"'\xf8O0\xcf\xd6`\x84\xc5P\x9a\x89\xd2H4\x84\x95\xfdk\xf6\xcc!D>\xd1\x8e\x05g"
 b'eVN\xec\\\xf4\xb1>\xdaJ\xf0\x03\xb1\x83p\x01\xc5\xe3\x8fr\x1c\x03\xdf\xbe'
 b'@\x10\xb4t|X>\x1d\xba/\xbf}\xd7\x85\x0f\xcdI\xb1\xb2\xd1\xbaP\x98\x84'
 b'\x91\x9b\x8d\xc5=O\x8f\x11\x17\x85\x0f\x1d\xcb\xfft\xf9\x18\xa8 ]'
 b'\xe9\x0b$\xa0s\x10\xf9T:\xf7\x90;y\x1dSx79E\x81\xef;\xb3\x12O\tq\xd7%7\xe4H'
 b'\xd0L\\\xd09\xacS\xa0\xeb\x8b\xf0D\xfd~\x9a\x8f(\xedO\xdd\xa2\xb4\xb0<'
 b'[\x19\xab\xcaa\x9a\x9ag\x97\x9dS\xe7\xddl\xae>\xe7 \x1e\x1fZe\xfdv=k\xf7\xe9'
 b"b\x1e=O\x8f\x9e\x15kGV\xc5V}\x0f\x0b2\xe43ZV\x190<\x17\xcd'>\xa9 \xb0\tc"
 b'|u\x90\xbeU\x8b\xedXS\xbc+\xfb\t\xa1\xfd\xe8J\x965@/\x055Y\xe2)YJA\xed.6'
 b"\x8c42C\xce\x94B|#\xf2'\x1c\xa8\xd2:\xfe8]\x15g\xc7\x8f\xa6;\x1c\xa6d\xf9"
 b"\xa1\x18\xfd+\xc7A\x01|\x8f\xeb\xb8\xb1\x15]':\xdd\xc6\x85h\xf5eJ\x1a"
 b'\x0f\x03\x1eZ{\x8e\xad\xae=cw\xcf\xaf*\r\xb5\xbbn\x86\x9cg!@b!\x80+\x83'
 b'\xc0\xc4~h\xe8@\xa3\xb6\x19\x0f\x00\x81\xf51M>\t\x11\x1c\xf6(\xeb\xc1?'
 b'\xb8\x03;\x18\xc0\xde\x03:\xf6\x1ea;\x0f\xdeX\x1c\xb6\x11\xb1F\xbb%\x95\xb1'
 b'\x8dHv\xcd\x17<@A[VW\x96\xa7\x15z\xa8R\xf2c\xe2\xd7\xc160\xcf\x07\x1e\x1a'
 b"mc,\xa7MZ\xaa\xf0g\x02\x05\x92'\x93d\x14U-`A\x9c6\x1e\xc76\xff\x80\xfc"
 b'\x8b\xce\xcb;\x06\tX\xfbC\xfc\xf1&\xbb\xc3\xa7\xe9\x1eT\x00_\xe0iz\x82'
 b'\xbcQg\xe9\x87\xc0\x83\xc5\x83{bWq1\xc2\xe3\xf0\xa9\xf8\x92\x99<\x9b\xd2'
 b'\x1c\xc4\xec;{\x9cE\x9b^\xc4\x04K\xf4z\x85\xd6D\xcb-J\x85\xaa\x92\r'
 b'Z\xc0E\x15\xfcy\x8f\xc6"\xf7iu\x1f\xc6"E\x84\x06\xcf\x8f#z\xe5\xfd\xd1lC\xcc'
 b'\xff\xda\xf88\xddA,?\x14?\xd0\xa0\xe6^\xe7+e\x10\xff_\x8c\xd1+\x14\x8dDF;'
 b'\xa4\xdcMr\xd7\x18C\xe7l\x9c@,\x1e\xc5b9\xed*\x12\x1ei\xe6\xa1\x08 Gb\xc2'
 b'2JqY\xb1_\x815\xc9\xc5\x08\xcd\x1dH\xf3\xf0\xea\x9d\xa0\xc1s\xd0\xc1\x89'
 b'\xadI\xaa\x89\xb22W\x01\tFq\x03\xb1\x93\xf0\x89\xc5\xce\x88\x08'
 b'\xae\x85\xb4\xe7!\xae\xcf\x0b\xb3\x9e%k\xd5p=\xe2\x10\x0e\x8b\xe7'
 b'\xa1\xac\xea\xaa\xce<ix\x1a\x89\x97\x13\t-\x7fH\xdfe\xa8\xa4\x04\xda\xf8$'
 b"\x05\xd4]\x02'7\xe9\xb1\xfas\xd0<\x8c\x06\x8a8\xdbG\xe7\xac@f ~\xe8\xee1\xff"
 b'\x19U7\x9f1@\xd8\x84b\x18Qg+S\x81\x0c\x9dU@\x9aH\x8af\x83\xd6\xf5N\xa6'
 b'\x82%Q\xe4[\x02\x0fN&\x10\xbd\x8eG\xc5\x01\x8a\xa4\x02\xb1b\xaeT~+\xfaP\x92W'
 b'\x90\x10>\xc2pqH\x87L\x92\x06\xe8\xabJd\x8c\xa7\x06?\xa3,\x9eKi\x7fr4C'
 b"\x89\xb5\xf1\xd1\x18\xb2\xe7\x81\xd2\xe6\xed\xdcj\xcc\xa4'z\xf2Rw\xc7U\xe5x"
 b'1:\xc4\xd1\x8dh\xe7e \x1d;{Yb\x8f{2\x83y\xfb\x16\xb3\xc76\x98\x88\x12\xce'
 b'\x17L\xe9\x97 A^^%\xa1]\xc6p\xb9\xd6w\x14\xf4W\x92D;\xd3g\xb2(=_e\xb6\x93C'
 b',\xfb)S\x8e\x1b\x0c\x9d.\xf8\xfd:\x02\x99Cy0\x88\tI\xa7\x86L\xb2H<\x14\x16'
 b'\xd9\xc6\xe34\x97\x00m|\x91C-\x0fX7\x8e&\x1c\xe9\xd4\x85\x19\x1b-\x17-\xd3oB'
 b'eA_\xa9\x88\xa0\x8c\xbd\x81\x97Q\xd2\xcc)(\xa7XP\xd2\x8c\x80\xc4P\xdf'
 b'\x1a\x9e\xd4L\x07\x1c\x18b\xfcW\xdcZ,\x94\xd9*2\xa6\x95\xbb\xff\x1b\x99\t'
 b'\x12\xd3/\xf6\x15/\xd1.<\xba\xcc0$\xd4\xd0f\x92\xaaa$\x96V\xb5%qa\xc9\xdd'
 b'$\x80l!\x94\xb5/?\xce\x8c\xd9\x18o?\x9f\xd1\x18\x7f\xbem\xcb\x00\xc9n'
 b'\xb8q\xeeU\x94\xff\xc2\x19\x91k\x17WO\xc2\xde\xfe\xe7_ar7\xfa&\x178\xa4\xcao'
 b'\xa2\xef\x0e\x16?\x94+\xa2e\xc9H? \xd9X\xd5\xa2\r\xf0\xa5\xf7\x1d\xd0\xe8'
 b'"`V\x95:{\xf3\xc0\x98\xe8\xbd\xdb\x13\xca\x997\xdc|\xc6\x01|\xb8\xcf\t'
 b"\x00\x8c\xc4\xa3@\x80+\x80\x0f\xcc'}\xda+\xde \xb1\x17\xdd\x07"
 b'\x85\xe6\x86\x0f\x1a\xda\xb6\x80\x90DYJ\xd3?\x05\x99NZ\x98\x8bg\xeb\xd3\xcc'
 b'\x85\x86&Ds\xc4\x9di\x02\xb8(\x04\xd2\x02\x12\x0b\xe0PL\xd2m:p\xa5b*\xc5S'
 b'\xe9\xa91\xb2\xed\xd9\xfb\xaaU7Pp*\xe7\xab\xdb\xde\xe8\xa7>\xf8\xfe\xa2\x1d'
 b'_\x95\x1dB\xfd\x11\xc1\r\xec\x02\x91\xdf\xa80aM\xc0\xb6&\xc2\x98uK\xe0'
 b"'.\xd9\xc1\x01\xe0wF$\x1c\xcd\xc1\xc8U\x8c\xb1\xac\xc2\xd8\x0e_bb\x18"
 b'\xbc\x0cie\x0e\xd6\x06\x08c\t\xea\xff\xba\xf7t\x86\x03\xa1A\x1eM\x7f\x9c\x08'
 b'\x06\x87w`nP\x81}\x8b\xb3\xb5/\x19x\xe3F\x9f\xb6\x83:"e\xffj\x89\xf9\x8d\x8b'
 b'\x82\xb3\xa3\xcc;\x18\x18\x13J\xa6\xd2\xcc\xd1.A\xbf{\x16=\x86\xd5\xc0WR'
 b'\x91\x8d\x85\x14o_\x9b<;4\xcd\xa8\xdaG\xde\xcf\x95*\xcf\xd9\x9a\xf0\x1e\xf9'
 b'\xc2\x83\x06\xe2\x82HZ\x9aY\xfdBrj\xba\xb5\xa9\x89D\x08\x19\x99\x8e|\xd9'
 b'\x89\x97I\x0c\x16v)\xafD.uzs\xed\xae+\xe8 \xd1\x01\x15\x92is\x13\xacv\x17'
 b'\r\xc91\x95\xb3%\n\x10-\xf8\xa4\xd9LvV\xd6\xb5\x97\x019\xea+\xf5\xb1'
 b'\t\xbd\x94\r\xfc{\xef\x16\xf8\x01|\xba\x0e]\xb0\xc0\xc3-\xa2\t@\x97\xd2='
 b'm\x0b\xf9\xef)\xa9\xc208\xd0\x91\x15o\x8a\xcf\xe6g\xfeV\xf7\x99\xc4\xb4\xec'
 b'\x94f\xae\x8b\x1bc\x8b\xe3\x02NT:\xdbt\xecQ\x86\x8e1\x07\x08\xfat\x19'
 b'\xab\x15E\x80\x874\xec\x94o6(\xe1\xbf^\xbb\x8a\x83\xcc\x83\x94\xbe~\xa7\xd3'
 b'ff\xc2\r\x08@R\x8f\x8dM+\x97\x87r\x15E\x18\x89\xf1/\xbdK1\xec\xa6p\xe7\x8d'
 b'\x89):\x06\xff\x82\xb1\x109\xdf\xdf\x8e\xac\xb4\x91tE\x86\x02\xdc\xe8\xcc"%'
 b'u>z<\xcd\xcd\xb5\xec?\x11>\xdb~3\xe9\xcb\xc8\x0c\xd0u|\x105\x92\x8f\x7f4\xe0'
 b'V7"$ \xb9\x93\xb2\x95E\x18\x02f\x08\x0b\xa04L\xcbez)EZ\x00~\xfd0'
 b"\x8e\xf3\x88pSi&\xf1\x16\x1bs\xc66]\x9d\t\x8c\xfd\xa6{%'\xb90gO\xb5\xaf"
 b'\xf8\x01\xd7`\xd6\x98R\xd7\x1b\xb8\xa4?\xd9K\x85\xef&,\xd9\x89'
 b'\x9f\xfc\xa6\xa1[\x1aRC\xda$\x93\xd6zA\x84\xd6\x9c\x04|\xc3&O\n\x0f'
 b'g\xf6\x8b.\xf5\xf0\x9a\xa2\xb1\xcf\x95\xcer\x03\xf5G\xcf\x9ed\xda'
 b'\xdb\xf4\x13\xb3\x87\xf8\xbfL\xb6vh~\xff\x14\xda\xd4j;\xa28\xe8\x86\xb1\xc0'
 b"\xc7\x7f\xb8A'oo\xf4\xda \xbe\xbc\xff\xba~F\x95\xfd\xc4\xcc\xdf\x93\x1e\xd0"
 b'\xccL\x8a\x87,\xd6\x81\x86\x17D\xa6\x01z\xc4\xc5\x9a\x96\xffc\xad'
 b'\xf9`\x80\xe0\x1e\x1d\x8c\x06$\xf5n!~\xe5\x10\xe3\x89c%4`N\xae\xac\xbfA1\xce'
 b'r\x0e\xfc\x94I\x94\xd4\xb9N\xda,\x01\x1eQ"\x98\xb8U\xa1<\xe0^9G\xa7\x87$*'
 b'\xee\xb8-\xb4\x10\xd5\xf1\x0f\x02\xe4DqHI\xb8\x82\xad\xc3\xa5l\xbf.\xb8\x81'
 b'\x94\xab\xed\xa2\x02\xe8\x83\x8d\x1be#\\\x00*\xac|\x0e\xecC\xbal\xd3?\x05'
 b'\xb5\xc7I\x81hx\x9aO>\x96a-\x9f\x92\xe5\x91\xb6\x00A\xeby\xf7\xc9\xe8'
 b'\x0c\xd7h\x19)P\x06\xf1\xc1\xac#:v\xfe\xc3\xfd\x18\xdd+V\xd2\xb4\xd4\xee'
 b'\xd3&1\xbf7E\xfc~[t\xfb]\xc6|a1\xdb\xc9\xafB_k\xf0\x19\x0eBX\x02'
 b'\x1cG\xd3\xf0\xa4\xb1\xd5#\xec\xd5\xa1`\xe93\xacs\x8f\xdc"8\x86\x13K\xb2'
 b'\xfc\xf2g\xfcBB\xe8D\xf3\xb4\x13K\x8a\xa1\x82>%\xf5\x17\xe9C\x84\xcb\xbd'
 b'~\x19\xf4\x1e\xb74\xb6\xe2\xb2\xe3A\xaeP &\xd4\xa7\x1b\xe9\xe5k\xca\x90#'
 b"\xcd\r\x1e\xaabDd\xf2\x036\xed\x95\x08'\x99\x81X\xe0\xc4\xd6bF\x07K"
 b'\xb5.h\xf3\x9f>\x93\xee\xcf%\xaaW>\xf6\xb9\xc0\x86\xc7v8\xc3E\xde\xd1)a3h'
 b'\xc4J\xda\xeeSg\xa9\xa8\x07\xc7\x91\x00\xb9\xef\xa9t\x80d\xa0\x98'
 b'\xc4\xed\xc9\xc5\xc1h~ Q\xaa\xb8\x07H\x8cJl\x9c\x965\xc2\xd4\x80\xb8['
 b"\x0b\x17\xec`i\x8e  kd\x06\x00#\xa3\xb1\x122\x1e\x90'cay\xe9\xaa\xfd0\x90"
 b'\xeaFF\xa6\xd2\xc4g\x01\x1f*\x8e2\x05\n\x10<\xadl\xa6+\xd0\xcc\x12\xcf'
 b'\xcc\x8d04\n\xf6C\x0e\xb3}&\n\xf1e\x01\x89\x02l\xfd\xa5\x82\xcd\x08\x19'
 b'>i\xd0\x88\xed\xca\xaf\x911\xd3X\xeb \r\xce\x93\x1f\x90\xe7\x1e\x8d\xad0\xf1'
 b"\x94\xdc\x00i\x89\xe6{\xc2i\xc2\xf1'\x16\x95\x0b,Q\x14L\xd6\xed\n\xc5\x9d"
 b"[E\x84\xcb\x16\xea\x17\x05\nh\x897Nc\xbcp[\xf3B\x81\x02Y\x19\xcf\x9c\x01H'"
 b'N]*\xc5$?RY\xc7Q^\x0f\xfc\x8e\xba\x06H\x9d\xad\x97\xe5N\xbd\xb6|^%\xe7'
 b'\xa0\x99UX\xeb\t\xaf\x8eGK\xe8\x1e!-\x0c\xf3\x92+\xf2\x14\xfe\x06\x1d2'
 b'\x08A\x18\xb9\xa0\xedd\x83\x14\xd4\xd7B\xe0\xb3\x14\xf2\xc1\x81\xd5\xc0'
 b'\x80\x02v-\xc0U\xb8\x94\x07d\x17@8\xe3\x9b|\x00\xf3w\xd9\x81\xfc\xce\x8d'
 b'6\x06P\xe7\xce%\xf97\x8e8\x18\xa2\xbf\xbf\x7f\x8e\xeb_Kwh\x98\xf0\xd7'
 b'\xaeY\xf1J\x94b\xa0q|D\x9b\x918hPi\xff;\\\xfa\xe7\xf0\xfc\x8b'
 b'\xe2\x08\xf9\xab\x0b\xd6"4\x93gq\xe7\x1eh\xbd\xfda1\x81Qk\xaaL\r'
 b'\xb6M\xae\x10\xe9\xe5S\x06\xf8\x83\xb2\x9a\x88\x98)]z\x96\xc8\x98'
 b'U\xe8\x18\xf9\xe3h@0.`\x10K\xe4\xd1\nB\xe5<\x8e\xa4BWS\xf0\x87\x1b\x96/'
 b'\xba\xf3\x83\x7fm*\r=\x01-\x1f\xf4q\xb2\xbc\x05\xc5\x8b<\x15\xbd\x97\x94\x16'
 b"\x15x\xb8d7c\xdc`\xb6Q\xa0\x94\xc7\x81(\xb7'%T\x00\xe6\xc3\xaf\xce,,5\x1a"
 b'\xee\xa5\xa4\x8aZK]\xb6\x9fT\xcf\xd0X\xd2q\xd3\xd5\x17*\x97|\xe3\x9fpXx[D'
 b'Zb%@ \x84w\xf1\x1a\x9a\x01m\xe1(\xaa}\x11T\xb7P\x0fGkT(\x9b\x7f\x96'
 b'\x12%\xa8\xeaD\xcao\x05s\x9c\xf9\xb2I\x8c\x9e\x84\x95&r|\x7fV\x03\x06'
 b'\xb1!\xc9\xb3{\xaf\x14f\x07\xe0\x83\xa3\x93\x8c;\xf2\x91\xb1c\xe9\xed0\x01i'
 b'|\xc7\xee/\r\x1e\x0e\xf8+$\xa4\xeac)\xc7\xac\xa2O\xb1\xf9\xee>\xd9\xff'
 b'V\x92\x87\x0c\xd16;"Hj\xacF:\xf0\x7f\xf9q\xa6Bsx#\'\x03\x17\x98\x9c\x06'
 b'\x16\xe1\xac9N\xec\xa8\r\xfe\xac\xc4\xadR\xa8\xe2/J\xc6Z\x0f\xd8Z\x9d\xac'
 b'\x03ou\xa5\xb6\n_7D\xe4[<\xef\x10\x13\xef\xe4\x98^\xbe\xdc\xdc\x1f`'
 b'S\x16\x82\xe9\xa1\xc8>\x1d\xaf\xcb\x07\xf6e\x8f~?\x00\x17\xd6g\x0f\x11Ww'
 b'\xc7\x8c\xc1\x00\xb9\x15\xb8\xec\x8e\x03\xa4G\x08C\x1dl\xd5\x9e=\xdd'
 b'C\xc3\xd4\xb5\xcb\x80\xf2\xc0\xd7]uIdV,\xe7\xc6\x1aT\xbc\x839\xed\x9f\x9cRQs'
 b"+2\xa3%@,\r/KR\xfe\xbb\x8b\xb39'\xd3\xd2\xea\x02\x81!\xe3L\r8\xa1\x84"
 b'+\xca\xbc\xef\t.\xd3r\xcd\xae\xfe-\x10c\x9b\xc2hH\xa4\x8d @\xdez\xeetv\xd0'
 b'\xdd\xd3V\xcfq\xb3-f\xd7\x0fO\xb8\x8f;\x07\x8fn\xb6\x1aD\x96\xe8\x08]'
 b'\x9f\x93^\xa3\ts\x06\xee\x01A\xb6#y\xf3\xff\xe7x\x83\xb2r\xb7W>6\r\xd8\xe6S'
 b'\x1a!_\r!\x8cN\x8d\x84\xa2\r\x8de\x93\xd1\x1c\xd5\xa4U\xf4Pz\x04\x92'
 b'\x08J\x11\x95\\\x9b$\x92\x10\xe5\x14"J\x9e\xb8\x01i\xefSd\xa1!\x9c\x90'
 b'\x89\x9613N\xa0>\t\x93\x1c\xe5\x83\xa7\xef]\xbeZ\x91C\x0b\xf7 k\xe3'
 b'\x1c\xa0\xbb\xc3k\xbb\x15\xa7\xff\xe1\xbc\xed\x0e[\x0e3\xc1M\x82\x02'
 b'\xc8G\xc5v\xa6_>K\xf4=\xed\xb5\xfb\xfb\x1f\x06<>\x16j\x0bF\xf0$\x15\x02\x94R'
 b'\xc3;\xc6\t\x1e\x17\x14\xc3\xe7bq\xfcH\x85\xcf\x7f\xcb\x04\x07J64ot'
 b'\xf9\x8c\xae\xae\xd8B\x12=DI\xb1)\x94\xc3\x8eWN\x87x\xfa\x88\xee\x9c\x94'
 b"-\xb0\x8f5`\x12[\x11\xf1\xf7\xbe\xeeWh\x91\xbcC\xef\xe9\x0e\xce\x0e'\xa0"
 b"\xac\xf5\xa4M\xbc\xc0\x90\xdf\xac\x81\xf8\xcd<\x90\xaf'r1\x7f(j\xb1\xf0\x03"
 b'\x97C\xf6T,sM\xab\x96\xfbg\xd1\x16\x89\x00J\xc054\xabu\x0b\x80r \xf3\xa2\x8b'
 b'\x1d\xfeI\xd5\x8c\x11\xa2\xc5\x9fN\x07\xb4g\x01\n\x0e\x01\x11=\x18'
 b'\xd1$\x80\xd6\xb0|dMs\x9d\x13@\xff\x9b\x1c\xacN-_z04\xa9\x160\xc4yE'
 b'\x94\xe0\n\xa2_\x07\x0e(o\x08\xb6)\xcaHn\x848+\x04\xc8\x84JF8B\xd5\xf6\xd0'
 b'\x91\xb8\xf3\xb1b\xdc\xf6k\xff\xc4\xa8F\x95\xc1\xbd2\xaai\x07\xbd'
 b'\xd6\xb3\xc0W\xa5 \x1f\xcdrv\x02TL\xbcP\xe9\xb5zn\x86\x8a1oM\xb2\x01\xbe\x05'
 b'y`*2\xc5\x11\xf5\xdc\x7f\xd0\xa0\xf37S\xc8\x8d\x17AA\xfb\xe3\x8f\xee\xb0'
 b'\x9c\x1f\x90\xd6\xba\xc2F\xf4\x0f\x81\xe9@\xb6\xef\xd70\x85\x8b\x153'
 b"\n\xbd\xf3}X\x90\x1dm4\xa9-\xa0\x7f\xc8\x05\x94\x98\xe3\x04\x0e\x1c\x8c'\xc9"
 b"\x14\xbb|\xa4?v?T\x14'\xebH\xf1\xec\xde\x82\xd5\x88\xf9\xf9\xa7\\9\xff"
 b'~\xc7Bi\x90\xdb*\xd8\xe3\x9f?oPDQ\x89\xcdq\x0c\xf2"\xb3\xef\x81\x82\x9b\x81('
 b'\x92\x05M\xe7\x93\xfe\xda#\xad\x01f\xd5\x92\x86\xd7;G\x015\xa5\xda1\r\xe7'
 b'\xa4\x89~$;/\xea{>A\xa1\xd4\xe0<K\\h!n ^\xfb\xc1\x19\xe9\xbc:h]\x7f\xa6&'
 b'8\x9d]\x88\xdb\xb9\x93+w\xc2\xdag\xe7\xec\xdf\x8e\x05P\xa3\x9eP\x8eE\xd4'
 b'r\xd0Q=\xd9O\x19\xde\xa1\xa7\xcd\xc1M\xb2}\xb5\xf1v\xdd\xadk\xe9\xe3\x07'
 b'|\xde\x82\x83Q\xd6\x13\x1a\x12\x88\xd4\r\x1e\xd5\x1e\x86\x9e&H4D\xb53/'
 b'\x95\xae\x84\x7f\xc4h\x06\xe6W\xea\xff]P\xa9\xaf\x90\x9b\xe6\x8c\x88'
 b'\x12CV\xac\x01\x98%\xfc\xff\xe2@\x19\xb9j\xa1\xd6\xdc-a4\xaa\xa4D\xb2'
 b'\x86\x9a\xd1D\xa0\xcb\xf2\xf6X\xe9\x80\xd3\xc9\x8b\x1c)h\xe6f\xfeBbhA'
 b'\xed\xb0!\x89\xbe\xbd|L\x8a|\xc1\x13\xac\x8e\xa4\xf5l\xd1B\x0e~\xca\x07\xe6'
 b'~iZ\xc4%\x83F\x0b\xcd,|\x03r\xd0I\xce\x05\x94\x04\xac}\x80\xa7\x0b&\x10J\xd3'
 b'BG\xcf\xdbF\xc0\xae\xf2`\x11<\xa7\x9f\x0b\xd3\xcc\x7fc\x96\xa8\xc6xz\xc4'
 b' \xc0T\xf7\nm\x08\xf4\xb3e\x9d\x83_K\x1e\xb1\xa0Ea4\x06\xd4a9\xcfg\x19\xc6'
 b'\xdag\x91\x11%\xdb\x80\xe3\x0e\x03-\xe0\x1b\x1a\xe8\xd3\xa4,VN\x83\xe0{8'
 b'q\x16o\x01\xef7\x7f\xf7Z\xc9\x0e\x9b\xee\xe4\x13\x85][j\xef\x1c\xa5S\x82'
 b'\x06\x19=U\xe0\r&\x04\x96\xe7+g\xff\xfe\x92\xae\xdc\xc7\x1ae\xa2\xca\x89\xfb'
 b'\x1c:\xa2G[\xe8/\t\r\x00\xa3\xa3}\x0c\xe9|\xda\xd4Ki\x81\x9c\x8c\xb6'
 b'v\x9a\xf0\x028~\xacgt\x99\x0e:\xe6\xf3\xe2\xdd\xf09\xd4m\n\xa1\xfd\xa3'
 b'\xc8\xdb\xd1\\\x8d\xaf\xbc\xceJ\xd2\x13\x0e\x83g\x900\x12\x02\x81\x05'
 b'o\xcd\xf1\xf3s>\xcba\x89\xfa\xb1\x99\x8c#\xf3\x90)\xd2\xb8\x03\xceN\x8e\xb1'
 b'Mo-\x16fM>?d=\x06\xa4\xf1\x94\xb1T\xf5\x89!S\x17\xbc\xa2o \xd448c\xc5\x0fc'
 b'\xae\x18\xad\xd2\xd2\xe1\xe1o\x03\xcd)\xa4\xfaP\xf0\x8f$p\xc3\x90'
 b'\xc3S\xf7\xb0\xd7Z\x8aL\xfd\xe9=\xbb>\x08\xd1\x8cy\xc5h\x0b\x1e\x83\xf5\xc5'
 b'\xba\x96EI\xf0;\x1f\x93\xdf\x94f\x16\x8d\xe06Ru\xf0C\x98\x8d\xc38\xc5'
 b'\xc4\xc3b\xfc\x06\xa2\x07\x98\xce\xcd\x0b\xea\x9b,\x10\t7\xf6x\x03"1\xdd\x0e'
 b'\xbf\xd4&W\xd2\x13\xb95f$\x1e\xa2\xcc4\x9e\xe8\xce@\xe5\xba\\\xac\xcf\xff'
 b'\x18\xbd\xc8\xc1\x7f\x88\x8dQ\xe5\x1e\xe8\xb9$>\xc9}Z\xc2{\xb8\xe7\\>\xef'
 b'\xd4\x18>\xd1<\xbe\x049\xae\xdck\xdd\xd2v\x9e9T\xe7\x9f\x06\xab\xa4\xed4'
 b"-\xa2>\xbc\xd2\xb2g'5\x14W\\\x07\xbb\x98\xbb\x9e\xfd\x9fl(C\xb6[\xba&'\xaa"
 b'[\xfa\xb2\x1a\x82\t\x16\\\xf8\xf1+\xbf\xa0\x8f@x\x07\x9d\x05\xdc'
 b'\xaf\x05\x9e\x1c\r7r\xbc\x00$9;\xc0@\x98\xf0\x1d\x03\xf8\x98\xf3<\xac!'
 b'\x17\xfe!o\xfb\xe1\x1e e{\x19\x16\xbe\xcc\x18\x15\xb2\xdb\x1a\x80\x8d\x8eg\\'
 b"\x0c\xb8\x12\xbf\xe0/\xecNU\x16\x88['\x18\x05R\xec,\x13d(\xfd\xd2\x08"
 b'\xb8\xa7\xc3\xc2\xa1\xc1K,TZ\xdb\x83\xdb"\x84\xb9\xcb\xce\xb0YP\x1c\xc7\xee'
 b'h\xef#\xd3\xb2\xe9\xba\x10\xa1z\x8d+\xb3w"\xf9\xb9\xc8\xc6\x1b\x83\xb7\xe0h'
 b'\xde\\\xf8q\x01u\x1d\x18\xb3YN\x8dG\xc9\x11"\x1e\x10<\xb27\xf9\xb23'
 b'\x10$\xef|\x98v\xb1\xe5\xa2b\xf0\x88\x1f\xa6\xc7\xe5=a7S.\x91\xb9|(\xdfn\xd2'
 b'K\xcd>\xee`\xee*\xeb\x99\xa0\x1c\x10>0\x0bm-\x06\x87P;\x85\xfa\xdc\xb2d\xa7P'
 b'E\x83\x11\xfd\x80\xa8\x07Q}\xb4\xbf]\xb8f\x8e<\x96\xb1\xb9:{\xdb\x8e\xc8'
 b'`\x81\x81\x9b\x1c\x94x\xac;-\x8e\xa3\xc3I\x11\x82\x0b\x89\x08\xc2'
 b'\x13$\xd1\xdd\xa07\xa4V\x11(9\x0b{\xbb\xe4G}\x13\x15\xd9M^S\x8cC$i\xbd'
 b"\xa6\xc4\xe2\xea\xd8%8T\xae>\xc9\xbe\xb9i!\xa3?t,\xee\xa2\x1c\x88\xacO'rf"
 b'\x8a\x9c\xf6P\xd0\x1fp\x00#\xf4\xe7\x8c\xc20LN\xc9\x83LM\xd9\xcc\xe6\x00'
 b'\xbc\x01\xa3\r\x1a\xc0\x92\x90b\xd6\xd3\xc8\x96q\x881\x00\x82\x9a\xbf'
 b'\xac\xfb1\x08\xc6\x9e\xd4Rx\x1e\xae\xb9\xa4\xb2\xd5+\x7fZ*\xbcW\xb1\xbf\x85'
 b'w\x1b\x01\xfb\xca{\nA\x1e\xe9\x95\xb98\xd2\xa4\x1fW\x8aDD\x9c\xc4-\xf0'
 b'\x1c\x11.\xd9\xbb*\xec^\xe2H>\x8c9`\xf0\xe8zv%\x18M\xf8&\x9eCX\n\xdc'
 b'\n\xb2\xf7vP\xae-\xf6f\x92s\x1c\x01\xc4\xc4#\xd6-\xeaf\xf1\x01\xb4\xb5'
 b'<\x94\xea=`E\xd7\xd1\xf2\x07X\xd9\x92\x10\xc3O\x08\xbb\xa5T\xa5GL\xb5'
 b'\xb8\xdf\x1d\x90\x81\xb8j\xc2\xac\x9a\xc7\xf6\\\x8c\x99\xdc\x8e\\\xac\xcb'
 b'\xe0\xdc\xe9\x1d\xc5\x96\xd5\xd2a\xe5\x943\xb5;\xa5\x92\xf5*\xfd!\xe1U`p'
 b'\xc7\x1f\xb4rL\x94\xd7\x0c\xa02\x88WZ\xa6\xb3\x1d^\xda/`\x1f\x7f\xf7Z'
 b'\x07 \xe4\xec\x0f=\xf6\xd9\xe6Y\x98\x07\xdd]\xea\xe3\x98\xaerh\x84\xdd\xc0a'
 b'\x9a\xfdU\xfd\xe3\xda\xd0\x08\xc2I\x12\x9eC\xbe\ralE\xcf\xbd\xa5-\xe3\xc4'
 b"\xe3K'N4\xb02\xaa\x90E\x83}FS\xfe\xef\xa08\xacS\xf4\x11g\x13q\xfe\x0c\xbd"
 b'\xc0\xf7\xab\xd5\xab\x1a\xe8\xb8N\xf0\xa3\xaffmLrp3\x1f\xbf\x05>\x93\xb4'
 b'\x0e\x81\xdd`O\x12}\xe0 K\x97O\xb1\x90\x06\xec\xeb\xd3\xab\x058\xa4`\x1d'
 b'\x19\x1ejt\x0e\xef\xdf\xd5\x13\xa0\x99S\xea\xf2^\xa3\xd8\xdb\x0f\x9c'
 b"\x8eM\xc9\xd1\xf9]\xea8\xd4\xf21f'\xe8\x90\xa8\x90*\xd5\xa8d\x14\xe4\xac"
 b'\xdd\x056\xebh\xeb\xbe3\xec\x81\x90,\x0cG\xdd\x19\xe3\xb9\xd4\x7f\x9a9\t\x86'
 b'L\xe0"\x89J\xdb\xb0\xa7\xac\xc5{\xceG4\xba\x9a\xbd\xa0\x07\xd5Q\xbb\x84\xa1'
 b'\x11s@\xfdo\xf8\x8eqP\xa4B\xae\xb6\xa0iB\x1c\xc4\x82\xb9\xac\xa7V7'
 b'\xfb\x92\xdc\xc0+\x19\x04\x10\xf9\x0e\x954!\xfd\x0b*\xe7\x04\xc7\xed'
 b'\xf9>\xdf\x8d{\r\xbce&\x17.\xd9W\x8f{*\xca\xa0\xf1\x13^\xaf\x9b\xd6'
 b'\x85\xe1\xc0|\n\x1ch\x1dT\x93J\xf6\xb8]e\x92E_(Y\xd8\t\xccBL\xa4\xd6\xa1'
 b'\xd67\xcfY,\xb9K\xe1!\xf0\xb5\r\x0cf#g\x12\xf9\x1d\x84\xac}\xa7\n'
 b'\x18\xa6C\xb4\x01/d/\xf1pH\xb8$\x81z\x18d\x98]\x9e\xf2I\xa1\x0e'
 b'\xb3\x10\xc5\xc2\n\xc0\xc5\xac\xc0\x01\xc11\xfe\x1cX\xd9\x87IP\xb8'
 b'\xbf\xe3]\x0c\xcb\xb0\x85cYs\x82I|\x99X$\x91w\xc4\xf2\xbe\xad0>M\xb7\x95\xec'
 b'\xf7\xb9\x03bV\x10n\x00\x8d\xbd\x0e\xb6wI>\xb7\xf6\xf6\xf6\x92\xd3\x80\xc8?'
 b'\xa8\x93\xfe\xe1\x07{\xb8\xd3\xa7\xd1\xbcY\x9e\xca\x87\x83p\xac\xfa\xa7'
 b'\x8b\x08\xb3\x0f\xe0\xb0np\xb9\x87Fm\xfae\xf2\xb7\x84\x14\xde-B\x03\xe2\xd8'
 b'\xc5M\xc4,\xee\x82e\x8b\xbe\x81\x99m\\v]\xb4\x16Oc\xe8\xda\xaa^\xf2'
 b'\x15\xed\x0b\xee\x7f;?X\x82\xa9\x82\xedXr\xe6T\x9a\xb1\xc1\xb5\x82@\x80\x96'
 b'\x18\xa0,\xe8t\xd6d\x9f\xcb\xb1:\xcd_\x07v\x8d3\xa7\xc8\xffL_\x850~\x0c?\x14'
 b'\x17\xb2\xb1\x81\xad\xa7~:tZ\xd4?M\x00\x90_\x00bF0^\xa4$oP\x93\x1e\x1e'
 b'U\xde\x12\x1c\x14\x0b\xc8Yf-4\xe3;OU\x17\xb6\x85q4@\x8dF\x9c\x80 >\x12'
 b'\xbe\x1f\xae\x8e>\xb8_\x81\x9c|\x9a\xe9x\xd4bDcqE\x9e\xc8a\x81&D\x81\xff\x1e'
 b'\xf8%R\x94Z\xb9i\x86\xb5g\x8fA\x02!\x93-/s3x+\xb4s\xbdpB\xf2I\xad\xa6:\xce'
 b'+\xe0\xcc\xc3N\xf3\xe5J\x07\xf9U\xb3e\xd9\x0f(&\xc1\xb0\xaf\x01\xd3y\xfd'
 b'\x83k\x05\xcb\xa1\n\x85\x1e\xb1\x12\xe5C\nI\x04\xd7L\xc3?\xf3G\xc7\xf0t'
 b'_\x17\xa6>\xe2t*L\\,\x10\xa4\x98\xed\xfa>\np?dU\xf8\x86\xe5B~F\xf7>\x84\x85}'
 b'_w\xd1\xec\xc8\xfd\x0b\xd0\xa2r\x1d\xfe\xef\xec\xe0\xf9:7[j\r*/}\xb1s%G'
 b'\x1c\x1cX%C\xf4B\xbc\xd0\xad\xdb\xc0\x845\x02\x19\xf0\x989\x97'
 b'\xa2\x03\xc6\x96 (\x02I\x94\xb617\xec.z\xa5\xd4%\\\x82?\x86f '
 b'\xd5\x97\x15\xb9o\xba\xdc\xdd/\x08P\xcc\xd1\x1a\xe8|\xd1\x18,)\x8d\x8bE\xb5'
 b'\x051)\x0c\x03N\x99\xb3\xbe\xa3\x98\x88{\x95\\9\x84\xc5Q!\x0fj$@'
 b'S\x8a\xbb\xcc\xe3\n\x94\x82\x9e\x9dj\xfdZi\xea?\x0ep\x1f\t\x95\x16>\r'
 b'\xc9\x17#\x8f\xad\x06f\xfdM\xa4F\xb2\xf26\x9au\xc3T1\xa5\x8e\xab$\xde'
 b'\x8f\x00VzE\x80\xf9\xbe\xfc"\xe9m\xc3\x98\x91\xef:\xcfa\xc7B\xd3-\x97'
 b'\x00\x00\xa4V\x90\x97L!\xf7\xbf\x19\xa5HL\x07\xdc\x8f]\xf4(\x03\xcbY)'
 b'\xa9\x9e\xd8\x04dU\xb2\xf1\xbf7$b\x06Jg\x08\xa4\x85\xc3\x18i\xac\xb5\x90'
 b'\xd6}\x02\xc0\xd9\xed\x86\x00\x01\xa7\xfa\xc4\x0f\xa79S\xa4\xc1X\xf5'
 b'\xbc\xc1K\xfbk\x81\x8a\x7fcM0\xd0\xf5\xb0\x7f\xd0\x8d\x17o:rX\x96F'
 b'\x0c\xdc\xed:P\xa2h\xa7\xe9!b\xdcY\xf4\\\xe63B4p3\x1e\xac\xdc\xc0\xf4X\x9c'
 b'h.\xc0J\xd4\xc7\xde\xd5\x12\xd6<d\xc6\xf1+R\x08|\xc8\xa9-\x89\xf1\x94w\xa8,X'
 b'\x85\x11\x17f\xa2~\xcc\x02\xee\x8ct\\U\xb4\x8e.\xb7\x82I\x87;\xa0\x1c\x0c'
 b'\x7f\xd6\xfd\xaf\xc5&S\x90\x8c\x15\x19\xc0\x1e\xfd\xfcN\xe4\x1c\x08\x14'
 b'\xeb\x1c\x919\xe7\xf4\x82\x12\xbe\xee~\xa8eO\xae\x9a\xf6\xc3\x0c9'
 b"\xd9\xb1\x8c\x0f\xd0\xc5\xd9\xa9'\x9e\xa5\x05\xd0\x0b|\x9d\x00\xd2|9"
 b'Y\xe9y\x8cG\x1f\xc4\xc3rL\x1aJ\xe1\xb2;t\xf8q\xde%Es\xa6\x03E\xc9\xf5)'
 b'>\x0fi\xca\xeb=\x9e\x043\xe5\xa2\t\x1aK\xaf\x87f\xbf:\x8fK\xcb%\xf7'
 b'\xb8_\xf4\xf7\x18\x17p~\xfbi\x7f{\x04\xbfX\xdfc\xa4@3\x8c\xf3\x8d\x82'
 b'\xb7C\t;\x1c\xfd\x04\xb6\xf9)Xl\x0ch\xa3\xbbM\x03;\xfc0@\x98\x9c'
 b'\xdb\x84\x82QF\xf9\t\x0cO@\x82\xc4\\\xc5\x176\x88\xa4\x85\xbbv\xda\x83\xd1'
 b'\xb8)\xd3\x9fa4Z\xb6?$\xff7\xd4s\x05\xb0\xb91\x88%\x1e\xcf\xc0M\x11\xf3h1'
 b'\x9f^`Q\xfd,K\xcb\t=\xf9P\xa8\x98\xc5\xb6\x05\x85\x88\rT\x033E\x8a\xa0\t\x1c'
 b'\xd6\xa3\x9by\x8d\x89WG#.\x9b\xb5\x1ate\xbf0\xe2\xc4l\x13PY\xefn\xa9\xed\x00'
 b'TU\x80\xd8;\xb6\t\x04>h\xe6f\r\xce,B\xcc\xdf\xa0%\x98t\xd7ip\xc2c-'
 b'\xa1\x0c\xde\xd7\xfdQ\x8e\xfcX\xf6\xd2\xfa\xf8\xd4j\xb4\xfd\xed\xa7\xea'
 b'D\x89\xb5\x03\xc1 rE\xa9\xd5\xf6\xb5y_\x0c\xa0\xc63\xcc\xdb7\x8d\xc9\xe6'
 b'(\xc6\x17Y\xf7]\xb9\x03e\xed\xca\xf7\xac\x15\xd3\x05\xb0\xc4="\xf2Xq\xde'
 b'\n }\x86v7Z\xf9,j\x9d)x\xc0\x14\x0e\x82Ky\xd2\xcbXi\xe5J\t\x06\xba'
 b'\xe8\x82\x13\xd1L"\xaaP\xea\x17\xd4\xca-\x9f\xd1\xdbdIY\xf5\xe3]\xec\x83'
 b"\x7f\xc9\x80H\x92\x9b\x1c'\xc9j=t<\xe3\xd62\x1c1V\xc2M\xe8(\x90\x9b\x0c\xfd1"
 b'\xcf\x01\xdd>\xd6Yi\xae\x96G\xfc\x16\xbb\xe0\xc2\x810\xc1eH\x8c\xfa\x9b!'
 b'j\x12\xc9\xa8\x11\x83\x01\x9f0\x8d9Gl\xa4\x14\xf1\x7f\x98\xae\xb9'
 b"\xd5\x15\xd3\x96p=\x88rlk=\xbek\x95B\x01vo:p\x18c\x1c@b\xb3|k^'\xd4s9(_\x93"
 b'\x82cf\xcb\xd0\x8c\xd5u\xa3\x03!\xdf\x90\x0f\t.\xc81\xafQp\xdb\xca\xd6'
 b'\xdc\xa3M\xd15>\xce\x0e{\xfc\x89\x8dr\x02H\xd8\xf0\xba\xae0j>\xef\xe3'
 b'\xb5D\x88\x97\xfe\x8a\x0c\xa13\x84\xd3\xef\xa8r\x039R\x13p\xd7'
 b'\xd1\x8d\x0b\x98\xa5=XF0\x08I Q\x8b\x933\xa4\xd3;s\xc0k+vl\xdc\x99Y-Mbm'
 b'\x13\xb3\xcc\xf6\xc9\xf0\x1b\xb7\x81{G\xc0d\xac\x83R}\x18\xb2`\xbc;\t7'
 b'\xb5\x8b\x7f\x96\xe3\x81V\x07J\xe9\xba:>\x06B\xc2W\xd0K\xc1\xff\x8c\x85@'
 b'\x983^_\xbej\xb4\x14\xe4\x94\x06\xee\x1e\xef\xda\x83\xcf6O\x03'
 b'\xed\x03\x1e\xa0\x98/C\x83\x16L\x83\xc1\x1f-\r!\x08N\xe1\xaba=4FG\xd8)\xd6'
 b'\x00\x0e\x15V].\x86mD\x98\xeb(\x15i\x01\xd4\xe4"\x0e\x9c\x83\xe6\x90\xbf'
 b'\x06\xa5\x1fC\x01\x16\x1c\x02\xb2\xe3%\xab\xe8\xaaA\xc6\xbb\x00\xc1\xda'
 b'\xdd\xfbL\xb8\xc8I\xc4\xe5\xeb\xda=\xccu\xa0\\\xdf\x00\xdcV\x8e\xab\xb4\x06B'
 b'\xb3\xbfp\x0e\xea,\xe9(\xa3\xc3q2\xd3\xac8\x17\x87\x05\x95\x1d|#d5\xcb\x19-`'
 b'U\xf4\xbd\xf3\t\x00G\xa6\x91\xd5F\xb8\xf1\x8a\xdb{C\x83\xe1\x1d\xb0\xcc\xce0'
 b"\x1d+\x06t\xcd\xf6\xb1'\xaf\x84\x1f\x8e<\x93\x12\xc9\xce*\x0bJ\xa8\xff\x0b["
 b'\xe5\xff\x03\x13\n\xeb\x89n\xfe\xb4\xa5\x13\x96\xe8G0\xcf\x0bj\x07'
 b'\x8c\xe1\x8a\xadc\xb0\x1f\x16E(\xb8.\xb4\xca/9w\xc9\xa6x\x04\x9d%m'
 b"w\xa6\x92\xd2p\xb4d4\xc4'\xe1\x02\xa2\x12\xe5\xa0^\xcb7t\xa1\x84\xd9@\xc5|:c"
 b'\x86\xfbh\x13\x91\xdd_\xab2\xabPE-_.x.\x11o\t\xd6\xbd\x05\xe0\x93\xf8\x92V'
 b'\xea@\x80 7\x0f\xb1\xf5f\xbb\xc9\xa6\x0f\xec\x80uzc\xd2I\x00\xe8"v'
 b'\x15v\x0e\xe9\x0e"\x93\xf2D\x01\xaeZ\x14o-\x00Q=\xde\x03@\xba\xaa\x9f'
 b'\x0f\x07\x92\xae9\x15k{\x06\xf0\xb5x\x08\xe2&\x8b8\xcfdpm\xd1T\xe1'
 b'\x8e"\x16\xaa\x8a\x1a\xe1\x12\'\xbd\xdb\xd4\xb3\x84PE\xf5\xa9(\x87'
 b'\x02F\x11\x93\xa5qM\n\xdcd\xf7u\xfa\xb7_\x06\xf5\x9aB\xac\x10\x0e\x1b]'
 b'\x18(\x9eg9\r\xba$}\xba2\x01\xc5V\xb6\x9d\x137\xf0Tc\x90^r\x96F\x1d\x80'
 b'@M\x10\xc5@\xdd,\xb3m\xc2\xc9\xc4h\x8b\xd4k\x1dF\xc2\x92\xb0;\xeb\x82'
 b'\x9b\xcf6\xf3\x02a\xdf8\x87v\xc4\x11DMb\x05I0\xc2H\xc0\xaa\x9b\xd9#q\x07='
 b'.\xd8\xcfuu\x7f\n`\xa18\xacHY0\xeeC\x0c\x96\x19\x06\xff8\xac\x97}\xd3v\xb0'
 b'\xb5\xf6e\x0eA\xd9\xd6?\xb2\xac\xe2#\x8b8\xbbD\xcch3\x9a\x13\xbag\xce'
 b'\xc1\xfco\x06\nx\x1cK92\xc6P\x15\x13\x0b*\x13\xd3\x8di|\xaf\xcd\xca'
 b'\x80\xe4\x93\xf1hi[y07\xc7\x10/N\xe0\xc9\x7f\xf5\xef\x7f\xe0+\xce>'
 b'\xb6\xb3\xd7\xe2\x866\x98\xb0t\xf1\x16\x06\x02\x9e\x9c\xd8\xb8V4y'
 b'\xe4\x1eI\xc4X\xd7\xed6\x19\xf4`\x16g\x194\xa6\xd7\xa5\x96.mA\t\xfe'
 b'\x9ao\x83\xb6\xfd\xe3Z=p*\x8a\xae|\x00L\xad\x15\x1a\xc4\xbb\x90DRM'
 b'\x81\n\xc2\xa8a\x0b\t}\x83\xeeRC\x9bR\xb6\x80\x95\x1f\xe4\x022\xe6\x94x'
 b'\xbc\xb7Aa(\x12\x0c\xbf\xc0X\xa8\x1d\xeb\x81D\x07U\xf1L\thID\xe1\x10\n\xc7L'
 b'gAO\xf1G\x1fje\xdd\xde\xbe\xc4\x13\xf1<\xe4""!i|\xaa\xf6\x0fn\xf4\xaf\x8b'
 b'\xf0\xaaM\xc2\xfd\xa4eSh\x0f)&\xe3S\xbe&\x05,\xa3\xe37\x04\x84\xa2'
 b'\xba\xf1\x87\xcc\xea\x81\x83\xf1\xdb\xfc\xc2|\\[n\xa2\x9fG\xd1\xc5'
 b'\x87\xf49\x17q\x11\xa1\x8b}\x0f\xd3\x0c\x98E\xbc_\x81g\td\xf3t\xcc\x00'
 b'\x00\xc6\x98VuQ\x8bP\xdbvK\xe8(\x14\xbf\xb4\xbe\xf2AU\xe2&I\xe2\x94\xac?]'
 b'Q\xa3C\xc5{\xb6y\x80g\xbb\x1f\xe5`\xf9<\xf9\xd1\x89\xc5N\xd4>\xef\xc6'
 b"\xcf\xfb&\xe9\x83Z@\x11n\x9e\xear\x84??\x87\x16\xe6L\x93h'\xc6\xc7"
 b'\xb2\xdd\r\xe4\x18[\\\xe2\x01\xea\xcc\x86\xdb\x079p|v\x11\xee\x02\xc3?\xb2'
 b'\x03gql\x84\xffG*\xf7Eg|2\xf92\\Z\xaf\x05\xfb\xf5!\xe9K\xbf\x1cf\xf2_dv\x19'
 b'\xd3<\xd9\x81Z\xeap9\x8anvF\xd0\x04\xdaQ\xf9\x14|u\xb9#V\xeb"f\xc5\x97'
 b'\xda\x90\x7f?\xec\xdb\x1f\x13\x00\xbf\x03\xe2x8\x93\x08K\xc3l\x86'
 b"'\xff\xd6\x11\xdd\xc7\x87\x94#\xca\xa4\xe9\x12t\xe3\x1a)\xba\xbf\x0e"
 b'\x87\xf3\x1c\xee\xa9\x99\x84gD\xdbR$\x978\x92]\xce-\x8d\xec\x8f\x9c\xc0?'
 b'\x07\xfc\x9f(\xdd\xdfTrA\xd3\x96\xa6\xf9F\x1b\xe7Lg\xe1zzB\xc1I\xf1@[\xf7'
 b'\xf2\x13\xeb\x919\xc4.\x98\xebV\x02\xc8O\x0f@e\x7f\x81\xc2\x07\x0c{\xba/'
 b'\xd4v\xf0\x1b\xf2\x07t\x8e\xe7<\xf5\xba\x11\xbc\xd7y\x9bD\x866'
 b'\xf4\xf0\xbf\x97\xde-\r\x00\xd3\x85\x12Sfrk\xd0\xa6\xe5\x156\xaa\xf0\x0c\r'
 b'_\x99L,\x94\x05\x87\xa9\xf04[p\x84\x84\xebs#J\x85\x86\xb9-\xfc;,0,,'
 b'X\xb6\x06\x86\x8a\xc3VQ\xa0\x94V(\x15\n\xad,h\xc7$\x84\x04\xd7\xa4\xbf'
 b'vu\x84\x04L!"?\x07~\xa8A\x1f\xd5\x1f\x03A\x04\x000\x14\x86\x94\x93'
 b'\x8aQ\xdd\x01\x12 \xf3\x18\x84\xc34\xaa\x084B"\x91H \x81\xc4\x89(H'
 b'\x8a\r\x07\n\x90\x9cnO\x92E>\xcfj\x15\xe2\xfe#\xc1\xc2\x04\xfc8\x8d<'
 b'\xf9|\xf2+\xf4\x07\xdc\xe4\x89\\6?\xb4c\x1fB\x13\xfb\xb8\xc1\xb4\x8f*\xc3'
 b'\x8e\x8a\x1f\x92\x11Lj\xe8\x8eT\x13J\xa5\xb3\x86\x04("h\x90\xfaR\xb6Y'
 b'\xe0\xbcD2r\xcax\xb4\xf3\xffC;\x14\x88C.D\xfdN\x08\x94+\xf0\xb9'
 b'\x9e\xac\x05\xb6d\x8c4\r1`<\x86\x94\x8a\xcf\xd6ex\xf4}#\x9c\xf3\x81}f\nk'
 b'\xb2\xc6za,|\x0c\x07a\xc4*\xba\xbc\x88\xa2a\xde\xc7\xb803m\x90w\\+\xc9\xd4'
 b'\xef-\x02\xd2\xdc\x88\x8f\xd0\xb1\xa0,\xd1!\xc4\x92\xb9\xbe\xa9\xc7\xd4'
 b'Z\xfcWp\x00\xcc\xf4\x948\x07!\xdc\x7fh\\\xbcO8\x7fc\xf3\xcf\x8fD'
 b'\x95\xee\xca\x00\xcf\xf0Z\x82\x07\x90\xea\x11`*\xc5\xefd\xc0j0\x80\xdao\xc6'
 b'(\x97\xa5\x8f\x074a\xd2\x1f9!\x184\xb7\x9cNQCK\xa2\xb1\x15J\x19\xb7A\xa3\xdd'
 b'\xa3-\xb2\xe9\x9e\x8b\x8e\xe5\x82\xc2\xcb\x13\xe4\xb0\x84\xbd\x9c\xe5\xd6S'
 b'5\x11Kd\x91u\x9b\x07\xe3\x14\xd3\x08\xe4\x86\xad_R\x12Ux\xf6%MS'
 b'\xb7\x99\x1b\xce\xc9\t*\x98\x97\xb43z\x01h\x9fu\xf1')

if __name__ == "__main__":
    test_main()
