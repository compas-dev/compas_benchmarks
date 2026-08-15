"""Content hashing for COMPAS data objects.

The benchmarks need a hash that answers "is this the same object after a round trip?"
without being coupled to the guid or to the wire format. :meth:`compas.data.Data.sha256`
is not that hash: it digests the full JSON text of the object, guid included, so two
equal objects hash differently and a protobuf round trip cannot be compared to a JSON one.

:func:`canonical_hash` provides the format-independent alternative, implemented here
rather than in COMPAS core so the benchmarks run against unmodified released versions.
"""

import hashlib
import json


def canonical_hash(obj, as_string=False):
    """Compute a content hash of a data object, independent of guid, name, and serialization format.

    Two objects with the same type and data produce the same hash regardless of their
    guid/name, and regardless of which format (JSON, protobuf, ...) they were loaded from,
    because every format reconstructs the same ``__data__``.

    Parameters
    ----------
    obj : :class:`compas.data.Data`
        The object to hash.
    as_string : bool, optional
        If True, return the digest in hexadecimal format rather than as bytes.

    Returns
    -------
    bytes | str

    Notes
    -----
    The canonical form is a UTF-8 JSON encoding of ``{"dtype", "data"}`` with sorted keys
    and no insignificant whitespace, produced with the guid excluded from this object and
    from any nested :class:`compas.data.Data` objects. This makes the hash suitable for
    content-addressed change detection and version control, independent of the wire format.

    Examples
    --------
    >>> from compas.geometry import Point
    >>> a = Point(0, 0, 0)
    >>> b = Point(0, 0, 0)
    >>> a.guid == b.guid
    False
    >>> canonical_hash(a) == canonical_hash(b)
    True

    """
    from compas.data import DataEncoder

    previous = DataEncoder.minimal
    DataEncoder.minimal = True
    try:
        canonical = json.dumps(
            obj.__jsondump__(minimal=True),
            cls=DataEncoder,
            sort_keys=True,
            separators=(",", ":"),
        )
    finally:
        DataEncoder.minimal = previous

    h = hashlib.sha256()
    h.update(canonical.encode())
    if as_string:
        return h.hexdigest()
    return h.digest()
