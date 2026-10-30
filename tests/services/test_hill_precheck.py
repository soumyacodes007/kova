from types import SimpleNamespace as NS
import pytest
from cadrecover.validator.hill.precheck import precheck_model, PrecheckError, MAX_WEIGHT_BYTES
from cadrecover.storage import db
from cadrecover.protocol.hill import Model

REV="a"*40

def api(files=None, **kw):
    info=NS(sha=REV,private=False,gated=False, siblings=files if files is not None else [
        NS(rfilename="config.json",size=1,lfs=None),
        NS(rfilename="model.safetensors",size=100,lfs=NS(sha256="b"*64,size=100))],**kw)
    return NS(model_info=lambda repo,revision,files_metadata:info)

def test_success_no_download_and_order_independent():
    a=api()
    result=precheck_model("o/m",REV,api=a)
    a.model_info("o/m",REV,True).siblings.reverse()
    assert precheck_model("o/m",REV,api=a) == result
    assert result.weight_bytes == 100

def test_branch_revision_never_queries():
    with pytest.raises(PrecheckError,match="40-hex"):
        precheck_model("o/m","main",api=NS())

@pytest.mark.parametrize("files,message",[
 ([NS(rfilename="adapter_config.json"),NS(rfilename="adapter_model.safetensors")],"adapter-only"),
 ([NS(rfilename="config.json")],"missing full"),
 ([NS(rfilename="model.safetensors",size=20,lfs=NS(sha256="b"*64))],"config.json"),
 ([NS(rfilename="config.json"),NS(rfilename="model.safetensors",size=MAX_WEIGHT_BYTES+1,lfs=NS(sha256="b"*64))],"exceed"),
 ([NS(rfilename="config.json"),NS(rfilename="model.safetensors",size=2,lfs=None)],"metadata"),
])
def test_rejections(files,message):
    with pytest.raises(PrecheckError,match=message):
        precheck_model("o/m",REV,api=api(files))

def test_duplicate_rejected(tmp_path):
    con=db.connect(tmp_path/"t.db")
    first=precheck_model("o/m",REV,api=api())
    db.save_model(con,Model(fingerprint=first.fingerprint,name="first",source="miner",
                           submitted_at="now",status="queued"))
    with pytest.raises(PrecheckError,match="same weights as first, committed later"):
        precheck_model("o/renamed",REV,con,api=api())

@pytest.mark.parametrize("field,value",[("private",True),("gated","auto"),("sha","c"*40)])
def test_public_and_resolved_commit(field,value):
    a=api()
    setattr(a.model_info("o/m",REV,True),field,value)
    with pytest.raises(PrecheckError):
        precheck_model("o/m",REV,api=a)
