import hashlib
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import verify_proactive_image_archive as verifier


def make_archive(tmp_path):
    source="a"*40
    tag=f"aiops2-portal-qualification:{source}"
    config=json.dumps({"config":{"Labels":{"org.opencontainers.image.revision":source}}},separators=(",",":")).encode()
    config_digest=hashlib.sha256(config).hexdigest()
    image_manifest=json.dumps({"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json","config":{"digest":"sha256:"+config_digest},"layers":[]},separators=(",",":")).encode()
    manifest_digest=hashlib.sha256(image_manifest).hexdigest()
    index_blob=json.dumps({"schemaVersion":2,"manifests":[{"digest":"sha256:"+manifest_digest}]},separators=(",",":")).encode()
    index_digest=hashlib.sha256(index_blob).hexdigest()
    index=json.dumps({"schemaVersion":2,"manifests":[{"digest":"sha256:"+index_digest}]},separators=(",",":")).encode()
    manifest=json.dumps([{"Config":f"blobs/sha256/{config_digest}","RepoTags":[tag],"Layers":[]}]).encode()
    archive_path=tmp_path/"image.tar"
    with tarfile.open(archive_path,"w") as tar:
        for name,data in [
            ("manifest.json",manifest),
            ("index.json",index),
            (f"blobs/sha256/{config_digest}",config),
            (f"blobs/sha256/{manifest_digest}",image_manifest),
            (f"blobs/sha256/{index_digest}",index_blob),
        ]:
            info=tarfile.TarInfo(name)
            info.size=len(data)
            tar.addfile(info,__import__("io").BytesIO(data))
    receipt_path=tmp_path/"receipt.json"
    receipt_path.write_text(json.dumps({
        "source_sha":source,
        "docker_engine_inspect_id":"sha256:"+manifest_digest,
        "buildx_iid":"sha256:"+index_digest,
        "state":"BUILD_PASS",
        "deploy_authorized":False,
    }))
    return archive_path,receipt_path,source,tag,"sha256:"+config_digest,"sha256:"+index_digest,"sha256:"+manifest_digest


def test_archive_verifier_binds_receipt_to_config_and_index(tmp_path):
    archive,receipt,source,tag,config_id,index_id,manifest_id=make_archive(tmp_path)
    result=verifier.verify(archive,receipt,source,tag,manifest_id)
    assert result["local_image_id"]==config_id
    assert result["docker_config_digest"]==config_id
    assert result["oci_index_digest"]==index_id
    assert result["docker_engine_inspect_id"]==manifest_id
    assert result["oci_manifest_digest"]==manifest_id


def test_archive_verifier_rejects_wrong_inspect_id(tmp_path):
    archive,receipt,source,tag,config_id,index_id,manifest_id=make_archive(tmp_path)
    with pytest.raises(ValueError,match="platform manifest"):
        verifier.verify(archive,receipt,source,tag,"sha256:"+"f"*64)


def test_archive_verifier_rejects_wrong_revision_label(tmp_path):
    archive,receipt,source,tag,config_id,index_id,manifest_id=make_archive(tmp_path)
    with tarfile.open(archive,"r") as tar:
        members={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    config_path=next(k for k in members if k.startswith("blobs/sha256/") and hashlib.sha256(members[k]).hexdigest()==k.split("/")[-1])
    config=json.loads(members[config_path])
    config["config"]["Labels"]["org.opencontainers.image.revision"]="b"*40
    changed=json.dumps(config,separators=(",",":")).encode()
    new_digest=hashlib.sha256(changed).hexdigest()
    members.pop(config_path)
    members[f"blobs/sha256/{new_digest}"]=changed
    manifest=json.loads(members["manifest.json"])
    manifest[0]["Config"]=f"blobs/sha256/{new_digest}"
    members["manifest.json"]=json.dumps(manifest).encode()
    with tarfile.open(archive,"w") as tar:
        for name,data in members.items():
            info=tarfile.TarInfo(name)
            info.size=len(data)
            tar.addfile(info,__import__("io").BytesIO(data))
    with pytest.raises(ValueError,match="revision label"):
        verifier.verify(archive,receipt,source,tag,config_id)
