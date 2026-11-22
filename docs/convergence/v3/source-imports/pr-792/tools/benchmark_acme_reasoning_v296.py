#!/usr/bin/env python3
"""ACME offline reasoning burn-in. No simulated model scores and no live actions."""
import argparse,hashlib,importlib.util,json,statistics,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def load(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def benchmark(predictions_dir,seed_start=20261021,seeds=5,modes=None):
    if not 1<=seeds<=1000: raise ValueError("seeds must be between 1 and 1000")
    generator=load("generate_acme_adversarial_v294.py","generator")
    evaluator=load("evaluate_acme_adversarial_v295.py","evaluator")
    modes=modes or generator.MODES
    samples=[]
    for offset in range(seeds):
        for mode in modes:
            seed=seed_start+offset
            scenario=generator.generate(mode,seed)
            obs=scenario["observations"]
            truth=scenario["ground_truth"]
            exercise=truth["exercise_id"]
            observations_bytes=json.dumps(obs,sort_keys=True,ensure_ascii=False).encode()
            digest=hashlib.sha256(observations_bytes).hexdigest()
            path=predictions_dir/(exercise+".json")
            if not path.is_file():
                samples.append({"exercise_id":exercise,"mode":mode,"seed":seed,
                    "status":"NOT_EVALUATED","reason":"prediction_missing",
                    "observation_sha256":digest,"f1":None,"precision":None,"recall":None})
                continue
            prediction=json.loads(path.read_text())
            if prediction.get("exercise_id")!=exercise or prediction.get("observation_sha256")!=digest:
                samples.append({"exercise_id":exercise,"mode":mode,"seed":seed,
                    "status":"REJECTED","reason":"prediction_identity_mismatch",
                    "observation_sha256":digest,"f1":None,"precision":None,"recall":None})
                continue
            result=evaluator.evaluate(truth,prediction,obs)
            samples.append({"exercise_id":exercise,"mode":mode,"seed":seed,
                "status":"EVALUATED","reason":None,"observation_sha256":digest,
                "f1":result["f1"],"precision":result["precision"],"recall":result["recall"],
                "false_positives":result["false_positives"],"false_negatives":result["false_negatives"],
                "critic_validated":result["critic_validated"]})
    measured=[x for x in samples if x["status"]=="EVALUATED"]
    total=len(samples)
    summary={"scope":"ACME","benchmark":"adversarial-reasoning-v296",
       "prediction_source":"external_predictions_only","model_inference_performed":False,
       "run_at":datetime.now(timezone.utc).isoformat(),
       "cases_total":total,"cases_evaluated":len(measured),
       "cases_missing":sum(x["status"]=="NOT_EVALUATED" for x in samples),
       "cases_rejected":sum(x["status"]=="REJECTED" for x in samples),
       "coverage":round(len(measured)/total,4) if total else 0,
       "mean_f1":round(statistics.mean(x["f1"] for x in measured),4) if measured else None,
       "mean_precision":round(statistics.mean(x["precision"] for x in measured),4) if measured else None,
       "mean_recall":round(statistics.mean(x["recall"] for x in measured),4) if measured else None,
       "noise_resistance":None,
       "limitations":["Missing predictions are not scored as zero or success.",
          "Scores require independently captured predictions from a real model.",
          "This benchmark neither sends model prompts nor triggers HITL, GLPI or remediation."]}
    return {"summary":summary,"samples":samples}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--predictions-dir",type=Path,required=True)
    p.add_argument("--seed-start",type=int,default=20261021)
    p.add_argument("--seeds",type=int,default=5)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=benchmark(args.predictions_dir,args.seed_start,args.seeds)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report["summary"],ensure_ascii=False,indent=2))
    if report["summary"]["cases_rejected"]:
        return 2
    return 0
if __name__=="__main__":sys.exit(main())
