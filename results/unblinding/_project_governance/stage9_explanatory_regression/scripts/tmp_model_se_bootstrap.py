# TASK-2999 draft: response-level bootstrap SE of the standardized model effect
# for ORIGINAL (non-expansion) experiments, using the FROZEN effect definitions
# from T2K10-20260923T034851/final_audit/blinding_effect_magnitude_analysis.py
# (record_outcome, normalize01 logic). Frozen files are only read, never modified.
import importlib.util, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
from statistics import fmean

UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
FIG = Path("/home/justin/work/research/T2K10-FIGURES")
MOD = UNBL/"T2K10-20260923T034851/final_audit/blinding_effect_magnitude_analysis.py"
spec = importlib.util.spec_from_file_location("frozen_bema", MOD)
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
B.ROOTS = {"run6": UNBL/"TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143",
           "run10": UNBL/"T2K10-20260923T034851"}   # canonical read-only roots

t0=time.time()
registry = json.load(open(FIG/"experiment_registry.json"))["experiments"]
codebook = pd.read_csv(FIG/"contrast_feature_codebook.csv")
models = [m["safe_name"] for m in json.load(open(UNBL/"T2K10-20260923T034851/manifest.json"))["models"]]
stage5 = pd.read_csv(UNBL/"_project_governance/stage5_exploratory/data/stage5_dataset.csv")
sd_h = stage5.groupby("contrast_id").sd_human_pooled_pp.first().to_dict()
frozen = pd.read_csv(UNBL/"agreed_figure_code_package/data/blinding_signed_contrasts.csv")
o5 = stage5[stage5.study_group=="original"]
fz = {}
for r in frozen.itertuples():
    fz[(r.model, r.experiment, r.contrast, "blinded")] = r.d_m_B
    fz[(r.model, r.experiment, r.contrast, "unblinded")] = r.d_m_U
assert len(fz)==524, len(fz)

# 1) load per-record outcomes once per (exp, blinding, model, arm)
arms_out = {}
for exp, cfg in registry.items():
    if exp in ("base_rate","false_consensus"): continue
    root = B.ROOTS[cfg["run"]]
    wave = cfg["human"]["wave1_3"]
    arms = list(wave["arms"])
    for blind in ("blinded","unblinded"):
        for model in models:
            path = root/model/f"{exp}_{blind}"/"records.jsonl"
            if not path.is_file(): continue
            by = {a: [] for a in arms}
            with open(path) as fh:
                for line in fh:
                    rec = json.loads(line)
                    if not rec.get("succeeded", False): continue
                    v = B.record_outcome(rec, exp)
                    if v is not None and rec.get("arm") in by:
                        by[rec["arm"]].append(v)
            arms_out[(exp,blind,model)] = by
print("loaded legs", len(arms_out), f"{time.time()-t0:.1f}s")

# 2) bootstrap
def d_m_point(by, c):
    return None if any(not by[a] for a in (c.treatment_arm, c.comparison_arm)) else None

B_DRAWS, RNG = 500, np.random.default_rng(20261028)
rows=[]
for exp, cfg in registry.items():
    if exp in ("base_rate","false_consensus"): continue
    spec01 = cfg["normalization_0_1"]; wave = cfg["human"]["wave1_3"]
    anchor = "anchor_mc" in list(wave["arms"].values())[0]
    for c in codebook[codebook.experiment==exp].itertuples():
        # map codebook contrast -> stage5 contrast_id via frozen |d_h| = |delta_human_pp|
        dh0 = frozen[(frozen.experiment==exp)&(frozen.contrast==c.contrast)].d_h.iloc[0]
        hit = o5[(o5.experiment_id==exp)&(np.isclose(o5.delta_human_pp.abs(),abs(dh0),atol=1e-6))]
        cids = hit.contrast_id.unique()
        if len(cids)!=1:
            print("NOMATCH", exp, c.contrast); continue
        cid = cids[0]; sdp = sd_h[cid]
        for blind in ("blinded","unblinded"):
            for model in models:
                by = arms_out.get((exp,blind,model))
                if by is None:
                    print("NOARM", exp, blind, model); continue
                ta, ca = c.treatment_arm, c.comparison_arm
                xt, xc = np.array(by[ta]), np.array(by[ca])
                if len(xt)==0 or len(xc)==0:
                    print("EMPTYARM", exp, blind, model, ta, len(xt), ca, len(xc)); continue
                lo, hi = spec01["min"], spec01["max"]
                def dm(xt_s, xc_s):
                    mt = xt_s.mean(axis=-1) if anchor else (xt_s.mean(axis=-1)-lo)/(hi-lo)
                    mc = xc_s.mean(axis=-1) if anchor else (xc_s.mean(axis=-1)-lo)/(hi-lo)
                    return (mt-mc)*100.0
                point = dm(xt, xc)
                ref = fz.get((model, exp, c.contrast, blind))
                match = ref is not None and abs(point-ref) < 1e-6
                idx_t = RNG.integers(0, len(xt), (B_DRAWS, len(xt)))
                idx_c = RNG.integers(0, len(xc), (B_DRAWS, len(xc)))
                draws = dm(xt[idx_t], xc[idx_c])
                se_std = float(draws.std(ddof=1))/sdp
                rows.append(dict(contrast_id=cid, experiment=exp, model=model, blinding=blind,
                                 d_m_point=point, d_m_frozen=ref, point_matches_frozen=match,
                                 se_model_effect=se_std, n_resamples=B_DRAWS,
                                 method="response-level within-arm bootstrap of arm means, standardized by frozen sd_human_pooled",
                                 n_treatment=len(xt), n_comparison=len(xc),
                                 degenerate=bool(se_std==0),
                                 reliable_flag=bool(match and len(xt)>=30 and len(xc)>=30 and se_std>0)))
df = pd.DataFrame(rows)
df["reliable_flag"]=df["reliable_flag"].astype(bool)
print("rows",len(df),"mismatches",(~df.point_matches_frozen.astype(bool)).sum(),
      "unreliable",(~df.reliable_flag.astype(bool)).sum(), f"{time.time()-t0:.1f}s")
df.to_csv("/home/justin/work/crew/research/OUTBOX/stage9_artifacts/MODEL_SE_BOOTSTRAP_DRAFT.csv", index=False)
print(df.groupby(df.point_matches_frozen.astype(bool)).size())
