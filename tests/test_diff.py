from apx_curve_watch.diff import diff_snapshots


def test_no_change_is_empty():
    ladders = {"SOHO_BESS1": [[100.0, 20.0], [200.0, 50.0]]}
    assert diff_snapshots(ladders, ladders) == []


def test_price_move_is_flagged_even_if_tiny():
    old = {"SOHO_BESS1": [[100.0, 20.0]]}
    new = {"SOHO_BESS1": [[100.0, 20.0001]]}
    diffs = diff_snapshots(old, new)
    assert len(diffs) == 1
    [seg] = diffs[0].segments
    assert seg.kind == "moved"
    assert seg.before == [100.0, 20.0]
    assert seg.after == [100.0, 20.0001]


def test_extra_segment_is_added_not_moved():
    old = {"SOHO_BESS1": [[100.0, 20.0]]}
    new = {"SOHO_BESS1": [[100.0, 20.0], [200.0, 50.0]]}
    diffs = diff_snapshots(old, new)
    [seg] = diffs[0].segments
    assert seg.kind == "added"
    assert seg.before is None
    assert seg.after == [200.0, 50.0]


def test_dropped_segment():
    old = {"SOHO_BESS1": [[100.0, 20.0], [200.0, 50.0]]}
    new = {"SOHO_BESS1": [[100.0, 20.0]]}
    diffs = diff_snapshots(old, new)
    [seg] = diffs[0].segments
    assert seg.kind == "dropped"
    assert seg.before == [200.0, 50.0]
    assert seg.after is None


def test_new_resource_is_all_added_segments():
    old: dict = {}
    new = {"RR_BESS1": [[50.0, 30.0]]}
    diffs = diff_snapshots(old, new)
    assert diffs[0].resource == "RR_BESS1"
    assert all(seg.kind == "added" for seg in diffs[0].segments)


def test_resource_dropping_out_entirely():
    old = {"RR_BESS1": [[50.0, 30.0]]}
    new: dict = {}
    diffs = diff_snapshots(old, new)
    assert diffs[0].resource == "RR_BESS1"
    assert all(seg.kind == "dropped" for seg in diffs[0].segments)


def test_unrelated_resource_untouched():
    old = {"SOHO_BESS1": [[100.0, 20.0]], "RR_BESS1": [[50.0, 30.0]]}
    new = {"SOHO_BESS1": [[100.0, 20.0]], "RR_BESS1": [[60.0, 30.0]]}
    diffs = diff_snapshots(old, new)
    assert [d.resource for d in diffs] == ["RR_BESS1"]
