import compas
from compas.geometry import Point

from compas_benchmarks import canonical_hash


def test_canonical_hash_is_guid_independent():
    a = Point(1, 2, 3)
    b = Point(1, 2, 3)
    assert a.guid != b.guid
    assert canonical_hash(a) == canonical_hash(b)
    # sha256 is coupled to the guid, so it differs for these two
    assert a.sha256() != b.sha256()


def test_canonical_hash_is_content_sensitive():
    assert canonical_hash(Point(1, 2, 3)) != canonical_hash(Point(1, 2, 4))


def test_canonical_hash_is_stable_and_string_form():
    p = Point(1, 2, 3)
    assert canonical_hash(p) == canonical_hash(p)
    assert canonical_hash(p, as_string=True) == canonical_hash(p, as_string=True)
    assert isinstance(canonical_hash(p, as_string=True), str)
    assert isinstance(canonical_hash(p), bytes)


def test_canonical_hash_survives_json_roundtrip():
    p = Point(1, 2, 3)
    q = compas.json_loads(compas.json_dumps(p))
    assert canonical_hash(q) == canonical_hash(p)
