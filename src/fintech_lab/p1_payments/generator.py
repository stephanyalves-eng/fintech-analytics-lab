"""Deterministic synthetic PSP payments generator (P1.2).

Every table produced here is ``data_origin = synthetic``. Parameters live in
``projects/01-payment-intelligence/configs/generator.yaml`` and are not calibrated to
real-world benchmarks. One payment has 1..max_attempts authorization attempts.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from fintech_lab.shared.provenance import DataOrigin, make_rng

GENERATOR_VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[3]
P1_ROOT = REPO_ROOT / "projects" / "01-payment-intelligence"
DEFAULT_CONFIG = P1_ROOT / "configs" / "generator.yaml"

# (decline_code, category, reason_group, retryable) â€” fixed taxonomy from the data dictionary.
DECLINE_CODES: list[tuple[str, str, str, bool]] = [
    ("insufficient_funds", "soft", "funds", True),
    ("limit_exceeded", "soft", "funds", True),
    ("do_not_honor", "soft", "issuer_generic", True),
    ("issuer_unavailable", "soft", "issuer_technical", True),
    ("suspected_fraud", "hard", "risk", False),
    ("invalid_card", "hard", "card_data", False),
    ("expired_card", "hard", "card_data", False),
    ("pix_rejected", "hard", "pix", False),
    ("timeout", "technical", "technical", True),
    ("acquirer_error", "technical", "technical", True),
]
TABLES = (
    "dim_merchant",
    "dim_acquirer",
    "dim_payment_method",
    "dim_decline_code",
    "dim_fx_rate",
    "fact_payment",
    "fact_attempt",
    "fact_settlement",
)
_NS = 1_000_000_000


def load_config(path: str | Path | None = None, **overrides: Any) -> dict[str, Any]:
    """Load the YAML config and apply non-None top-level overrides (e.g. seed, target_attempts)."""
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    for key, value in overrides.items():
        if value is not None:
            cfg[key] = value
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    if cfg.get("data_origin") != DataOrigin.SYNTHETIC:
        raise ValueError("generator config must declare data_origin: synthetic")
    make_rng(cfg["seed"])  # validates seed
    if not 1_000 <= int(cfg["target_attempts"]) <= 5_000_000:
        raise ValueError("target_attempts must be in [1000, 5000000]")
    if int(cfg["n_merchants"]) < len(cfg["countries"]):
        raise ValueError("n_merchants must be >= number of countries")
    if cfg["retry"]["max_attempts"] != len(cfg["attempt_logit_effect"]):
        raise ValueError("attempt_logit_effect must have one entry per attempt_no")
    for country, mix in cfg["method_mix"].items():
        if abs(sum(mix.values()) - 1) > 1e-9:
            raise ValueError(f"method_mix[{country}] must sum to 1")
        if "pix" in mix and country != "BR":
            raise ValueError("pix is only available in BR")


def _p(weights: dict[str, float]) -> tuple[list[str], np.ndarray]:
    keys = list(weights)
    w = np.array([float(weights[k]) for k in keys])
    return keys, w / w.sum()


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _round_money(values: np.ndarray, decimals: np.ndarray) -> np.ndarray:
    scale = 10.0**decimals
    return np.round(values * scale) / scale


def _local_to_utc(local: pd.Series, tz: pd.Series) -> pd.Series:
    out = pd.Series(pd.NaT, index=local.index, dtype="datetime64[ns]")
    for zone in tz.unique():
        m = tz == zone
        idx = pd.DatetimeIndex(local[m]).tz_localize(
            zone, ambiguous=np.zeros(int(m.sum()), dtype=bool), nonexistent="shift_forward"
        )
        out[m] = idx.tz_convert("UTC").tz_localize(None).as_unit("ns")
    return out


def _utc_to_local(utc: pd.Series, tz: pd.Series) -> pd.Series:
    out = pd.Series(pd.NaT, index=utc.index, dtype="datetime64[ns]")
    for zone in tz.unique():
        m = tz == zone
        idx = pd.DatetimeIndex(utc[m]).tz_localize("UTC").tz_convert(zone)
        out[m] = idx.tz_localize(None).as_unit("ns")
    return out


def generate(cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Generate all P1 tables. Same config (incl. seed) => identical output."""
    cfg = copy.deepcopy(cfg)
    validate_config(cfg)
    streams = np.random.SeedSequence(cfg["seed"]).spawn(4)
    r_merch, r_fx, r_pay, r_att = (np.random.default_rng(s) for s in streams)

    countries = list(cfg["countries"])
    ccfg = cfg["countries"]
    dec_map = cfg["currency_decimals"]
    n_days = int(cfg["days"])
    dates = pd.date_range(pd.Timestamp(cfg["start_date"]), periods=n_days, freq="D")

    # ---- FX: daily synthetic random walk, rate_to_brl ------------------------------------
    fx_rows, fx_matrix = [], {}
    for c in countries:
        cur, vol = ccfg[c]["currency"], float(ccfg[c]["fx_daily_vol"])
        steps = r_fx.normal(0.0, vol, n_days)
        steps[0] = 0.0
        rate = np.round(float(ccfg[c]["fx_start"]) * np.exp(np.cumsum(steps)), 8)
        fx_matrix[cur] = rate
        fx_rows.append(
            pd.DataFrame({"rate_date": dates.date, "currency": cur, "rate_to_brl": rate})
        )
    dim_fx = pd.concat(fx_rows, ignore_index=True)

    # ---- acquirers ----------------------------------------------------------------------
    acq_ids = list(cfg["acquirers"])
    acfg = cfg["acquirers"]
    acq_country = np.array([acfg[a]["country"] for a in acq_ids])
    acq_type = np.array([acfg[a]["type"] for a in acq_ids])
    alt_acq = np.arange(len(acq_ids))
    for i in range(len(acq_ids)):
        peers = [
            j
            for j in range(len(acq_ids))
            if j != i and acq_country[j] == acq_country[i] and acq_type[j] == acq_type[i]
        ]
        if peers:
            alt_acq[i] = peers[0]
    acq_base = np.array([acfg[a]["base_logit"] for a in acq_ids], dtype=float)
    acq_err = np.array([acfg[a]["error_rate"] for a in acq_ids], dtype=float)
    acq_peak = np.array([acfg[a]["peak_error_mult"] for a in acq_ids], dtype=float)
    acq_lat = np.array([acfg[a]["latency_median_ms"] for a in acq_ids], dtype=float)
    acq_fix = np.array([acfg[a]["fee_fixed_local"] for a in acq_ids], dtype=float)
    acq_bps = np.array([acfg[a]["fee_bps_approved"] for a in acq_ids], dtype=float)
    pix_acq = acq_ids.index("PIX_BR")
    dim_acquirer = pd.DataFrame(
        {
            "acquirer_id": acq_ids,
            "country": acq_country,
            "acquirer_type": acq_type,
            "fee_fixed_local": acq_fix,
            "fee_bps_approved": acq_bps.astype("int32"),
        }
    )

    # ---- methods & decline codes --------------------------------------------------------
    methods = list(cfg["methods"])
    mcfg = cfg["methods"]
    dim_method = pd.DataFrame(
        {
            "method_code": methods,
            "method_family": [mcfg[m]["family"] for m in methods],
            "available_countries": [
                ",".join(c for c in countries if m in cfg["method_mix"][c]) for m in methods
            ],
            "settlement_lag_days": np.array(
                [mcfg[m]["settlement_lag_days"] for m in methods], dtype="int32"
            ),
        }
    )
    dim_decline = pd.DataFrame(
        DECLINE_CODES, columns=["decline_code", "category", "reason_group", "retryable"]
    )

    # ---- merchants ----------------------------------------------------------------------
    n_m = int(cfg["n_merchants"])
    c_keys, c_p = _p({c: ccfg[c]["weight"] for c in countries})
    m_country = r_merch.choice(len(c_keys), n_m, p=c_p)
    m_country[: len(c_keys)] = np.arange(len(c_keys))  # every country has >= 1 merchant
    s_keys, s_p = _p({s: v["weight"] for s, v in cfg["sectors"].items()})
    m_sector = r_merch.choice(len(s_keys), n_m, p=s_p)
    t_keys, t_p = _p({t: v["weight"] for t, v in cfg["size_tiers"].items()})
    m_tier = r_merch.choice(len(t_keys), n_m, p=t_p)
    pre = r_merch.random(n_m) < float(cfg["merchant_preexisting_share"])
    m_offset = np.where(
        pre,
        -r_merch.integers(30, 731, n_m),
        r_merch.integers(0, max(1, n_days - 30), n_m),
    )
    m_logit = r_merch.normal(0.0, float(cfg["merchant_logit_sd"]), n_m)
    m_primary = np.empty(n_m, dtype=int)
    for ci, c in enumerate(c_keys):
        card = [
            i
            for i, a in enumerate(acq_ids)
            if acq_country[i] == c and acq_type[i] == "card_acquirer"
        ]
        w = np.array([acfg[acq_ids[i]]["routing_weight"] for i in card], dtype=float)
        sel = m_country == ci
        m_primary[sel] = np.array(card)[r_merch.choice(len(card), int(sel.sum()), p=w / w.sum())]

    # day-of-period demand curve
    seas = cfg["seasonality"]
    day_w = (
        np.array(seas["weekday"])[dates.day_of_week]
        * np.array(seas["month"])[dates.month - 1]
        * (1.0 + float(seas["annual_growth"]) * np.arange(n_days) / max(1, n_days - 1))
    )
    for d, mult in seas.get("peak_days", {}).items():
        hit = dates == pd.Timestamp(d)
        day_w[hit] *= float(mult)
    cdf = np.cumsum(day_w) / day_w.sum()
    cdf_before = np.concatenate([[0.0], cdf[:-1]])
    first_day = np.clip(m_offset, 0, n_days - 1)
    active_mass = 1.0 - cdf_before[first_day]
    tier_vol = np.array([cfg["size_tiers"][t]["volume_weight"] for t in t_keys], dtype=float)
    m_volume = tier_vol[m_tier] * r_merch.lognormal(0.0, 0.5, n_m) * active_mass

    merchant_country = np.array(c_keys)[m_country]
    dim_merchant = pd.DataFrame(
        {
            "merchant_id": [f"M{i + 1:05d}" for i in range(n_m)],
            "sector": np.array(s_keys)[m_sector],
            "country": merchant_country,
            "currency": [ccfg[c]["currency"] for c in merchant_country],
            "timezone": [ccfg[c]["timezone"] for c in merchant_country],
            "size_tier": np.array(t_keys)[m_tier],
            "activation_date": (dates[0] + pd.to_timedelta(m_offset, unit="D")).date,
        }
    )

    # ---- payments (over-generate, then keep a prefix that fits target_attempts) ---------
    target = int(cfg["target_attempts"])
    n_gen = target  # every payment has >= 1 attempt, so this is an upper bound
    p_m = r_pay.choice(n_m, n_gen, p=m_volume / m_volume.sum())
    lo = cdf_before[first_day[p_m]]
    p_day = np.minimum(
        np.searchsorted(cdf, lo + r_pay.random(n_gen) * (1.0 - lo), side="right"), n_days - 1
    )
    hour_p = np.array(seas["hour"], dtype=float)
    p_hour = r_pay.choice(24, n_gen, p=hour_p / hour_p.sum())
    p_sec = r_pay.integers(0, 3600, n_gen)
    p_country = m_country[p_m]
    p_method = np.empty(n_gen, dtype=int)
    for ci, c in enumerate(c_keys):
        keys, probs = _p(cfg["method_mix"][c])
        sel = p_country == ci
        p_method[sel] = np.array([methods.index(k) for k in keys])[
            r_pay.choice(len(keys), int(sel.sum()), p=probs)
        ]
    p_mobile = r_pay.random(n_gen) < float(cfg["device_mobile_share"])
    p_risk = r_pay.beta(cfg["risk"]["beta_a"], cfg["risk"]["beta_b"], n_gen)
    sec_cfg = [cfg["sectors"][s] for s in s_keys]
    med = np.array([s["median_brl"] for s in sec_cfg], dtype=float)[m_sector[p_m]]
    sig = np.array([s["sigma"] for s in sec_cfg], dtype=float)[m_sector[p_m]]
    amount_brl_raw = np.exp(r_pay.normal(np.log(med), sig))
    p_currency = np.array([ccfg[c]["currency"] for c in c_keys])[p_country]
    p_dec = np.array([dec_map[c] for c in p_currency])
    fx_on_day = np.empty(n_gen)
    for cur, rates in fx_matrix.items():
        sel = p_currency == cur
        fx_on_day[sel] = rates[p_day[sel]]
    amount = np.maximum(_round_money(amount_brl_raw / fx_on_day, p_dec), 1.0)
    amount_brl = amount * fx_on_day
    band_logit = np.array(cfg["amount_band_logit"]["effects"])[
        np.searchsorted(np.array(cfg["amount_band_logit"]["edges_brl"]), amount_brl, side="right")
    ]
    tz_p = pd.Series(np.array([ccfg[c]["timezone"] for c in c_keys])[p_country])
    local = pd.Series(
        dates[p_day].values
        + (p_hour.astype("int64") * 3600 + p_sec).astype("timedelta64[s]").astype("timedelta64[ns]")
    )
    created_utc = _local_to_utc(local, tz_p).to_numpy().astype("int64")

    # ---- attempts -----------------------------------------------------------------------
    rc = cfg["retry"]
    max_att = int(rc["max_attempts"])
    att_eff = {int(k): float(v) for k, v in cfg["attempt_logit_effect"].items()}
    m_eff = np.array([mcfg[m]["logit_effect"] for m in methods], dtype=float)[p_method]
    sector_eff = np.array([s["logit_effect"] for s in sec_cfg], dtype=float)[m_sector[p_m]]
    night = np.isin(p_hour, cfg["night_hours_local"])
    peak = np.isin(p_hour, cfg["peak_hours_local"])
    static_logit = (
        m_eff
        + sector_eff
        + m_logit[p_m]
        + band_logit
        + night * float(cfg["night_logit_effect"])
        + float(cfg["risk"]["logit_coef"]) * p_risk
    )
    is_pix = p_method == methods.index("pix")
    code_idx = {c[0]: i for i, c in enumerate(DECLINE_CODES)}
    cat_codes = {}
    for cat, weights in cfg["decline_code_weights"].items():
        keys, probs = _p(weights)
        cat_codes[cat] = (np.array([code_idx[k] for k in keys]), probs)

    active = np.arange(n_gen)
    cur_acq = np.where(is_pix, pix_acq, m_primary[p_m])
    to_alt = ~is_pix & (r_att.random(n_gen) >= float(cfg["primary_acquirer_share"]))
    cur_acq = np.where(to_alt, alt_acq[cur_acq], cur_acq)
    last_t = created_utc.copy()
    prev_cat = np.full(n_gen, "", dtype=object)
    parts = []
    for k in range(1, max_att + 1):
        if active.size == 0:
            break
        n = active.size
        acq = cur_acq[active]
        if k > 1:
            pc = prev_cat[active]
            sw_p = np.where(pc == "technical", rc["switch_prob_technical"], rc["switch_prob_soft"])
            acq = np.where(r_att.random(n) < sw_p, alt_acq[acq], acq)
            delay_mean = np.where(
                pc == "technical", rc["delay_mean_s_technical"], rc["delay_mean_s_soft"]
            )
        else:
            delay_mean = np.full(n, 2.0)
        t = last_t[active] + ((1.0 + r_att.exponential(delay_mean)) * _NS).astype("int64")
        t -= t % 1_000_000  # millisecond precision
        p_err = np.minimum(acq_err[acq] * np.where(peak[active], acq_peak[acq], 1.0), 0.5)
        is_err = r_att.random(n) < p_err
        p_app = _sigmoid(acq_base[acq] + static_logit[active] + att_eff[k])
        approved = ~is_err & (r_att.random(n) < p_app)
        declined = ~is_err & ~approved
        hard_p = cfg["risk"]["hard_share_base"] + cfg["risk"]["hard_share_slope"] * p_risk[active]
        hard = declined & (is_pix[active] | (r_att.random(n) < hard_p))
        soft = declined & ~hard
        cat = np.where(is_err, "technical", np.where(hard, "hard", np.where(soft, "soft", "")))
        code = np.full(n, -1)
        for name, mask in (("soft", soft), ("hard", hard & ~is_pix[active]), ("technical", is_err)):
            codes, probs = cat_codes[name]
            code[mask] = codes[r_att.choice(len(codes), int(mask.sum()), p=probs)]
        code[hard & is_pix[active]] = code_idx["pix_rejected"]
        latency = np.maximum(1, np.round(r_att.lognormal(np.log(acq_lat[acq]), 0.35))).astype(
            "int64"
        )
        to = code == code_idx["timeout"]
        latency[to] = int(cfg["timeout_ms"]) + np.round(
            r_att.exponential(500.0, int(to.sum()))
        ).astype("int64")
        result = np.where(approved, "approved", np.where(is_err, "error", "declined"))
        cost = acq_fix[acq] + approved * amount[active] * acq_bps[acq] / 10_000.0
        parts.append(
            pd.DataFrame(
                {
                    "_p": active,
                    "attempt_no": k,
                    "_acq": acq,
                    "_t": t,
                    "result": result,
                    "_code": code,
                    "latency_ms": latency,
                    "_cost": _round_money(cost, p_dec[active]),
                }
            )
        )
        retry_p = np.where(
            cat == "technical",
            rc["prob_after_technical"],
            np.where(cat == "soft", rc["prob_after_soft"], 0.0),
        )
        again = (k < max_att) & (r_att.random(n) < retry_p)
        prev_cat[active] = cat
        cur_acq[active] = acq
        last_t[active] = t
        active = active[again]
    att = pd.concat(parts, ignore_index=True)

    # ---- truncate to target_attempts (payments are i.i.d. in generation order) ----------
    n_att = np.bincount(att["_p"].to_numpy(), minlength=n_gen)
    keep = np.cumsum(n_att) <= target
    att = att[keep[att["_p"].to_numpy()]]
    kept = np.flatnonzero(keep)
    order = kept[np.lexsort((kept, created_utc[kept]))]  # chronological payment ids
    pid_of = np.full(n_gen, -1)
    pid_of[order] = np.arange(order.size)
    succeeded_gen = np.zeros(n_gen, dtype=bool)
    succeeded_gen[att.loc[att["result"] == "approved", "_p"].to_numpy()] = True

    fact_payment = pd.DataFrame(
        {
            "payment_id": [f"P{i + 1:09d}" for i in range(order.size)],
            "merchant_id": dim_merchant["merchant_id"].to_numpy()[p_m[order]],
            "method_code": np.array(methods)[p_method[order]],
            "created_at_utc": created_utc[order].astype("datetime64[ns]"),
            "amount": amount[order],
            "currency": p_currency[order],
            "device_type": np.where(p_mobile[order], "mobile_app", "web"),
            "final_status": np.where(succeeded_gen[order], "succeeded", "failed"),
        }
    )

    att = att.assign(_pid=pid_of[att["_p"].to_numpy()]).sort_values(
        ["_pid", "attempt_no"], kind="stable"
    )
    code_names = np.array([c[0] for c in DECLINE_CODES] + [None], dtype=object)
    fact_attempt = pd.DataFrame(
        {
            "attempt_id": [f"A{i + 1:010d}" for i in range(len(att))],
            "payment_id": fact_payment["payment_id"].to_numpy()[att["_pid"].to_numpy()],
            "attempt_no": att["attempt_no"].to_numpy().astype("int32"),
            "acquirer_id": np.array(acq_ids)[att["_acq"].to_numpy()],
            "attempted_at_utc": att["_t"].to_numpy().astype("datetime64[ns]"),
            "result": att["result"].to_numpy(),
            "decline_code": code_names[att["_code"].to_numpy()],
            "latency_ms": att["latency_ms"].to_numpy().astype("int32"),
            "processing_cost": att["_cost"].to_numpy(),
        }
    )

    # ---- settlement: 1 per succeeded payment, D+N on the local approval date -----------
    appr = att[att["result"] == "approved"]
    ap = appr["_p"].to_numpy()
    tz_ap = pd.Series(tz_p.to_numpy()[ap])
    appr_local = _utc_to_local(pd.Series(appr["_t"].to_numpy().astype("datetime64[ns]")), tz_ap)
    lag = dim_method["settlement_lag_days"].to_numpy()[p_method[ap]]
    mdr = np.array(
        [
            cfg["mdr"][methods[mi]][t_keys[ti]]
            for mi, ti in zip(p_method[ap], m_tier[p_m[ap]], strict=True)
        ]
    )
    gross = amount[ap]
    fee = _round_money(gross * mdr, p_dec[ap])
    sett = pd.DataFrame(
        {
            "_pid": pid_of[ap],
            "settlement_date": (
                appr_local.dt.normalize() + pd.to_timedelta(lag, unit="D")
            ).dt.date.to_numpy(),
            "gross_amount": gross,
            "fee": fee,
            "net_amount": _round_money(gross - fee, p_dec[ap]),
            "currency": p_currency[ap],
        }
    ).sort_values("_pid", kind="stable")
    fact_settlement = pd.DataFrame(
        {
            "settlement_id": [f"S{i + 1:09d}" for i in range(len(sett))],
            "payment_id": fact_payment["payment_id"].to_numpy()[sett["_pid"].to_numpy()],
            **{
                c: sett[c].to_numpy()
                for c in ("settlement_date", "gross_amount", "fee", "net_amount", "currency")
            },
        }
    )

    return {
        "dim_merchant": dim_merchant,
        "dim_acquirer": dim_acquirer,
        "dim_payment_method": dim_method,
        "dim_decline_code": dim_decline,
        "dim_fx_rate": dim_fx,
        "fact_payment": fact_payment,
        "fact_attempt": fact_attempt,
        "fact_settlement": fact_settlement,
    }
