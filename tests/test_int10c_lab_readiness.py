import pytest
from int10c_lab_readiness import validate_plan

C="a"*40
B="b"*40
RUN="ci-0123456789ab"

def plan():
    return dict(c_sha=C,b_sha=B,run_id=RUN,postgres_image="sha256:"+"c"*64,
                temporal_image="sha256:"+"d"*64,worker_image="sha256:"+"e"*64,
                database=RUN.replace("-","_"),queue=RUN+"-queue",
                workflow=RUN+"-workflow",directory="/tmp/"+RUN,
                synthetic_only=True,external_egress=False,external_credentials=False,
                timeout_seconds=300)

def test_plan_never_authorizes_launch():
    assert validate_plan(plan(),expected_c_sha=C,expected_b_sha=B)=={
        "status":"PLAN_ONLY","launch_authorized":False,
        "runtime_attested":False,"ownership":"UNKNOWN"}

@pytest.mark.parametrize("change",[
    {"c_sha":"f"*40},{"b_sha":"f"*40},{"run_id":"production"},
    {"postgres_image":"postgres:16"},{"temporal_image":"latest"},
    {"worker_image":"latest"},{"database":"aiops"},{"queue":"shared"},
    {"workflow":"existing"},{"directory":"/tmp/../etc"},
    {"synthetic_only":False},{"external_egress":True},
    {"external_credentials":True},{"timeout_seconds":901},
    {"timeout_seconds":True},{"authorization":True},
])
def test_plan_refuses_unsafe_declaration(change):
    with pytest.raises(ValueError):
        validate_plan(dict(plan(),**change),expected_c_sha=C,expected_b_sha=B)
