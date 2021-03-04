Introduction
------------

``pyzstd`` module provides classes and functions for compressing and decompressing data, using Facebook's `Zstandard <http://www.zstd.net>`_ (or zstd as short name) algorithm.

The API is similar to Python's bz2/lzma/zlib module.

Includes zstd v1.4.9 source code.


Links
-----------

Documentation: https://pyzstd.readthedocs.io/en/latest

GitHub: https://github.com/animalize/pyzstd


Release note
------------
**0.14.3  (Mar 4, 2021)**

Update zstd source code from v1.4.8 to `v1.4.9 <https://github.com/facebook/zstd/releases/tag/v1.4.9>`_.

**0.14.2  (Feb 24, 2021)**

#. Add two convenient functions: `compress_stream() <https://pyzstd.readthedocs.io/en/latest/#compress_stream>`_, `decompress_stream() <https://pyzstd.readthedocs.io/en/latest/#decompress_stream>`_.

#. Some improvements.

**0.14.1  (Dec 19, 2020)**

#. Update zstd source code from v1.4.5 to `v1.4.8 <https://github.com/facebook/zstd/releases/tag/v1.4.8>`_.

    * v1.4.6 is a non-public release for Linux kernel.

    * v1.4.8 is a hotfix for `v1.4.7 <https://github.com/facebook/zstd/releases/tag/v1.4.7>`_.

#. Some improvements, no API changes.

**0.13.0  (Nov 7, 2020)**

#. ``ZstdDecompressor`` class: now it has the same API and behavior as BZ2Decompressor / LZMADecompressor classes in Python standard library, it stops after a frame is decompressed.

#. Add an ``EndlessZstdDecompressor`` class, it accepts multiple concatenated frames. It is renamed from previous ``ZstdDecompressor`` class, but ``.at_frame_edge`` is ``True`` when both input and output streams are at a frame edge.

#. Rename ``zstd_open()`` function to ``open()``, consistent with Python standard library.

#. ``decompress()`` function:

    * ~9% faster when: there is one frame, and the decompressed size was recorded in frame header.

    * raises ZstdError when input **or** output data is not at a frame edge. Previously, it only raise for output data is not at a frame edge.

**0.12.5  (Oct 12, 2020)**

No longer use `Argument Clinic <https://docs.python.org/3/howto/clinic.html>`_, now supports Python 3.5+, previously 3.7+.

**0.12.4  (Oct 7, 2020)**

It seems the API is stable.

**0.2.4  (Sep 2, 2020)**

The first version upload to PyPI.

Includes zstd `v1.4.5 <https://github.com/facebook/zstd/releases/tag/v1.4.5>`_ source code.