from apps.surveys import scoring


def test_nps():
    r = scoring.nps([10, 9, 8, 7, 6, 0])
    assert (r["promoters"], r["passives"], r["detractors"]) == (2, 2, 2)
    assert r["score"] == 0
    assert scoring.nps([10, 10])["score"] == 100
    assert scoring.nps([0, 3])["score"] == -100
    assert scoring.nps([]) is None


def test_csat_ces_average():
    assert scoring.csat([5, 4, 3, 1])["score"] == 50
    assert scoring.csat([5, 4, 3, 1])["average"] == 3.25
    ces = scoring.ces([7, 5, 2, 1])
    assert ces["score"] == 3.8 and ces["easy_pct"] == 50
    assert scoring.average([4, 5])["score"] == 4.5
