"""Real disk/tar tests with a synthetic ten-reference OCI store."""
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from oci_transport import SERVICES, digest, verify
from oci_envelope import pack, unpack


def raw(doc):
    return json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / 'source'
        self.root.mkdir()
        store = self.root / 'blobs'
        store.mkdir()
        cfg = raw({'os':'linux','architecture':'amd64'})
        layer = b'synthetic OCI layer bytes'
        c, l = digest(cfg), digest(layer)
        manifest = raw({'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json',
                        'config':{'mediaType':'application/vnd.oci.image.config.v1+json','digest':c,'size':len(cfg)},
                        'layers':[{'mediaType':'application/vnd.oci.image.layer.v1.tar+gzip','digest':l,'size':len(layer)}]})
        m = digest(manifest)
        for blob in (cfg, layer, manifest):
            (store / digest(blob)[7:]).write_bytes(blob)
        bom = {'schema_version':1,'classification':'DISPOSABLE_POC_E17_IMAGE_BOM','source_sha':'a'*40,'production_authorized':False,
               'images':{s:{'reference':'127.0.0.1:15080/aiops-v3/'+s+'@'+m,'manifest_digest':m,'config_digest':c,'engine_image_id':c,'os':'linux','architecture':'amd64'} for s in SERVICES}}
        self.bom = raw(bom)
        (self.root/'image-bom.json').write_bytes(self.bom)
        self.expected = digest(self.bom)
        self.archive = self.tmp/'envelope.tar'
        self.destination = self.tmp/'dest'
        self.layer_name = 'blobs/'+l[7:]

    def unpack(self, archive_sha=None):
        return unpack(self.archive,self.destination,archive_sha or digest(self.archive.read_bytes()),self.expected)

    def mutate(self, name=None, kind=tarfile.REGTYPE, data=b'bad', drop=None, replace=None):
        with tarfile.open(self.archive,'w',format=tarfile.USTAR_FORMAT) as t:
            for p in [self.root/'image-bom.json', *sorted((self.root/'blobs').iterdir())]:
                n=p.relative_to(self.root).as_posix()
                if n==drop: continue
                b=data if n==replace else p.read_bytes()
                member=tarfile.TarInfo(n); member.size=len(b)
                t.addfile(member,io.BytesIO(b))
            if name is not None:
                member=tarfile.TarInfo(name); member.type=kind
                if kind==tarfile.REGTYPE:
                    member.size=len(data); t.addfile(member,io.BytesIO(data))
                else:
                    member.linkname='/tmp/outside'; t.addfile(member)

    def rejected(self):
        with self.assertRaises((ValueError,tarfile.TarError)): self.unpack()
        self.assertFalse(self.destination.exists())

    def test_roundtrip_deterministic(self):
        a=pack(self.root,self.archive,self.expected)
        b=pack(self.root,self.tmp/'second.tar',self.expected)
        self.assertEqual(a,b); self.assertEqual(self.unpack(),a)
        self.assertEqual(verify(self.destination,self.expected)['blobs'],3)
        self.assertEqual(stat.S_IMODE(self.archive.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE((self.destination/'image-bom.json').stat().st_mode),0o600)
    def test_wrong_archive_hash(self):
        pack(self.root,self.archive,self.expected)
        with self.assertRaises(ValueError): self.unpack('sha256:'+'0'*64)
        self.assertFalse(self.destination.exists())
    def test_traversal(self):
        self.mutate(name='../outside'); self.rejected(); self.assertFalse((self.tmp/'outside').exists())
    def test_absolute(self):
        self.mutate(name='/tmp/never-write-here'); self.rejected()
    def test_duplicate(self):
        self.mutate(name='image-bom.json',data=self.bom); self.rejected()
    def test_symlink(self):
        self.mutate(name='blobs/'+'f'*64,kind=tarfile.SYMTYPE); self.rejected()
    def test_hardlink(self):
        self.mutate(name='blobs/'+'f'*64,kind=tarfile.LNKTYPE); self.rejected()
    def test_missing_blob(self):
        self.mutate(drop=self.layer_name); self.rejected()
    def test_tampered_blob(self):
        self.mutate(replace=self.layer_name); self.rejected()
    def test_extra_valid_blob(self):
        self.mutate(name='blobs/'+digest(b'bad')[7:]); self.rejected()
    def test_no_overwrite(self):
        pack(self.root,self.archive,self.expected); before=self.archive.read_bytes()
        with self.assertRaises(FileExistsError): pack(self.root,self.archive,self.expected)
        self.assertEqual(self.archive.read_bytes(),before)
        self.destination.mkdir(); marker=self.destination/'marker'; marker.write_text('keep')
        with self.assertRaises(FileExistsError): self.unpack()
        self.assertEqual(marker.read_text(),'keep')
    def test_corrupted_source(self):
        (self.root/self.layer_name).write_bytes(b'wrong')
        with self.assertRaises(ValueError): pack(self.root,self.archive,self.expected)
        self.assertFalse(self.archive.exists())

if __name__=='__main__': unittest.main()
