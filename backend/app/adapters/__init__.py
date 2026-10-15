"""适配器包入口。"""
from .base import SourceAdapter
from .registry import AdapterRegistry, registry

__all__ = ["SourceAdapter", "AdapterRegistry", "registry"]
