"""In-memory inode-based file system simulator."""

import time
from typing import Dict, List, Optional

from .block import BlockDevice


class InodeFS:
    """A simplified inode-based file system on top of a BlockDevice.

    Each inode holds direct block pointers, a size, and simple metadata.
    Directories are flat maps from filename to inode number.
    """

    def __init__(self, block_device: BlockDevice):
        self.bd = block_device
        self._inodes: Dict[int, dict] = {}
        self._dir: Dict[str, int] = {}
        self._next_ino = 1

    def create(self, name: str, size: int = 0) -> int:
        """Create a file and return its inode number."""
        if name in self._dir:
            raise FileExistsError(f"file '{name}' already exists")
        ino = self._next_ino
        self._next_ino += 1
        self._inodes[ino] = {
            "ino": ino,
            "size": 0,
            "blocks": [],
            "ctime": time.time(),
        }
        self._dir[name] = ino
        if size > 0:
            self.write(name, b"\x00" * size)
        return ino

    def write(self, name: str, data: bytes) -> int:
        """Write data to a file, allocating new blocks as needed."""
        ino = self._lookup(name)
        inode = self._inodes[ino]
        blocks_needed = (len(data) + self.bd.block_size - 1) // self.bd.block_size
        current = len(inode["blocks"])

        for _ in range(blocks_needed - current):
            inode["blocks"].append(self.bd.allocate())

        for i, bid in enumerate(inode["blocks"][:blocks_needed]):
            chunk = data[i * self.bd.block_size : (i + 1) * self.bd.block_size]
            self.bd.write_block(bid, chunk)

        inode["size"] = len(data)
        return len(data)

    def read(self, name: str, size: Optional[int] = None) -> bytes:
        """Read up to `size` bytes from a file."""
        ino = self._lookup(name)
        inode = self._inodes[ino]
        if size is None or size > inode["size"]:
            size = inode["size"]
        out = b""
        for i, bid in enumerate(inode["blocks"]):
            chunk = self.bd.read_block(bid)
            start = i * self.bd.block_size
            end = start + self.bd.block_size
            if start >= size:
                break
            if end > size:
                chunk = chunk[: size - start]
            out += chunk
        return out[:size]

    def delete(self, name: str) -> None:
        """Delete a file and free its blocks."""
        ino = self._lookup(name)
        inode = self._inodes.pop(ino)
        for bid in inode["blocks"]:
            self.bd.free(bid)
        del self._dir[name]

    def listdir(self) -> List[str]:
        return list(self._dir.keys())

    def stat(self, name: str) -> dict:
        ino = self._lookup(name)
        inode = self._inodes[ino].copy()
        inode["blocks"] = list(inode["blocks"])
        return inode

    def _lookup(self, name: str) -> int:
        if name not in self._dir:
            raise FileNotFoundError(f"file '{name}' not found")
        return self._dir[name]
