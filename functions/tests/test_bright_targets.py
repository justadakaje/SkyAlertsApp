"""Unit tests for bright transient, comet, NEO, variable, and photometry helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from skyalerts_ingest.normalize import DetectionRow

from skyalerts_functions.bright_targets import (
    evergreen_variable_targets,
    parse_bright_supernovae_html,
    parse_cad_response,
    parse_mpc_comets,
    parse_sexagesimal_dec,
    parse_sexagesimal_ra,
)
from skyalerts_functions.firestore_store import compute_latest_photometry


def test_sexagesimal_conversion() -> None:
    ra = parse_sexagesimal_ra("06:00:00.000")
    assert ra == 90.0
    dec_neg = parse_sexagesimal_dec("-00:30:00.00")
    assert dec_neg == -0.5
    dec_pos = parse_sexagesimal_dec("+45:15:00.00")
    assert dec_pos == 45.25
    assert parse_sexagesimal_ra("25:00:00") is None
    assert parse_sexagesimal_dec("-95:00:00") is None


def test_parse_bright_supernovae_html() -> None:
    sample = """
    <table>
      <tr>
        <td><a href="../supernova.html#2026ahvu">2026ahvu</a></td>
        <td>NGC 1433</td>
        <td>03:41:55.511</td>
        <td>-47:13:39.39</td>
        <td>60.7E 20.6S</td>
        <td>12.3</td>
        <td>2026/11/10</td>
        <td>Ia</td>
        <td>0.003589</td>
        <td>12.3</td>
        <td>2026/11/10</td>
        <td>2026/11/02</td>
        <td>ATLAS</td>
        <td>ATLAS26ncp, GOTO26ltt</td>
      </tr>
      <tr>
        <td>2026faint</td>
        <td>Anon</td>
        <td>12:00:00.000</td>
        <td>+10:00:00.00</td>
        <td>0.0</td>
        <td>19.8</td>
        <td>2026/11/10</td>
        <td>II</td>
        <td>0.05</td>
        <td>19.8</td>
        <td>2026/11/10</td>
        <td>2026/11/01</td>
        <td>ZTF</td>
        <td></td>
      </tr>
    </table>
    """
    items = parse_bright_supernovae_html(sample, max_mag=17.5)
    assert len(items) == 1
    sn = items[0]
    assert sn["doc_id"] == "tns_2026ahvu"
    assert sn["survey"] == "tns"
    assert sn["tier"] == "bright"
    assert sn["top_class"] == "SN Ia"
    assert sn["latest_mag"] == 12.3
    assert sn["host_galaxy"] == "NGC 1433"
    assert sn["aliases"] == ["ATLAS26ncp", "GOTO26ltt"]
    assert 55.0 < sn["meanra"] < 56.0
    assert -48.0 < sn["meandec"] < -47.0


def test_parse_cad_response() -> None:
    payload = {
        "fields": ["des", "orbit_id", "jd", "cd", "dist", "h"],
        "data": [["2026 VP8", "3", "2461357.5", "2026-Nov-13 02:12", "0.00758", "22.1"]],
    }
    rows = parse_cad_response(payload)
    assert len(rows) == 1
    assert rows[0]["des"] == "2026 VP8"
    assert rows[0]["close_approach_au"] == 0.00758
    assert rows[0]["h_mag"] == 22.1


def test_parse_mpc_comets() -> None:
    # Construct two fixed-width MPC Soft00Cmt lines: one near perihelion & bright, one far & faint.
    line_bright = (
        "    CK26A010  2026 11 20.0000  0.850000  0.990000  120.0000  200.0000   45.0000"
        "  20261112   8.5  4.0  C/2026 A1 (TestComet)                                      MPEC"
    )
    line_old = (
        "    CJ95O010  1997 03 29.0280  0.926906  0.994893  130.7391  281.8153   89.7307"
        "  20261112  -2.0  4.0  C/1995 O1 (Hale-Bopp)                                    MPC194091"
    )
    res = parse_mpc_comets(
        f"{line_bright}\n{line_old}\n",
        now=datetime(2026, 11, 12, tzinfo=UTC),
    )
    assert len(res) == 1
    assert res[0]["designation"] == "C/2026 A1"


def test_evergreen_variable_targets() -> None:
    items = evergreen_variable_targets(now=datetime(2026, 11, 12, tzinfo=UTC))
    assert len(items) == 12
    assert all(item["survey"] == "variable" for item in items)
    assert all(0.0 <= item["meanra"] < 360.0 for item in items)
    assert all(-90.0 <= item["meandec"] <= 90.0 for item in items)
    assert all(item["latest_mag"] <= 10.0 for item in items)


def test_compute_latest_photometry() -> None:
    dets = [
        DetectionRow(
            survey="ztf",
            oid="ZTF1",
            measurement_id="m1",
            mjd=61350.0,
            band="g",
            mag=15.2,
            mag_err=0.05,
            flux_njy=None,
            flux_err_njy=None,
            raw={"isdiffpos": 1},
        ),
        DetectionRow(
            survey="ztf",
            oid="ZTF1",
            measurement_id="m2",
            mjd=61355.0,
            band="r",
            mag=16.4,
            mag_err=0.06,
            flux_njy=None,
            flux_err_njy=None,
            raw={"isdiffpos": 1},
        ),
    ]
    latest_mag, latest_band = compute_latest_photometry(dets)
    assert latest_mag == 16.4
    assert latest_band == "r"
