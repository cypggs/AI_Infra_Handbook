"""Storage systems mini demo package."""

__version__ = "0.1.0"

from .block import BlockDevice
from .inode_fs import InodeFS
from .object_store import ObjectStore
from .erasure_coding import SimpleXORCodec
from .tiered_cache import TieredCache
from .checkpoint import CheckpointManager

__all__ = [
    "BlockDevice",
    "InodeFS",
    "ObjectStore",
    "SimpleXORCodec",
    "TieredCache",
    "CheckpointManager",
]
