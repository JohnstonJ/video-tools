from typing import BinaryIO


def read_file_bytes(file: BinaryIO, chunk_size: int) -> bytearray:
    """Read exactly chunk_size bytes or until EOF"""

    rv = bytearray([])
    while len(rv) < chunk_size:
        remaining = chunk_size - len(rv)
        next_read = file.read(remaining)
        if len(next_read) == 0:
            return rv
        rv += next_read

    return bytearray(rv)
