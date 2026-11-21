#!/usr/bin/env python3
"""Offline adversarial evaluation. Ground truth is opened only AFTER predictions exist.

Predictions JSON: {"root_causes":[{"root_cause_id":"RC-...", "evidence_ids":[...]}],
"rejected_noise_ids":[...], "critic":{"validated":false,"issues":[...]}}.
Scoring is exact-label only; unrecognized guesses count as false positives.
"""
import argparse,json
from pathlib import Path

def evaluate(truth,prediction,observations):
    truth_ids={x["root_cause_id"] for x in truth.get("root_causes",[])}
    proposed=prediction.get("root_causes",[])
    if not isinstance(proposed,list):raise ValueError("root_causes must be a list")
    guessed=[x.get("root_cause_id") for x in proposed if isinstance(x,dict)]
    if len(guessed)!=len(set(guessed)):raise ValueError("duplicate root causes")
    predicted=set(guessed)
    tp=len(truth_ids&predicted)
    fp=len(predicted-truth_ids)
    fn=len(truth_ids-predicted)
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    # Cannot score distractor detection without per-observation noise labels.
    # Ground truth currently specifies only the noise count.
    noise_count=truth.get("unrelated_observation_count",0)
    evidence_refs=sum(len(x.get("evidence_ids",[])) for x in proposed if isinstance(x,dict))
    output={"exercise_id":truth.get("exercise_id"),"root_causes_expected":len(truth_ids),
       "root_causes_predicted":len(predicted),"true_positives":tp,"false_positives":fp,
       "false_negatives":fn,"precision":round(precision,4),"recall":round(recall,4),
       "f1":round(f1,4),"evidence_references_claimed":evidence_refs,
       "noise_observations_expected":noise_count,
       "noise_resistance_score":None,
       "critic_validated":(prediction.get("critic") or {}).get("validated"),
       "limitations":["Root cause score uses exact evaluator IDs, not semantic equivalence.",
       "Noise rejection and citation correctness require per-event truth and evidence IDs.",
       "No model call or HITL/GLPI action is performed by this evaluator."]}
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--truth",type=Path,required=True)
    p.add_argument("--predictions",type=Path,required=True)
    p.add_argument("--observations",type=Path,required=True)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.truth.resolve()==args.predictions.resolve():p.error("truth/prediction must be separate")
    truth=json.loads(args.truth.read_text())
    predictions=json.loads(args.predictions.read_text())
    observations=[json.loads(x) for x in args.observations.read_text().splitlines() if x.strip()]
    if truth.get("scope")!="ACME" or any(x.get("scope")!="ACME" for x in observations):
        p.error("not strictly ACME scoped")
    report=evaluate(truth,predictions,observations)
    rendered=json.dumps(report,indent=2,ensure_ascii=False)
    if args.output:args.output.write_text(rendered+"\n")
    print(rendered)

if __name__=="__main__":main()
