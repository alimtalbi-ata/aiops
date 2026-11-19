import pytest
from portal.mission_data.graph import dependencies

def test_graph():
    nodes = [{"node_id": n} for n in "abcd"]
    edges = [{"source_id": a, "target_id": b} for a,b in ("ab","bc","ca","ac","cd")]
    assert dependencies(nodes, edges, "a")["affected"] == [
        {"node_id":"a","depth":0},{"node_id":"b","depth":1},
        {"node_id":"c","depth":1},{"node_id":"d","depth":2}]
    assert dependencies(nodes, edges, "d", direction="incoming", max_depth=1)["affected"] == [
        {"node_id":"d","depth":0},{"node_id":"c","depth":1}]
    with pytest.raises(ValueError):
        dependencies(nodes, edges, "missing")
    with pytest.raises(ValueError):
        dependencies(nodes, edges + [{"source_id":"a","target_id":"x"}], "a")
