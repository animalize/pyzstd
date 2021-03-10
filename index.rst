.. title:: pyzstd moudle

Introduction
------------

pyzstd module provides classes and functions for compressing and decompressing data using Facebook's `Zstandard <http://www.zstd.net>`_ (or zstd as short name) algorithm. The API is similar to Python's bz2/lzma/zlib module.

Links: `GitHub page <https://github.com/animalize/pyzstd>`_, `PyPI page <https://pypi.org/project/pyzstd>`_.

Features of zstd:

* Fast compression and decompression speed.
* If use :ref:`multi-threaded compression<mt_compression>`, the compression speed improves significantly.
* If use pre-trained :ref:`dictionary<zstd_dict>`, the compression ratio on small data (a few KiB) improves dramatically.
* :ref:`Frame and block<frame_block>` allow the use more flexible, suitable for many scenarios.

.. note::
    Two other zstd modules on PyPI:

    * `zstd <https://pypi.org/project/zstd/>`_, a very simple module.
    * `zstandard <https://pypi.org/project/zstandard/>`_, provides rich API, supports PyPy.

Exception
---------

.. py:exception:: ZstdError

    This exception is raised when an error occurs when calling the underlying zstd library.


Common functions
----------------

    This section contains:

        * function :py:func:`compress`
        * function :py:func:`decompress`

    .. hint::
        If there are a big number of same type individual data, reuse these objects may eliminate the small overhead of creating context / setting parameters / loading dictionary.

        * compression: :py:class:`ZstdCompressor`, :py:class:`RichMemZstdCompressor`.
        * decompression: :py:class:`EndlessZstdDecompressor`.


.. py:function:: compress(data, level_or_option=None, zstd_dict=None)

    Compress *data*, return the compressed data.

    If compress ``b''``, return an empty content frame (9 bytes or more).

    :param data: Data to be compressed.
    :type data: bytes-like object
    :param level_or_option: When it's an ``int`` object, it represents :ref:`compression level<compression_level>`. When it's a ``dict`` object, it contains :ref:`advanced compression parameters<CParameter>`. The default value ``None`` means to use zstd's default compression level/parameters.
    :type level_or_option: int or dict
    :param zstd_dict: Pre-trained dictionary for compression.
    :type zstd_dict: ZstdDict
    :return: Compressed data
    :rtype: bytes

.. sourcecode:: python

    # int compression level
    compressed_dat = compress(raw_dat, 10)

    # dict option, use 6 threads to compress, and append a 4-byte checksum.
    option = {CParameter.compressionLevel : 10,
              CParameter.nbWorkers : 6,
              CParameter.checksumFlag : 1}
    compressed_dat = compress(raw_dat, option)


.. py:function:: decompress(data, zstd_dict=None, option=None)

    Decompress *data*, return the decompressed data.

    Support multiple concatenated frames.

    :param data: Data to be decompressed.
    :type data: bytes-like object
    :param zstd_dict: Pre-trained dictionary for decompression.
    :type zstd_dict: ZstdDict
    :param option: A ``dict`` object that contains :py:ref:`advanced decompression parameters<DParameter>`. The default value ``None`` means to use zstd's default decompression parameters.
    :type option: dict
    :return: Decompressed data
    :rtype: bytes
    :raises ZstdError: If decompression fails.


Rich memory compression
-----------------------

    Compress data using :ref:`rich memory mode<rich_mem>`. This mode is designed to allocate more memory, but faster in some cases.

    This section contains:

        * function :py:func:`richmem_compress`
        * class :py:class:`RichMemZstdCompressor`, a reusable compressor.

.. py:function:: richmem_compress(data, level_or_option=None, zstd_dict=None)

    Use :ref:`rich memory mode<rich_mem>` to compress *data*. It's faster than :py:func:`compress` in some cases, but allocates more memory.

    The parameters are the same as :py:func:`compress` function.

    If compress ``b''``, return an empty content frame (9 bytes or more).


.. py:class:: RichMemZstdCompressor

    A reusable compressor using :ref:`rich memory mode<rich_mem>`. It can be reused for big number of same type individual data.

    Since it can only generates individual :ref:`frames<frame_block>`, it's not suitable for streaming compression, otherwise the compression ratio will be reduced, and some programs can't decompress multiple frames data. For streaming compression, see :ref:`this section<stream_compression>`.

    Thread-safe at method level.

    .. py:method:: __init__(self, level_or_option=None, zstd_dict=None)

        The parameters are the same as :py:meth:`ZstdCompressor.__init__` method.

    .. py:method:: compress(self, data)

        Compress *data* use :ref:`rich memory mode<rich_mem>`, return a single zstd :ref:`frame<frame_block>`.

        If compress ``b''``, return an empty content frame (9 bytes or more).

        :param data: Data to be compressed.
        :type data: bytes-like object
        :return: A single zstd frame.
        :rtype: bytes

    .. sourcecode:: python

        c = RichMemZstdCompressor()
        frame1 = c.compress(raw_dat1)
        frame2 = c.compress(raw_dat2)


.. _stream_compression:

Streaming compression
---------------------

    This section contains:

        * function :py:func:`compress_stream`, a fast and convenient function.
        * class :py:class:`ZstdCompressor`, similar to compressors in Python standard library.

    It would be nice to know some knowledge about zstd data, see :ref:`frame and block<frame_block>`.

.. py:function:: compress_stream(input_stream, output_stream, *, level_or_option=None, zstd_dict=None, pledged_input_size=None, read_size=131_072, write_size=131_591, callback=None)

    A fast and convenient function, it compresses *input_stream* and writes the compressed data to *output_stream*. It doesn't close the streams.

    If input stream is ``b''``, nothing will be written to output stream.

    The default values of *read_size* and *write_size* parameters are the buffer sizes recommended by zstd, increasing them may be faster, and reduce the number of callback function calls.

    .. versionadded:: 0.14.2

    :param input_stream: Input stream that has a `.readinto(b) <https://docs.python.org/3/library/io.html#io.RawIOBase.readinto>`_ method.
    :param output_stream: Output stream that has a `.write(b) <https://docs.python.org/3/library/io.html#io.RawIOBase.write>`_ method. If use *callback* function, this argument can be ``None``.
    :param level_or_option: When it's an ``int`` object, it represents :ref:`compression level<compression_level>`. When it's a ``dict`` object, it contains :ref:`advanced compression parameters<CParameter>`. The default value ``None`` means to use zstd's default compression level/parameters.
    :type level_or_option: int or dict
    :param zstd_dict: Pre-trained dictionary for compression.
    :type zstd_dict: ZstdDict
    :param pledged_input_size: If set this argument to the size of input data, the :ref:`size<content_size>` will be written into frame header. If the actual input data doesn't match it, a :py:class:`ZstdError` exception will be raised. It may increase compression ratio slightly, and help decompression code to allocate output buffer faster.
    :type pledged_input_size: int
    :param read_size: Input buffer size, in bytes.
    :type read_size: int
    :param write_size: Output buffer size, in bytes.
    :type write_size: int
    :param callback: A callback function that accepts four parameters: ``(total_input, total_output, read_data, write_data)``, the first two are ``int`` objects, the last two are readonly `memoryview <https://docs.python.org/3/library/stdtypes.html#memory-views>`_ objects.
    :type callback: callable
    :return: A 2-item tuple, ``(total_input, total_output)``, the items are ``int`` objects.

    .. sourcecode:: python

        # compress an input file, and write to an output file.
        with io.open(input_file_path, 'rb') as ifh:
            with io.open(output_file_path, 'wb') as ofh:
                compress_stream(ifh, ofh, level_or_option=5)

        # compress a bytes object, and write to a file.
        with io.BytesIO(raw_dat) as bi:
            with io.open(output_file_path, 'wb') as ofh:
                compress_stream(bi, ofh, pledged_input_size=len(raw_dat))

        # compress an input file, obtain a bytes object.
        # compared to reading a file and compressing it in memory,
        # it's faster on Linux, slower on Windows.
        with io.open(input_file_path, 'rb') as ifh:
            with io.BytesIO() as bo:
                compress_stream(ifh, bo)
                compressed_dat = bo.getvalue()

        # with callback function
        def func(total_input, total_output, read_data, write_data):
            percent = 100 * total_input / input_file_size
            print(f'Progress: {percent:.1f}%')

        with io.open(input_file_path, 'rb') as ifh:
            with io.open(output_file_path, 'wb') as ofh:
                compress_stream(ifh, ofh, callback=func)


.. py:class:: ZstdCompressor

    A streaming compressor. It's thread-safe at method level.

    .. py:method:: __init__(self, level_or_option=None, zstd_dict=None)

        Initialize a ZstdCompressor object.

        :param level_or_option: When it's an ``int`` object, it represents the :ref:`compression level<compression_level>`. When it's a ``dict`` object, it contains :ref:`advanced compression parameters<CParameter>`. The default value ``None`` means to use zstd's default compression level/parameters.
        :type level_or_option: int or dict
        :param zstd_dict: Pre-trained dictionary for compression.
        :type zstd_dict: ZstdDict

    .. py:method:: compress(self, data, mode=ZstdCompressor.CONTINUE)

        Provide data to the compressor object.

        :param data: Data to be compressed.
        :type data: bytes-like object
        :param mode: Can be these 3 values: :py:attr:`ZstdCompressor.CONTINUE`, :py:attr:`ZstdCompressor.FLUSH_BLOCK`, :py:attr:`ZstdCompressor.FLUSH_FRAME`.
        :return: A chunk of compressed data if possible, or ``b''`` otherwise.
        :rtype: bytes

    .. py:method:: flush(self, mode=ZstdCompressor.FLUSH_FRAME)

        Flush any remaining data in internal buffer.

        Since zstd data consists of one or more independent frames, the compressor object can still be used after this method is called.

        **Note**: Abuse of this method will reduce compression ratio, and some programs can only decompress single frame data. Use it only when necessary.

        :param mode: Can be these 2 values: :py:attr:`ZstdCompressor.FLUSH_FRAME`, :py:attr:`ZstdCompressor.FLUSH_BLOCK`.
        :return: Flushed data.
        :rtype: bytes

    .. py:attribute:: last_mode

        The last mode used to this compressor, its value can be :py:attr:`~ZstdCompressor.CONTINUE`, :py:attr:`~ZstdCompressor.FLUSH_BLOCK`, :py:attr:`~ZstdCompressor.FLUSH_FRAME`. Initialized to :py:attr:`~ZstdCompressor.FLUSH_FRAME`.

        It can be used to get the current state of a compressor, such as, a block ends, a frame ends.

    .. py:attribute:: CONTINUE

        Used for *mode* argument in :py:meth:`~ZstdCompressor.compress` method.

        Collect more data, encoder decides when to output compressed result, for optimal compression ratio. Usually used for traditional streaming compression.

    .. py:attribute:: FLUSH_BLOCK

        Used for *mode* argument in :py:meth:`~ZstdCompressor.compress`, :py:meth:`~ZstdCompressor.flush` methods.

        Flush any remaining data, but don't close current :ref:`frame<frame_block>`. Usually used for communication scenarios.

        If there is data, it creates at least one new :ref:`block<frame_block>`, that can be decoded immediately on reception.

        **Note**: Abuse of this mode will reduce compression ratio. Use it only when necessary.

    .. py:attribute:: FLUSH_FRAME

        Used for *mode* argument in :py:meth:`~ZstdCompressor.compress`, :py:meth:`~ZstdCompressor.flush` methods.

        Flush any remaining data, and close current :ref:`frame<frame_block>`. Usually used for traditional flush.

        Since zstd data consists of one or more independent frames, data can still be provided after a frame is closed.

        **Note**: Abuse of this mode will reduce compression ratio, and some programs can only decompress single frame data. Use it only when necessary.

    .. sourcecode:: python

        c = ZstdCompressor()

        # traditional streaming compression
        dat1 = c.compress(b'123456')
        dat2 = c.compress(b'abcdef')
        dat3 = c.flush()

        # use .compress() method with mode argument
        compressed_dat1 = c.compress(raw_dat1, c.FLUSH_BLOCK)
        compressed_dat2 = c.compress(raw_dat2, c.FLUSH_FRAME)

    .. hint:: Why :py:meth:`ZstdCompressor.compress` method has a *mode* parameter?

        #. When reuse :py:class:`ZstdCompressor` object for big number of same type individual data, make operation more convenient. The object is thread-safe at method level.
        #. If data is generated by a single :py:attr:`~ZstdCompressor.FLUSH_FRAME` mode, the size of uncompressed data will be recorded in frame header.


Streaming decompression
-----------------------

    This section contains:

        * function :py:func:`decompress_stream`, a fast and convenient function.
        * class :py:class:`ZstdDecompressor`, similar to decompressors in Python standard library.
        * class :py:class:`EndlessZstdDecompressor`, a decompressor accepts multiple concatenated :ref:`frames<frame_block>`.

.. py:function:: decompress_stream(input_stream, output_stream, *, zstd_dict=None, option=None, read_size=131_075, write_size=131_072, callback=None)

    A fast and convenient function, it decompresses *input_stream* and writes the decompressed data to *output_stream*. It doesn't close the streams.

    Supports multiple concatenated frames.

    The default values of *read_size* and *write_size* parameters are the buffer sizes recommended by zstd, increasing them may be faster, and reduce the number of callback function calls.

    .. versionadded:: 0.14.2

    :param input_stream: Input stream that has a `.readinto(b) <https://docs.python.org/3/library/io.html#io.RawIOBase.readinto>`_ method.
    :param output_stream: Output stream that has a `.write(b) <https://docs.python.org/3/library/io.html#io.RawIOBase.write>`_ method. If use *callback* function, this argument can be ``None``.
    :param zstd_dict: Pre-trained dictionary for decompression.
    :type zstd_dict: ZstdDict
    :param option: A ``dict`` object, contains :ref:`advanced decompression parameters<DParameter>`.
    :type option: dict
    :param read_size: Input buffer size, in bytes.
    :type read_size: int
    :param write_size: Output buffer size, in bytes.
    :type write_size: int
    :param callback: A callback function that accepts four parameters: ``(total_input, total_output, read_data, write_data)``, the first two are ``int`` objects, the last two are readonly `memoryview <https://docs.python.org/3/library/stdtypes.html#memory-views>`_ objects.
    :type callback: callable
    :return: A 2-item tuple, ``(total_input, total_output)``, the items are ``int`` objects.
    :raises ZstdError: If decompression fails.

    .. sourcecode:: python

        # decompress an input file, and write to an output file.
        with io.open(input_file_path, 'rb') as ifh:
            with io.open(output_file_path, 'wb') as ofh:
                decompress_stream(ifh, ofh)

        # decompress a bytes object, and write to a file.
        with io.BytesIO(compressed_dat) as bi:
            with io.open(output_file_path, 'wb') as ofh:
                decompress_stream(bi, ofh)

        # decompress an input file, obtain a bytes object.
        # compared to reading a file and decompressing it in memory,
        # it's faster on Linux, slower on Windows.
        with io.open(input_file_path, 'rb') as ifh:
            with io.BytesIO() as bo:
                decompress_stream(ifh, bo)
                decompressed_dat = bo.getvalue()

        # with callback function
        def func(total_input, total_output, read_data, write_data):
            percent = 100 * total_input / input_file_size
            print(f'Progress: {percent:.1f}%')

        with io.open(input_file_path, 'rb') as ifh:
            with io.open(output_file_path, 'wb') as ofh:
                decompress_stream(ifh, ofh, callback=func)


.. py:class:: ZstdDecompressor

    A streaming decompressor.

    After a :ref:`frame<frame_block>` is decompressed, it stops and sets :py:attr:`~ZstdDecompressor.eof` flag to ``True``.

    For multiple frames data, use :py:class:`EndlessZstdDecompressor`.

    Thread-safe at method level.

    .. py:method:: __init__(self, zstd_dict=None, option=None)

        Initialize a ZstdDecompressor object.

        :param zstd_dict: Pre-trained dictionary for decompression.
        :type zstd_dict: ZstdDict
        :param dict option: A ``dict`` object that contains :ref:`advanced decompression parameters<DParameter>`. The default value ``None`` means to use zstd's default decompression parameters.

    .. py:method:: decompress(self, data, max_length=-1)

        Decompress *data*, returning decompressed data as a ``bytes`` object.

        After a :ref:`frame<frame_block>` is decompressed, it stops and sets :py:attr:`~ZstdDecompressor.eof` flag to ``True``.

        :param data: Data to be decompressed.
        :type data: bytes-like object
        :param int max_length: Maximum size of returned data. When it's negative, the output size is unlimited. When it's non-negative, returns at most *max_length* bytes of decompressed data. If this limit is reached and further output can (or may) be produced, the :py:attr:`~ZstdDecompressor.needs_input` attribute will be set to ``False``. In this case, the next call to this method may provide *data* as ``b''`` to obtain more of the output.

    .. py:attribute:: needs_input

        If the *max_length* output limit in :py:meth:`~ZstdDecompressor.decompress` method has been reached, and the decompressor has (or may has) unconsumed input data, it will be set to ``False``. In this case, pass ``b''`` to :py:meth:`~ZstdDecompressor.decompress` method may output further data.

        If ignore this attribute when there is unconsumed input data, there will be a little performance loss because of extra memory copy.

    .. py:attribute:: eof

        ``True`` means the end of the first frame has been reached. If decompress data after that, an ``EOFError`` exception will be raised.

    .. py:attribute:: unused_data

        A bytes object. When ZstdDecompressor object stops after decompressing a frame, unused input data after the first frame. Otherwise this will be ``b''``.

    .. sourcecode:: python

        # --- unlimited output ---
        d1 = ZstdDecompressor()

        decompressed_dat1 = d1.decompress(dat1)
        decompressed_dat2 = d1.decompress(dat2)
        decompressed_dat3 = d1.decompress(dat3)

        assert d1.eof, 'data is an incomplete zstd frame.'

        # --- limited output ---
        d2 = ZstdDecompressor()

        while True:
            if d2.needs_input:
                dat = read_input(2*1024*1024) # read 2 MiB input data
                if not dat: # input stream ends
                    raise Exception('Input stream ends, but the end of '
                                    'the first frame is not reached.')
            else: # maybe there is unconsumed input data
                dat = b''

            chunk = d2.decompress(dat, 10*1024*1024) # limit output buffer to 10 MiB
            write_output(chunk)

            if d2.eof: # reach the end of the first frame
                break


.. py:class:: EndlessZstdDecompressor

    It doesn't stop after a :ref:`frame<frame_block>` is decompressed, can be used in these scenarios:

        * Streaming decompression for multiple concatenated frames
        * Reuse for big number of same type individual data

    Thread-safe at method level.

    .. py:method:: __init__(self, zstd_dict=None, option=None)

        The parameters are the same as :py:meth:`ZstdDecompressor.__init__` method.

    .. py:method:: decompress(self, data, max_length=-1)

        The parameters are the same as :py:meth:`ZstdDecompressor.decompress` method.

        After decompressing a frame, it doesn't stop like :py:meth:`ZstdDecompressor.decompress`.

    .. py:attribute:: needs_input

        It's the same as :py:attr:`ZstdDecompressor.needs_input`.

    .. py:attribute:: at_frame_edge

        ``True`` when both input and output streams are at a :ref:`frame<frame_block>` edge, or the decompressor just be initialized.

        This flag could be used to check data integrity in some cases.

    .. sourcecode:: python

        # --- streaming decomression, unlimited output ---
        d1 = EndlessZstdDecompressor()

        decompressed_dat1 = d1.decompress(dat1)
        decompressed_dat2 = d1.decompress(dat2)
        decompressed_dat3 = d1.decompress(dat3)

        assert d1.at_frame_edge, 'data ends in an incomplete frame.'

        # --- streaming decomression, limited output ---
        d2 = EndlessZstdDecompressor()

        while True:
            if d2.needs_input:
                dat = read_input(2*1024*1024) # read 2 MiB input data
                if not dat: # input stream ends
                    if not d2.at_frame_edge:
                        raise Exception('data ends in an incomplete frame.')
                    break
            else: # maybe there is unconsumed input data
                dat = b''

            chunk = d2.decompress(dat, 10*1024*1024) # limit output buffer to 10 MiB
            write_output(chunk)

        # --- reuse for same type individual data ---

        # reuse an object may eliminate the small overhead of creating
        # context / setting parameters / loading dictionary.
        d3 = EndlessZstdDecompressor()
        for compressed_data in data_source():
            decompressed_data = d3.decompress(compressed_data)

            # check data integrity
            if not d3.at_frame_edge:
                decompressed_data = None  # decompressed data is incomplete
                d3 = EndlessZstdDecompressor() # reset decompressor

    .. hint:: Why :py:class:`EndlessZstdDecompressor` doesn't stop at frame edges?

        If so, unused input data after an edge will be copied to an internal buffer, this may be a performance overhead.

        If want to stop at frame edges, write a wrapper using :py:class:`ZstdDecompressor` class. And don't feed too much data every time, the overhead of copying unused input data to :py:attr:`ZstdDecompressor.unused_data` attribute still exists.


.. _zstd_dict:

Dictionary
----------

    This section contains:

        * class :py:class:`ZstdDict`
        * function :py:func:`train_dict`
        * function :py:func:`finalize_dict`

.. note::
    If use pre-trained zstd dictionary, the compression ratio achievable on small data (a few KiB) improves dramatically, has best effect on data that smaller than 1 KiB.

    **Attention**

        #. If you lose a zstd dictionary, then can't decompress the corresponding data.
        #. Zstd dictionary is vulnerable.
        #. Zstd dictionary has negligible effect on large data (multi-MiB) compression.

    **Background**

    The smaller the amount of data to compress, the more difficult it is to compress. This problem is common to all compression algorithms, and reason is, compression algorithms learn from past data how to compress future data. But at the beginning of a new data set, there is no "past" to build upon.

    Zstd training mode can be used to tune the algorithm for a selected type of data. Training is achieved by providing it with a few samples (one file per sample). The result of this training is stored in a file called "dictionary", which must be loaded before compression and decompression.


.. py:class:: ZstdDict

    Represents a zstd dictionary, can be used for compression/decompression.

    It's thread-safe, and can be shared by multiple :py:class:`ZstdCompressor` / :py:class:`ZstdDecompressor` objects. It has an internal cache for costly digesting.

    .. py:method:: __init__(self, dict_content, is_raw=False)

        Initialize a ZstdDict object.

        :param dict_content: Dictionary's content.
        :type dict_content: bytes-like object
        :param is_raw: This parameter is for advanced user. ``True`` means *dict_content* argument is a "raw content" dictionary, free of any format restriction. ``False`` means *dict_content* argument is an ordinary zstd dictionary, was created by zstd functions, follow a specified format.
        :type is_raw: bool

    .. py:attribute:: dict_content

        The content of zstd dictionary, a ``bytes`` object. It's the same as *dict_content* argument in :py:meth:`~ZstdDict.__init__` method. It can be used with other programs.

    .. py:attribute:: dict_id

        ID of zstd dictionary, a 32-bit unsigned integer value. See :ref:`this note<dict_id>` for details.

        Non-zero means ordinary dictionary, was created by zstd functions, follow a specified format.

        ``0`` means a "raw content" dictionary, free of any format restriction, used for advanced user. (Note that the meaning of ``0`` is different from ``dictionary_id`` in :py:func:`get_frame_info` function.)

    .. sourcecode:: python

        # load a zstd dictionary from file
        with io.open(dict_path, 'rb') as f:
            file_content = f.read()
        zd = ZstdDict(file_content)

        # use the dictionary to compress
        compressed_dat = compress(raw_dat, zstd_dict=zd)


.. py:function:: train_dict(samples, dict_size)

    Train a zstd dictionary, see :ref:`tips<train_tips>` for training a zstd dictionary.

    :param samples: An iterable of samples, a sample is a bytes-like object represents a file.
    :type samples: iterable
    :param int dict_size: Returned zstd dictionary's **maximum** size, in bytes.
    :return: Trained zstd dictionary. If want to save the dictionary to a file, save the :py:attr:`ZstdDict.dict_content` attribute.
    :rtype: ZstdDict

    .. sourcecode:: python

        def samples():
            rootdir = r"E:\data"

            # Note that the order of the files may be different,
            # therefore the generated dictionary may be different.
            for parent, dirnames, filenames in os.walk(rootdir):
                for filename in filenames:
                    path = os.path.join(parent, filename)
                    with io.open(path, 'rb') as f:
                        dat = f.read()
                    yield dat

        dic = pyzstd.train_dict(samples(), 100*1024)

.. _train_tips:

.. tip:: Training a zstd dictionary

   1. A reasonable dictionary has a size of ~100 KiB. It's possible to select smaller or larger size, just by specifying *dict_size* argument.
   2. It's recommended to provide a few thousands samples, though this can vary a lot.
   3. It's recommended that total size of all samples be about ~x100 times the target size of dictionary.
   4. Dictionary training will fail if there are not enough samples to construct a dictionary, or if most of the samples are too small (< 8 bytes being the lower limit). If dictionary training fails, you should use zstd without a dictionary, as the dictionary would've been ineffective anyways.
   5. You may compose a more efficient dictionary by hand, and use :py:func:`finalize_dict` function to finalize a dictionary. For example, use the general parts of some files to compose a more efficient dictionary.
   6. It would be nice to know some knowledge about dictionary ID, see :ref:`this note<dict_id>`.

.. py:function:: finalize_dict(zstd_dict, samples, dict_size, level)

    Given a custom content as a basis for dictionary, and a set of samples, finalize dictionary by adding headers and statistics according to the zstd dictionary format.

    You may compose an efficient dictionary content by hand, which is used as basis dictionary, and use some samples to finalize a dictionary. The basis dictionary can be a "raw content" dictionary, see *is_raw* argument in :py:meth:`ZstdDict.__init__` method. When composing text content, pay attention to newline characters.

    There is a practical `usage <https://github.com/facebook/zstd/issues/2203>`_ on zstd GitHub Issues.

    :param zstd_dict: A basis dictionary.
    :type zstd_dict: ZstdDict
    :param samples: An iterable of samples, a sample is a bytes-like object represents a file.
    :type samples: iterable
    :param int dict_size: Returned zstd dictionary's **maximum** size, in bytes.
    :param int level: The compression level expected to use in production. The statistics for each compression level differ, so tuning the dictionary for the compression level can help quite a bit.
    :return: Finalized zstd dictionary. If want to save the dictionary to a file, save the :py:attr:`ZstdDict.dict_content` attribute.
    :rtype: ZstdDict


Module-level functions
----------------------

    This section contains:

        * function :py:func:`get_frame_info`, get frame infomation from frame header.
        * function :py:func:`get_frame_size`, get a frame's size.

.. py:function:: get_frame_info(frame_buffer)

    Get zstd frame infomation from a frame header.

    Return a two-items namedtuple: (decompressed_size, dictionary_id)

    If ``decompressed_size`` is ``None``, decompressed size is unknown.

    ``dictionary_id`` is a 32-bit unsigned integer value. ``0`` means dictionary ID was not recorded in frame header, the frame may or may not need a dictionary to be decoded, and the ID of such a dictionary is not specified. (Note that the meaning of ``0`` is different from :py:attr:`ZstdDict.dict_id` attribute.)

    It's possible to append more items to the namedtuple in the future.

    :param frame_buffer: It should starts from the beginning of a frame, and contains at least the frame header (6 to 18 bytes).
    :type frame_buffer: bytes-like object
    :return: Information about a frame.
    :rtype: namedtuple
    :raises ZstdError: When parsing the frame header fails.

.. sourcecode:: python

    >>> pyzstd.get_frame_info(compressed_dat[:20])
    frame_info(decompressed_size=687379, dictionary_id=1040992268)


.. py:function:: get_frame_size(frame_buffer)

    Get the size of a zstd frame, including frame header and 4-byte checksum if it has.

    It will iterate all blocks' header within a frame, to accumulate the frame's size.

    :param frame_buffer: It should starts from the beginning of a frame, and contains at least one complete frame.
    :type frame_buffer: bytes-like object
    :return: The size of a zstd frame.
    :rtype: int
    :raises ZstdError: When it fails.

.. sourcecode:: python

    >>> pyzstd.get_frame_size(compressed_dat)
    252874


Module-level variables
----------------------

    This section contains:

        * :py:data:`zstd_version`, a ``str``.
        * :py:data:`zstd_version_info`, a ``tuple``.
        * :py:data:`compressionLevel_values`, some values defined by underlying zstd library.

.. py:data:: zstd_version

    Underlying zstd library's version, ``str`` form.

.. sourcecode:: python

    >>> pyzstd.zstd_version
    '1.4.5'


.. py:data:: zstd_version_info

    Underlying zstd library's version, ``tuple`` form.

.. sourcecode:: python

    >>> pyzstd.zstd_version_info
    (1, 4, 5)


.. py:data:: compressionLevel_values

    A three-items namedtuple, values defined by underlying zstd library, see :ref:`compression level<compression_level>` for details.

    ``default`` is default compression level, it is used when compression level is set to ``0``.

    ``min``/``max`` are minimum/maximum avaliable values of compression level, both inclusive.

.. sourcecode:: python

    >>> pyzstd.compressionLevel_values  # 131072 = 128*1024
    values(default=3, min=-131072, max=22)


ZstdFile class and open() function
---------------------------------------

.. py:class:: ZstdFile

    Open a zstd-compressed file in binary mode.

    This class is very similar to `bz2.BZ2File <https://docs.python.org/3/library/bz2.html#bz2.BZ2File>`_ /  `gzip.GzipFile <https://docs.python.org/3/library/gzip.html#gzip.GzipFile>`_ / `lzma.LZMAFile <https://docs.python.org/3/library/lzma.html#lzma.LZMAFile>`_ classes in Python standard library. You may read their documentation.

    This class can be used with Python's ``tarfile`` module, see :ref:`this note<with_tarfile>`.

    .. py:method:: __init__(self, filename, mode="r", *, level_or_option=None, zstd_dict=None)

        When using read mode (decompression), the *level_or_option* argument can only be a ``dict`` object, that represents decompression option. It doesn't support ``int`` type compression level in this case.

.. py:function:: open(filename, mode="rb", *, level_or_option=None, zstd_dict=None, encoding=None, errors=None, newline=None)

    Open a zstd-compressed file in binary or text mode, returning a file object (:py:class:`ZstdFile` or `io.TextIOWrapper <https://docs.python.org/3/library/io.html#io.TextIOWrapper>`_).

    This function is very similar to `bz2.open() <https://docs.python.org/3/library/bz2.html#bz2.open>`_ / `gzip.open() <https://docs.python.org/3/library/gzip.html#gzip.open>`_ / `lzma.open() <https://docs.python.org/3/library/lzma.html#lzma.open>`_ functions in Python standard library. You may read their documentation.

    When using read mode (decompression), the *level_or_option* argument can only be a ``dict`` object, that represents decompression option. It doesn't support ``int`` type compression level in this case.


Advanced parameters
-------------------

    This section contains class :py:class:`CParameter`, :py:class:`DParameter`, :py:class:`Strategy`, they are subclass of IntEnum, used for setting advanced parameters.

    :py:class:`CParameter` class' attributes:

        - Compression level (:py:attr:`~CParameter.compressionLevel`)
        - Compress algorithm parameters (:py:attr:`~CParameter.windowLog`, :py:attr:`~CParameter.hashLog`, :py:attr:`~CParameter.chainLog`, :py:attr:`~CParameter.searchLog`, :py:attr:`~CParameter.minMatch`, :py:attr:`~CParameter.targetLength`, :py:attr:`~CParameter.strategy`)
        - Long distance matching (:py:attr:`~CParameter.enableLongDistanceMatching`, :py:attr:`~CParameter.ldmHashLog`, :py:attr:`~CParameter.ldmMinMatch`, :py:attr:`~CParameter.ldmBucketSizeLog`, :py:attr:`~CParameter.ldmHashRateLog`)
        - Misc (:py:attr:`~CParameter.contentSizeFlag`, :py:attr:`~CParameter.checksumFlag`, :py:attr:`~CParameter.dictIDFlag`)
        - Multi-threaded compression (:py:attr:`~CParameter.nbWorkers`, :py:attr:`~CParameter.jobSize`, :py:attr:`~CParameter.overlapLog`)

    :py:class:`DParameter` class' attribute:

        - Decompression parameter (:py:attr:`~DParameter.windowLogMax`)

    :py:class:`Strategy` class' attributes:

        :py:attr:`~Strategy.fast`, :py:attr:`~Strategy.dfast`, :py:attr:`~Strategy.greedy`, :py:attr:`~Strategy.lazy`, :py:attr:`~Strategy.lazy2`, :py:attr:`~Strategy.btlazy2`, :py:attr:`~Strategy.btopt`, :py:attr:`~Strategy.btultra`, :py:attr:`~Strategy.btultra2`.

.. _CParameter:

.. py:class:: CParameter(IntEnum)

    Advanced compression parameters.

    When using, put the parameters in a ``dict`` object, the key is a :py:class:`CParameter` name, the value is a 32-bit signed integer value.

    Each parameter should belong to an interval with lower and upper bounds, otherwise they will either trigger an error or be automatically clamped.

    The constant values mentioned below are defined in `zstd.h <https://github.com/facebook/zstd/blob/release/lib/zstd.h>`_, note that these values may be different in different zstd versions.

    .. sourcecode:: python

        option = {CParameter.compressionLevel : 10,
                  CParameter.checksumFlag : 1}

        # used with compress() function
        compressed_dat = compress(raw_dat, option)

        # used with ZstdCompressor object
        c = ZstdCompressor(level_or_option=option)
        compressed_dat1 = c.compress(raw_dat)
        compressed_dat2 = c.flush()

    .. py:method:: bounds(self)

        Return lower and upper bounds of a parameter, both inclusive.

        .. sourcecode:: python

            >>> CParameter.compressionLevel.bounds()
            (-131072, 22)
            >>> CParameter.windowLog.bounds()
            (10, 31)
            >>> CParameter.enableLongDistanceMatching.bounds()
            (0, 1)

    .. py:attribute:: compressionLevel

        Set compression parameters according to pre-defined compressionLevel table, see :ref:`compression level<compression_level>` for details.

        Setting a compression level does not set all other compression parameters to default. Setting this will dynamically impact the compression parameters which have not been manually set, the manually set ones will "stick".

    .. py:attribute:: windowLog

        Maximum allowed back-reference distance, expressed as power of 2, ``1 << windowLog`` bytes.

        This will set a memory budget for streaming decompression, with larger values requiring more memory and typically compressing more.

        Must be clamped between ``ZSTD_WINDOWLOG_MIN`` and ``ZSTD_WINDOWLOG_MAX``.

        Special: value ``0`` means "use default windowLog", then the value is dynamically set, see "W" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

        Note: Using a windowLog greater than ``ZSTD_WINDOWLOG_LIMIT_DEFAULT`` requires explicitly allowing such size at streaming decompression stage, the constant is ``27`` in zstd v1.4.8, means 128 MiB (1 << 27).

    .. py:attribute:: hashLog

        Size of the initial probe table, as a power of 2, resulting memory usage is ``1 << (hashLog+2)`` bytes.

        Must be clamped between ``ZSTD_HASHLOG_MIN`` and ``ZSTD_HASHLOG_MAX``.

        Larger tables improve compression ratio of strategies <= :py:attr:`~Strategy.dfast`, and improve speed of strategies > :py:attr:`~Strategy.dfast`.

        Special: value ``0`` means "use default hashLog", then the value is dynamically set, see "H" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

    .. py:attribute:: chainLog

        Size of the multi-probe search table, as a power of 2, resulting memory usage is ``1 << (chainLog+2)`` bytes.

        Must be clamped between ``ZSTD_CHAINLOG_MIN`` and ``ZSTD_CHAINLOG_MAX``.

        Larger tables result in better and slower compression.

        This parameter is useless for :py:attr:`~Strategy.fast` strategy.

        It's still useful when using :py:attr:`~Strategy.dfast` strategy, in which case it defines a secondary probe table.

        Special: value ``0`` means "use default chainLog", then the value is dynamically set, see "C" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

    .. py:attribute:: searchLog

        Number of search attempts, as a power of 2.

        More attempts result in better and slower compression.

        This parameter is useless for :py:attr:`~Strategy.fast` and :py:attr:`~Strategy.dfast` strategies.

        Special: value ``0`` means "use default searchLog", then the value is dynamically set, see "S" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

    .. py:attribute:: minMatch

        Minimum size of searched matches.

        Note that Zstandard can still find matches of smaller size, it just tweaks its search algorithm to look for this size and larger.

        Larger values increase compression and decompression speed, but decrease ratio.

        Must be clamped between ``ZSTD_MINMATCH_MIN`` and ``ZSTD_MINMATCH_MAX``.

        Note that currently, for all strategies < :py:attr:`~Strategy.btopt`, effective minimum is ``4``, for all strategies > :py:attr:`~Strategy.fast`, effective maximum is ``6``.

        Special: value ``0`` means "use default minMatchLength", then the value is dynamically set, see "L" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

    .. py:attribute:: targetLength

        Impact of this field depends on strategy.

        For strategies :py:attr:`~Strategy.btopt`, :py:attr:`~Strategy.btultra` & :py:attr:`~Strategy.btultra2`:

            Length of Match considered "good enough" to stop search.

            Larger values make compression stronger, and slower.

        For strategy :py:attr:`~Strategy.fast`:

            Distance between match sampling.

            Larger values make compression faster, and weaker.

        Special: value ``0`` means "use default targetLength", then the value is dynamically set, see "TL" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

    .. py:attribute:: strategy

        See :py:attr:`Strategy` class definition.

        The higher the value of selected strategy, the more complex it is, resulting in stronger and slower compression.

        Special: value ``0`` means "use default strategy", then the value is dynamically set, see "strat" column in this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_.

    .. py:attribute:: enableLongDistanceMatching

        Enable long distance matching.

        This parameter is designed to improve compression ratio, for large inputs, by finding large matches at long distance.

        It increases memory usage and window size.

        Note:
            * Enabling this parameter increases default :py:attr:`~CParameter.windowLog` to 128 MiB except when expressly set to a different value.
            * This will be enabled by default if :py:attr:`~CParameter.windowLog` >= 128 MiB and compression strategy >= :py:attr:`~Strategy.btopt` (compression level 16+).

    .. py:attribute:: ldmHashLog

        Size of the table for long distance matching, as a power of 2.

        Larger values increase memory usage and compression ratio, but decrease compression speed.

        Must be clamped between ``ZSTD_HASHLOG_MIN`` and ``ZSTD_HASHLOG_MAX``, default: :py:attr:`~CParameter.windowLog` - 7.

        Special: value ``0`` means "automatically determine hashlog".

    .. py:attribute:: ldmMinMatch

        Minimum match size for long distance matcher.

        Larger/too small values usually decrease compression ratio.

        Must be clamped between ``ZSTD_LDM_MINMATCH_MIN`` and ``ZSTD_LDM_MINMATCH_MAX``.

        Special: value ``0`` means "use default value" (default: 64).

    .. py:attribute:: ldmBucketSizeLog

        Log size of each bucket in the LDM hash table for collision resolution.

        Larger values improve collision resolution but decrease compression speed.

        The maximum value is ``ZSTD_LDM_BUCKETSIZELOG_MAX``.

        Special: value ``0`` means "use default value" (default: 3).

    .. py:attribute:: ldmHashRateLog

        Frequency of inserting/looking up entries into the LDM hash table.

        Must be clamped between 0 and ``(ZSTD_WINDOWLOG_MAX - ZSTD_HASHLOG_MIN)``.

        Default is MAX(0, (:py:attr:`~CParameter.windowLog` - :py:attr:`~CParameter.ldmHashLog`)), optimizing hash table usage.

        Larger values improve compression speed.

        Deviating far from default value will likely result in a compression ratio decrease.

        Special: value ``0`` means "automatically determine hashRateLog".

    .. _content_size:

    .. py:attribute:: contentSizeFlag

        Uncompressed content size will be written into frame header whenever known.

        Default value is ``1``.

        In traditional streaming compression, content size is unknown.

        In these compressions, the content size is known:

            * :py:func:`compress` function
            * :py:func:`richmem_compress` function
            * :py:class:`RichMemZstdCompressor` class
            * :py:func:`compress_stream` function setting *pledged_input_size* argument
            * :py:class:`ZstdCompressor` class using a single :py:attr:`~ZstdCompressor.FLUSH_FRAME` mode

        The field in frame header is 1/2/4/8 bytes, depending on size value. It may help decompression code to allocate output buffer faster.

    .. py:attribute:: checksumFlag

        A 4-byte checksum of uncompressed content is written at the end of frame. If decompression verification fails, a :py:class:`ZstdError` exception will be raised.

        Default value is ``0``.

    .. py:attribute:: dictIDFlag

        When applicable, dictionary's ID is written into frame header. See :ref:`this note<dict_id>` for details.

        Default value is ``1``.

    .. py:attribute:: nbWorkers

        Select how many threads will be spawned to compress in parallel.

        When nbWorkers > ``1``, enables multi-threaded compression, see :ref:`zstd multi-threaded compression<mt_compression>` for details.

        More workers improve speed, but also increase memory usage.

        Default value is ``0``, aka "single-threaded mode" : no worker is spawned, compression is performed inside caller's thread.

    .. py:attribute:: jobSize

        Size of a compression job, in bytes. This value is enforced only when :py:attr:`~CParameter.nbWorkers` > 1.

        Each compression job is completed in parallel, so this value can indirectly impact the nb of active threads.

        ``0`` means default, which is dynamically determined based on compression parameters.

        Job size must be a minimum of overlap size (specified by :py:attr:`CParameter.overlapLog`), or 1 MiB, whichever is largest.

        The minimum size is automatically and transparently enforced.

    .. py:attribute:: overlapLog

        Control the overlap size, as a fraction of window size.

        The overlap size is an amount of data reloaded from previous job at the beginning of a new job.

        It helps preserve compression ratio, while each job is compressed in parallel.

        This value is enforced only when :py:attr:`~CParameter.nbWorkers` > 1.

        Larger values increase compression ratio, but decrease speed.

        Possible values range from 0 to 9 :

        - 0 means "default" : value will be determined by the library, depending on :py:attr:`~CParameter.strategy`
        - 1 means "no overlap"
        - 9 means "full overlap", using a full window size.

        Each intermediate rank increases/decreases load size by a factor 2 :

        9: full window;  8: w/2;  7: w/4;  6: w/8;  5:w/16;  4: w/32;  3:w/64;  2:w/128;  1:no overlap;  0:default

        Default value varies between 6 and 9, depending on :py:attr:`~CParameter.strategy`.

        "Window size" and :py:attr:`CParameter.windowLog` are different, see `zstd format document <https://github.com/facebook/zstd/blob/release/doc/zstd_compression_format.md#window_descriptor>`_ for details.


.. _DParameter:

.. py:class:: DParameter(IntEnum)

    Advanced decompression parameters.

    When using, put the parameters in a ``dict`` object, the key is a :py:class:`DParameter` name, the value is a 32-bit signed integer value.

    Each parameter should belong to an interval with lower and upper bounds, otherwise they will either trigger an error or be automatically clamped.

    The constant values mentioned below are defined in `zstd.h <https://github.com/facebook/zstd/blob/release/lib/zstd.h>`_, note that these values may be different in different zstd versions.

    .. sourcecode:: python

        # set memory allocation limit to 16 MiB (1 << 24)
        option = {DParameter.windowLogMax : 24}

        # used with decompress() function
        decompressed_dat = decompress(dat, option=option)

        # used with ZstdDecompressor object
        d = ZstdDecompressor(option=option)
        decompressed_dat = d.decompress(dat)

    .. py:method:: bounds(self)

        Return lower and upper bounds of a parameter, both inclusive.

        .. sourcecode:: python

            >>> DParameter.windowLogMax.bounds()
            (10, 31)

    .. py:attribute:: windowLogMax

        Select a size limit (in power of 2) beyond which the streaming API will refuse to allocate memory buffer in order to protect the host from unreasonable memory requirements.

        This parameter is only useful in streaming mode, since no internal buffer is allocated in single-pass mode. :py:func:`decompress` function may use streaming mode or single-pass mode.

        By default, a decompression context accepts window sizes <= ``(1 << ZSTD_WINDOWLOG_LIMIT_DEFAULT)``, the constant is ``27`` in zstd v1.4.8, means 128 MiB (1 << 27). If frame requested window size is greater than this value, need to explicitly set this parameter.

        Special: value ``0`` means "use default maximum windowLog".


.. py:class:: Strategy(IntEnum)

    Used for :py:attr:`CParameter.strategy`.

    Compression strategies, listed from fastest to strongest.

    Note : new strategies **might** be added in the future, only the order (from fast to strong) is guaranteed.

    .. py:attribute:: fast
    .. py:attribute:: dfast
    .. py:attribute:: greedy
    .. py:attribute:: lazy
    .. py:attribute:: lazy2
    .. py:attribute:: btlazy2
    .. py:attribute:: btopt
    .. py:attribute:: btultra
    .. py:attribute:: btultra2

    .. sourcecode:: python

        option = {CParameter.strategy : Strategy.lazy2,
                  CParameter.checksumFlag : 1}
        compressed_dat = compress(raw_dat, option)


Informative notes
-----------------

Compression level
>>>>>>>>>>>>>>>>>

.. _compression_level:

.. note:: Compression level

    Compression level is an integer:

    * ``1`` to ``22`` (currently), regular levels. Levels >= 20, labeled *ultra*, should be used with caution, as they require more memory.
    * ``0`` means use default level, which is currently ``3`` defined by underlying zstd library.
    * ``-131072`` to ``-1``, negative levels extend the range of speed vs ratio preferences. The lower the level, the faster the speed, but at the cost of compression ratio. 131072 = 128*1024.

    :py:data:`compressionLevel_values` is some values defined by underlying zstd library.

    **For advanced user**

    Compression levels are just numbers that map to a set of compression parameters, see this `v1.4.8 table <https://github.com/facebook/zstd/blob/v1.4.8/lib/compress/zstd_compress.c#L4971-L5076>`_ for overview. The parameters may be adjusted by underlying zstd library after gathering some infomation, such as data size, using dictionary or not.

    Setting a compression level does not set all other :ref:`compression parameters<CParameter>` to default. Setting this will dynamically impact the compression parameters which have not been manually set, the manually set ones will "stick".


Frame and block
>>>>>>>>>>>>>>>

.. _frame_block:

.. note:: Frame and block

    **Frame**

    Zstd data consists of one or more independent "frames". The decompressed content of multiple concatenated frames is the concatenation of each frame decompressed content.

    A frame is completely independent, has a frame header, and a set of parameters which tells the decoder how to decompress it.

    In addition to normal frame, there is `skippable frame <https://github.com/facebook/zstd/blob/release/doc/zstd_compression_format.md#skippable-frames>`_ that can contain any user-defined data, skippable frame will be decompressed to ``b''``.

    **Block**

    A frame encapsulates one or multiple "blocks". Block has a guaranteed maximum size (3 bytes block header + 128 KiB), the actual maximum size depends on frame parameters.

    Unlike independent frames, each block depends on previous blocks for proper decoding, but doesn't need later blocks. So flushing block may be used in communication scenarios, see :py:attr:`ZstdCompressor.FLUSH_BLOCK`.

    .. attention::

        In some `language bindings <https://facebook.github.io/zstd/#other-languages>`_, decompress() function doesn't support multiple frames, or/and doesn't support a frame with unknown :ref:`content size<content_size>`, pay attention when compressing data for other languages/modules.


Multi-threaded compression
>>>>>>>>>>>>>>>>>>>>>>>>>>

.. _mt_compression:

.. note:: Multi-threaded compression

    Zstd library supports multi-threaded compression, set :py:attr:`CParameter.nbWorkers` parameter > ``1`` to enable multi-threaded compression.

    The threads are spawned by underlying zstd library, not by pyzstd module.

    .. sourcecode:: python

        # use 4 threads to compress
        option = {CParameter.nbWorkers : 4}
        compressed_dat = compress(raw_dat, option)

    The data will be split into portions and compressed in parallel. The portion size can be specified by :py:attr:`CParameter.jobSize` parameter, the overlap size can be specified by :py:attr:`CParameter.overlapLog` parameter, usually don't need to set these.

    The multi-threaded output will be different than the single-threaded output. However, both are deterministic, and the multi-threaded output produces the same compressed data no matter how many threads used.

    The multi-threaded output is a single :ref:`frame<frame_block>`, it's larger a little. Compressing a 520.58 MiB data, single-threaded output is 273.55 MiB, multi-threaded output is 274.33 MiB.


Rich memory mode
>>>>>>>>>>>>>>>>

.. _rich_mem:

.. note:: Rich memory mode

    pyzstd module has a "rich memory mode" for compression. It is designed to allocate more memory, but faster in some cases.

    There is a :py:func:`richmem_compress` function, a :py:class:`RichMemZstdCompressor` class. (Note that currently it won't be faster when using :ref:`zstd multi-threaded compression <mt_compression>`, it will issue a ``ResourceWarnings`` in this case.)

    Effects:

    * The output buffer is larger than input data a little.
    * If input data is larger than ~31.8KB, 4 ~ 15% faster.

    When not using this mode, the output buffer grows `gradually <https://github.com/animalize/pyzstd/blob/0.14.2/src/_zstdmodule.c#L135-L160>`_, in order not to allocate too much memory. The negative effect is that pyzstd module usually need to call the underlying zstd library's compress function multiple times.

    When using this mode, the size of output buffer is provided by ZSTD_compressBound() function, which is larger than input data a little (maximum compressed size in worst case single-pass scenario). For a 100 MiB input data, the allocated output buffer is (100 MiB + 400 KiB). The underlying zstd library has a speed optimization for this output buffer size (~4% faster than this size - 1).

    .. sourcecode:: python

        # use richmem_compress() function
        compressed_dat = richmem_compress(raw_dat)

        # reuse RichMemZstdCompressor object
        c = RichMemZstdCompressor()
        frame1 = c.compress(raw_dat1)
        frame2 = c.compress(raw_dat2)

    Compressing a 520.58 MiB data, it accelerates from 5.40 seconds to 4.62 seconds.


Use with tarfile module
>>>>>>>>>>>>>>>>>>>>>>>

.. _with_tarfile:

.. note:: Use with tarfile module

    Python's `tarfile <https://docs.python.org/3/library/tarfile.html>`_ module supports arbitrary compression algorithms by providing a file object.

    This code encapsulates a ``ZstdTarFile`` class using :py:class:`ZstdFile`, it can be used like `tarfile.TarFile <https://docs.python.org/3/library/tarfile.html#tarfile.TarFile>`_ class:

    .. sourcecode:: python

        import tarfile

        # when using read mode (decompression), the level_or_option argument
        # can only be a dict object, that represents decompression option. It
        # doesn't support int type compression level in this case.

        class ZstdTarFile(tarfile.TarFile):
            def __init__(self, name, mode='r', *, level_or_option=None, zstd_dict=None, **kwargs):
                self.zstd_file = ZstdFile(name, mode,
                                          level_or_option=level_or_option,
                                          zstd_dict=zstd_dict)
                try:
                    super().__init__(fileobj=self.zstd_file, mode=mode, **kwargs)
                except:
                    self.zstd_file.close()
                    raise

            def close(self):
                super().close()
                self.zstd_file.close()

        # write .tar.zst file (compression)
        with ZstdTarFile('archive.tar.zst', mode='w', level_or_option=5) as tar:
            # do something

        # read .tar.zst file (decompression)
        with ZstdTarFile('archive.tar.zst', mode='r') as tar:
            # do something


Zstd dictionary ID
>>>>>>>>>>>>>>>>>>

.. _dict_id:

.. note:: Zstd dictionary ID

    Dictionary ID is a 32-bit unsigned integer value. Decoder uses it to check if the correct dictionary is used.

    According to zstd dictionary format `specification <https://github.com/facebook/zstd/blob/release/doc/zstd_compression_format.md#dictionary-format>`_, if a dictionary is going to be distributed in public, the following ranges are reserved for future registrar and shall not be used:

        - low range: <= 32767
        - high range: >= 2^31

    Outside of these ranges, any value in (32767 < v < 2^31) can be used freely, even in public environment.

    In zstd frame header, the `Dictionary_ID <https://github.com/facebook/zstd/blob/release/doc/zstd_compression_format.md#dictionary_id>`_ field can be 0/1/2/4 bytes. If the value is small, this can save 2~3 bytes. Or don't write the ID by setting :py:attr:`CParameter.dictIDFlag` parameter.

    pyzstd module doesn't support specifying ID when training dictionary currently. If want to specify the ID, modify the dictionary content according to format specification, and take the corresponding risks.

    **Attention**

    In :py:class:`ZstdDict` class, :py:attr:`ZstdDict.dict_id` attribute == 0 means the dictionary is a "raw content" dictionary, free of any format restriction, used for advanced user. Non-zero means it's an ordinary dictionary, was created by zstd functions, follow the format specification.

    In :py:func:`get_frame_info` function, ``dictionary_id`` == 0 means dictionary ID was not recorded in frame header, the frame may or may not need a dictionary to be decoded, and the ID of such a dictionary is not specified.


Dynamically link to zstd library
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

.. _dynamic_link:

.. note:: Dynamically link to zstd library

    .. attention::

        This feature will be available in next release, pyzstd verion > 0.14.3.

    Pyzstd module supports dynamically linking to zstd library, the zstd source code in ``lib`` folder will be ignored.

        * No matter static or dynamic linking, pyzstd module requires zstd v1.4.0+.
        * Before zstd v1.5.0, ZSTD_MULTITHREAD macro is not defined by default. So :ref:`multi-threaded compression<mt_compression>` may not be used in system provided zstd library, in this case pyzstd module will perform single-threaded compression and issue a ``RuntimeWarning``.

    On Linux, dynamically link to zstd library provided by system:

    .. sourcecode:: shell

        # build pyzstd module and install
        python3 setup.py --dynamic-link-zstd install

    On Windows, there is no system-wide zstd library. Pyzstd module can dynamically link to a DLL library, modify ``setup.py``:

    .. sourcecode:: python

        if DYNAMIC_LINK:
            # E:\zstd_dll folder has zstd.h / zdict.h / libzstd.lib that
            # along with libzstd.dll
            include_dirs = ['E:\zstd_dll']  # .h directory
            library_dirs = ['E:\zstd_dll']  # .lib directory
            libraries = ['libzstd']         # lib name, not filename.

    And put ``libzstd.dll`` into one of these directories:

        * Python's root directory that has python.exe.
        * Directory added by `os.add_dll_directory() <https://docs.python.org/3/library/os.html#os.add_dll_directory>`_ function.
        * %SystemRoot%\System32

    Note that the above list doesn't include the current working directory and %PATH% directories.
