"""Transport failures must be rejected before mathematical verification."""
import hashlib
import io
import lzma
import struct
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from certificate_io import FILES, sha256, unpack_xz


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = {name: (name + "\n").encode() for name in FILES}

    def archive(self, extra=None, omit=None):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tar:
            for name, data in self.data.items():
                if name == omit:
                    continue
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if extra:
                tar.addfile(extra, io.BytesIO(b""))
        path = self.root / "bundle.tar.xz"
        path.write_bytes(lzma.compress(stream.getvalue()))
        return path, dict(direction="upper", archive_sha256=sha256(path), members={
            n: dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for n, b in self.data.items()})

    def test_exact_contents_and_lower_roundtrip(self):
        path, entry = self.archive()
        dest = self.root / "expanded"
        dest.mkdir()
        unpack_xz(path, entry, dest)
        self.assertEqual({p.name: p.read_bytes() for p in dest.iterdir()}, self.data)
        raw = b'{"certificate": "example"}\n'
        path.write_bytes(lzma.compress(raw))
        lower = dict(direction="lower", archive_sha256=sha256(path), members={
            "lower.json": dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())})
        unpack_xz(path, lower, dest)
        self.assertEqual((dest / "lower.json").read_bytes(), raw)

    def test_unexpected_paths_duplicates_and_links(self):
        for name, kind in [("../escape", tarfile.REGTYPE), ("sp.jsonl", tarfile.REGTYPE),
                           ("elsewhere", tarfile.SYMTYPE), ("/absolute", tarfile.REGTYPE)]:
            with self.subTest(name=name):
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = "sp.jsonl" if kind == tarfile.SYMTYPE else ""
                path, entry = self.archive(extra=info)
                with self.assertRaises(ValueError):
                    unpack_xz(path, entry)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_missing_member(self):
        path, entry = self.archive(omit="sp.jsonl")
        with self.assertRaises(ValueError):
            unpack_xz(path, entry)

    def test_recorded_size_and_hash_enforced(self):
        for field, bad in [("bytes", 1), ("sha256", "0" * 64)]:
            path, entry = self.archive()
            entry["members"]["sp.jsonl"][field] = bad
            with self.assertRaises(ValueError):
                unpack_xz(path, entry)

    def test_archive_identity_enforced(self):
        path, entry = self.archive()
        entry["archive_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            unpack_xz(path, entry)

    def test_truncated_xz_footer(self):
        path, entry = self.archive()
        path.write_bytes(path.read_bytes()[:-8])
        entry["archive_sha256"] = sha256(path)
        with self.assertRaises(ValueError):
            unpack_xz(path, entry)

    def test_decoder_rejects_dictionary_above_memory_limit(self):
        path, entry = self.archive()
        data = bytearray(path.read_bytes())
        # This fixture has one LZMA2 filter and no optional block size fields.
        # Change only its declared dictionary to 4 GiB, then repair header CRC.
        start = 12
        size = (data[start] + 1) * 4
        self.assertEqual(data[start + 1:start + 4], bytes([0, 0x21, 1]))
        data[start + 4] = 40
        crc = zlib.crc32(data[start:start + size - 4])
        data[start + size - 4:start + size] = struct.pack("<I", crc)
        path.write_bytes(data)
        entry["archive_sha256"] = sha256(path)
        with self.assertRaises((ValueError, tarfile.TarError)):
            unpack_xz(path, entry)


if __name__ == "__main__":
    unittest.main()
