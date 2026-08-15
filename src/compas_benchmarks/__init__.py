"""Benchmarks for the COMPAS core ecosystem.

Each benchmark suite lives in its own subpackage and is runnable as a module, e.g.::

    python -m compas_benchmarks.serialization.run

"""

from .hashing import canonical_hash

__author__ = "Gonzalo Casas"
__copyright__ = "ETH Zurich"
__license__ = "MIT License"
__version__ = "0.1.0"

__all__ = ["canonical_hash"]
