#!/usr/bin/env python3
"""Bind the build receipt to the exact Docker config exported in docker save."""
import hashlib
import json
import re
import sys
import tarfile
import tempfile
from pathlib import Path


def read_member(archive, name):
    member=archive.getmember(name)
    stream=archive.extractfile(member)
    if stream is None:
        raise ValueError(f"archive member is not a file: {name}")
    return stream.read()


def digest(data):
    return "sha256:"+hashlib.sha256(data).hexdigest()


def verify(archive_path, receipt_path, source_sha, expected_tag, inspect_id):
    if not re.fullmatch(r"[0-9a-f]{40}",source_sha):
        raise ValueError("invalid source SHA")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}",inspect_id):
        raise ValueError("invalid docker image inspect ID")
    with tarfile.open(archive_path,"r:*") as archive:
        manifests=json.loads(read_member(archive,"manifest.json"))
        if not isinstance(manifests,list) or len(manifests)!=1:
            raise ValueError("expected exactly one Docker image manifest")
        manifest=manifests[0]
        if expected_tag not in manifest.get("RepoTags",[]):
            raise ValueError("Docker archive tag mismatch")
        config_path=manifest.get("Config","")
        match=re.fullmatch(r"blobs/sha256/([0-9a-f]{64})",config_path)
        if not match:
            raise ValueError("invalid Docker config path")
        config_bytes=read_member(archive,config_path)
        config_digest=digest(config_bytes)
        if config_digest!="sha256:"+match.group(1):
            raise ValueError("Docker config bytes do not match manifest digest")
        config=json.loads(config_bytes)
        labels=config.get("config",{}).get("Labels",{})
        if labels.get("org.opencontainers.image.revision")!=source_sha:
            raise ValueError("OCI revision label does not match frozen source SHA")
        if inspect_id!=config_digest:
            raise ValueError("docker image inspect ID does not match exported config digest")

        index_digest=None
        try:
            index=json.loads(read_member(archive,"index.json"))
        except KeyError:
            index=None
        if index is not None:
            descriptors=index.get("manifests",[])
            if not isinstance(descriptors,list) or len(descriptors)!=1:
                raise ValueError("expected exactly one OCI index descriptor")
            descriptor=descriptors[0]
            index_match=re.fullmatch(r"sha256:([0-9a-f]{64})",descriptor.get("digest",""))
            if not index_match:
                raise ValueError("invalid OCI index descriptor digest")
            index_path="blobs/sha256/"+index_match.group(1)
            index_bytes=read_member(archive,index_path)
            index_digest=digest(index_bytes)
            if index_digest!=descriptor["digest"]:
                raise ValueError("OCI index descriptor bytes do not match digest")

    receipt_path=Path(receipt_path)
    receipt=json.loads(receipt_path.read_text())
    if receipt.get("source_sha")!=source_sha or receipt.get("state")!="BUILD_PASS":
        raise ValueError("build receipt source/state mismatch")
    buildx_iid=receipt.get("buildx_iid")
    if index_digest and buildx_iid!=index_digest:
        raise ValueError("Buildx IID does not match OCI index digest")
    if receipt.get("local_image_id")!=inspect_id:
        raise ValueError("receipt local_image_id does not match docker image inspect ID")
    receipt["local_image_id"]=config_digest
    receipt["docker_config_digest"]=config_digest
    receipt["docker_image_inspect_id"]=inspect_id
    receipt["oci_index_digest"]=index_digest
    receipt["image_tag"]=expected_tag
    tmp=receipt_path.with_suffix(receipt_path.suffix+".tmp")
    tmp.write_text(json.dumps(receipt,sort_keys=True)+"\n")
    tmp.replace(receipt_path)
    return receipt


if __name__=="__main__":
    if len(sys.argv)!=6:
        raise SystemExit("usage: verify_proactive_image_archive.py TAR RECEIPT SOURCE_SHA TAG DOCKER_INSPECT_ID")
    result=verify(*sys.argv[1:])
    print(json.dumps(result,sort_keys=True))
