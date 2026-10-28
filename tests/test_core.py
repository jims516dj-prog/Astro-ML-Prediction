from datetime import datetime, timezone

import numpy as np
import pytest

from astrofoot import db, ephem, models
from astrofoot.dataset import devig
from astrofoot.engines import chokoisky, frawley, rao
from astrofoot.engines.common import View, within_after, within_before

UCL99 = ephem.raw_chart(ephem.jd_utc(datetime(1999, 5, 26, 18, 45, tzinfo=timezone.utc)), 41.3809, 2.1228)


def test_sun_position_known_date():
    # 26 May 1999: Sun at ~5 Gemini tropical
    v = View(UCL99, "tropical", "placidus")
    assert 64.5 < v.lon["Su"] < 65.5
    assert 180 < v.lon["Mo"] < 210        # waxing Moon in Libra, four days before full


def test_ayanamsha_and_sidereal_shift():
    assert 23.7 < UCL99["ayan_lahiri"] < 24.0
    vt, vs = View(UCL99, "tropical", "placidus"), View(UCL99, "lahiri", "placidus")
    assert abs(ephem.angdiff(vt.lon["Ma"] - vs.lon["Ma"], UCL99["ayan_lahiri"])) < 1e-9
    # quadrant cusps are points: occupancy is zodiac-independent
    assert all(vt.house(p) == vs.house(p) for p in vt.lon)


def test_antiscia_pairs():
    assert ephem.antiscion(10.0) == pytest.approx(170.0)      # 10 Aries -> 20 Virgo
    assert ephem.antiscion(45.0) == pytest.approx(135.0)      # 15 Taurus -> 15 Leo
    assert ephem.contra_antiscion(10.0) == pytest.approx(350.0)


def test_navamsha_and_kp():
    assert ephem.d9(0.0) == 0.0
    assert ephem.d9(3 + 1 / 3) == pytest.approx(30.0)         # second navamsha of Aries = Taurus
    star, sub = ephem.kp_sublord(0.1)
    assert star == "Ke" and sub == "Ke"                       # start of Ashwini


def test_cusp_predicates():
    assert within_before(28.0, 30.5 - 0.6, 3) is True         # same sign, 1.9 deg before
    assert within_before(29.0, 31.0, 3) is False              # different sign
    assert within_after(31.0, 30.0, 3) is True


def test_devig_and_rps():
    p = devig(np.array([[2.0, 3.4, 3.8]]))[0]
    assert p.sum() == pytest.approx(1.0)
    assert p[0] > p[2] > 0
    P = np.array([[1.0, 0, 0], [0.5, 0.3, 0.2]])
    y = np.array([0, 2])
    assert models.rps(P, y)[0] == 0
    assert models.rps(P, y)[1] == pytest.approx(0.5 * (0.5 ** 2 + 0.8 ** 2))


def test_offset_softmax_recovers_coefficient():
    rng = np.random.default_rng(1)
    n = 40000
    x = rng.normal(size=(n, 3))
    lp = np.log(np.tile([0.45, 0.27, 0.28], (n, 1)))
    eta = 0.3 * x[:, 0]
    logits = lp + np.column_stack([eta, 0 * eta, -eta])
    P = np.exp(logits); P /= P.sum(1, keepdims=True)
    y = (rng.random(n)[:, None] > np.cumsum(P, 1)).sum(1)
    m = models.OffsetSoftmax(l1=0.002, l2=0).fit(x, y, lp)
    assert m.w[0] == pytest.approx(0.3, abs=0.05)
    assert abs(m.w[1]) < 0.03 and abs(m.w[2]) < 0.03
    u = models.univariate(x[:, 0], y, lp)
    assert u["beta"] == pytest.approx(0.3, abs=0.05) and u["p"] < 1e-6


def test_multiple_comparison_helpers():
    p = np.array([0.001, 0.01, 0.04, 0.5])
    assert (models.holm(p) >= p).all()
    q = models.bh_qvalues(p)
    assert (q >= p).all() and q[-1] == pytest.approx(0.5)


def test_engines_run_and_are_deterministic():
    a = frawley.analyse(UCL99, draw_possible=False).to_dict()
    b = frawley.analyse(UCL99, draw_possible=False).to_dict()
    assert a == b
    c = chokoisky.analyse(UCL99, "Manchester United", "Bayern", draw_possible=False)
    assert c.winner in ("fav", "dog")
    r = rao.analyse(UCL99, draw_possible=False)
    assert len(r.table) == 7 and r.caveats


def test_frawley_equal_odds_disables():
    assert frawley.analyse(UCL99, equal_odds=True).winner == "disabled"


def test_rao_planetary_influence_layer():
    r = rao.analyse(UCL99, draw_possible=False, when=datetime(1999, 5, 26),
                    captain={"fav_jersey": 7, "dog_jersey": 8, "fav_color": "red", "dog_color": "grey"})
    assert r.features["influence_included"] is True


def test_ledger_hash_and_audit(tmp_path):
    con = db.connect(tmp_path / "t.sqlite3")
    mid = db.insert_match(con, {"team_a": "A", "team_b": "B", "kickoff_utc": "2099-01-01T15:00:00+00:00"})
    row = db.commit_prediction(con, mid, "engine4", "v1", {"p_fav": 0.5}, "2099-01-01T15:00:00+00:00")
    assert row["committed_before_kickoff"] == 1 and len(row["sha256"]) == 64
    changed = db.update_match(con, mid, {"score_a": 2, "score_b": 1, "status": "completed"})
    assert changed == {"score_a", "score_b", "status"}
    assert len(db.audit_trail(con, mid)) == 3


def test_unseen_configuration_cannot_explode_predictions():
    # A slow-planet aspect that never formed in training but forms in the test season
    # (found when a placebo sky produced a 100%/0%/0% forecast).
    rng = np.random.default_rng(0)
    n = 5000
    x_tr = np.column_stack([rng.normal(size=n), np.full(n, 1e-30)])
    lp = np.log(np.tile([0.45, 0.27, 0.28], (n, 1)))
    y = rng.integers(0, 3, n)
    m = models.OffsetSoftmax(l1=0.0, l2=1e-2).fit(x_tr, y, lp)
    x_te = np.array([[0.0, 1.0]])
    assert np.abs(m._prep(x_te)).max() <= models.Z_CLIP   # was ~5e5 before SD_FLOOR / Z_CLIP
    assert np.isfinite(m.predict(x_te, lp[:1])).all()


def test_screening_ignores_barely_seen_primitives():
    rng = np.random.default_rng(0)
    n = 5000
    X = np.column_stack([rng.normal(size=n), (rng.random(n) < 0.01).astype(float)])  # 2nd: ~50 active rows
    lp = np.log(np.tile([0.45, 0.27, 0.28], (n, 1)))
    y = rng.integers(0, 3, n)
    assert models.score_vector(X, y, lp)[1] == 0.0
