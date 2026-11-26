import unittest
from rca_preview import preview

class PreviewTest(unittest.TestCase):
    def test_counterfactual(self):
        rows=[dict(synthetic=True,metric="latency_ms",phase="baseline",value=40,evidence_id="E1"),
              dict(synthetic=True,metric="latency_ms",phase="incident",value=160,evidence_id="E2")]
        result=preview(rows)
        self.assertEqual(result["hypothesis"],"LATENCY_REGRESSION_OBSERVED")
        self.assertEqual(result["root_cause"],"UNKNOWN")
        self.assertEqual(result["preview"]["conditional_reduction_ms"],120)
        self.assertEqual(result["evidence_ids"],["E1","E2"])
        self.assertFalse(result["executed_on_host"])
        self.assertIsNone(preview(rows[:1])["preview"])
        self.assertIsNone(preview([dict(r,synthetic=False) for r in rows])["preview"])
        with self.assertRaises(ValueError):
            preview([rows[0],dict(rows[1],evidence_id="E1")])
        with self.assertRaises(ValueError):
            preview([rows[0],dict(rows[1],value=float("nan"))])
    def test_measured_recovery_comparison(self):
        scope=["NODE-CI-ROOT","NODE-CI-ENT-ASSET-PAR","NODE-CI-ENT-APP-PAY"]
        rows=[dict(synthetic=True,metric="latency_ms",phase=p,value=v,evidence_id=e,measurement_scope=scope,occurred_at=t)
              for p,v,e,t in (("baseline",10,"E1","2026-01-01T09:00:00Z"),("incident",120,"E2","2026-01-01T09:00:01Z"),("recovery",11,"E3","2026-01-01T09:00:02Z"))]
        d=preview(rows)
        self.assertTrue(d["recovery"]["within_baseline_tolerance"])
        self.assertEqual(d["recovery"]["observed_reduction_ms"],109)
        self.assertFalse(d["recovery"]["causality_established"])
        self.assertEqual(d["evidence_ids"],["E1","E2","E3"])
        self.assertFalse(preview([*rows[:2],dict(rows[2],value=110)])["recovery"]["within_baseline_tolerance"])
        for bad in (dict(rows[2],evidence_id="E2"),dict(rows[2],measurement_scope=None),dict(rows[2],occurred_at="2025-01-01T00:00:00Z")):
            with self.assertRaises(ValueError):preview([*rows[:2],bad])
        with self.assertRaises(ValueError):preview(rows[1:])

    def test_recovery_requires_strict_canonical_utc_order(self):
        scope=["NODE-CI-ROOT","NODE-CI-ENT-ASSET-PAR","NODE-CI-ENT-APP-PAY"]
        rows=[dict(synthetic=True,metric="latency_ms",phase=p,value=v,evidence_id=e,measurement_scope=scope,occurred_at=t)
              for p,v,e,t in (("baseline",10,"E1","2026-01-01T09:00:00Z"),("incident",120,"E2","2026-01-01T09:00:01Z"),("recovery",11,"E3","2026-01-01T09:00:02Z"))]
        for idx,stamp in ((1,rows[0]["occurred_at"]),(2,rows[1]["occurred_at"]),(2,"2026-02-30T09:00:02Z"),(2,"2026-01-01T09:00:02+00:00"),(2,None)):
            with self.subTest(idx=idx,stamp=stamp):
                altered=[dict(row) for row in rows]
                altered[idx]["occurred_at"]=stamp
                with self.assertRaises(ValueError):preview(altered)
        self.assertTrue(preview(rows)["recovery"]["within_baseline_tolerance"])


class RecoveryVerifyTest(unittest.TestCase):
    def fixture(self, recovery=11):
        from recovery_verify import digest
        from copy import deepcopy
        run1,run2 = "RUN-"+"A"*16,"RUN-"+"B"*16
        incident1,incident2 = "INC-CI-INGEST-"+"a"*32,"INC-CI-INGEST-"+"b"*32
        scope = ["NODE-CI-ROOT","NODE-CI-ENT-ASSET-PAR","NODE-CI-ENT-APP-PAY"]
        def signal(i,sec,phase=None,value=None,message=None):
            ent = dict(asset_id=scope[1],application_id=scope[2],
                       occurred_at="2026-01-01T09:00:%02dZ"%sec)
            result = dict(id=i,tenant="synthetic-demo",resource=scope[0],synthetic=True,
                          kind="metric" if phase else "event",source="measured-recovery-ci",
                          severity="critical",enterprise=ent)
            if phase:
                ent["measurement"] = dict(classification="MEASURED_SYNTHETIC_LAB",
                    method="HTTP_MONOTONIC_MEDIAN_5",samples_ms=[value]*5)
                result["observation"] = dict(metric="latency_ms",phase=phase,value=value)
            else:
                ent["message"] = message
            return result
        old=[signal("base",0,"baseline",10),signal("fault",1,message="fault"),
             signal("incident",2,"incident",120)]
        def snapshot(rid,inc,signals):
            from ingestion_demo import ingest
            correlated=ingest(signals)["incidents"][0]
            assert correlated["resource"]==scope[0] and correlated["tenant"]=="synthetic-demo"
            normalized={sig["event_id"]:sig for sig in correlated["evidence"]}
            rows=[dict(evidence_id="EVD-"+rid[-1]+str(i),payload_hash=digest(
                dict(run_id=rid,incident_id=inc,resource=scope[0],
                     correlation_id=correlated["id"],signal=normalized[raw["id"]])),
                     signal=deepcopy(normalized[raw["id"]]))
                  for i,raw in enumerate(signals)]
            refs=[{k:r[k] for k in ("evidence_id","payload_hash")} for r in rows]
            return (dict(run=dict(run_id=rid,incident_id=inc,mode="DEMO"),
                         production_authorized=False),
                    dict(run_id=rid,root=scope[0],classification="SYNTHETIC_LAB_CONTEXT",
                         policy="DENY",production_authorized=False,evidence=refs,verified_signals=rows))
        first=snapshot(run1,incident1,old)
        refs=first[1]["evidence"]
        receipt=dict(classification="SYNTHETIC_LAB_ACTION_RECEIPT",status="SIMULATED",
                     receipt_id="ACT-"+"c"*32,completed_at="2026-01-01T09:00:03Z",
                     executed_on_host=False,production_authorized=False,operational_decision="DENY",
                     binding=dict(run_id=run1,workflow_id=run1,incident_id=incident1,
                                  context_sha256=digest([incident1,run1,sorted(refs,key=lambda r:r["evidence_id"])]),
                                  receipt_id="HITL-"+"d"*32,receipt_sha256="e"*64,
                                  lab_action=dict(action="RESET_LAB_HTTP_DELAY",resource=scope[0],target_id="f"*32)))
        action_hash=digest(receipt)
        second=snapshot(run2,incident2,old+[signal("act",3,message=
                        "Temporal lab action receipt "+action_hash+"; original run "+run1),
                        signal("recovery",4,"recovery",recovery)])
        snapshots={run1:first,run2:second}
        kwargs=dict(read_context=lambda rid:deepcopy(snapshots[rid]),
                    read_action_receipt=lambda rid:deepcopy(receipt),original_run_id=run1,
                    comparison_run_id=run2,scope=scope,original_refs=deepcopy(refs),
                    comparison_refs=deepcopy(second[1]["evidence"]),
                    action_receipt_id=receipt["receipt_id"],action_receipt_sha256=action_hash)
        return kwargs,snapshots,receipt

    def test_verify_measured_recovery_and_nonimprovement(self):
        from recovery_verify import verify_recovery
        for recovery,status in ((11,"RECOVERED"),(110,"NOT_RECOVERED")):
            kwargs,_,_=self.fixture(recovery)
            result=verify_recovery(**kwargs)
            self.assertEqual(result["status"],status)
            self.assertEqual(result["measurements"]["recovery_ms"],recovery)
            self.assertFalse(result["causality_established"])
            self.assertFalse(result["production_authorized"])

    def test_verify_rejects_bad_scope_evidence_and_receipt(self):
        from recovery_verify import verify_recovery
        kwargs,_,_=self.fixture()
        for bad in (dict(scope=["NODE-CI-OTHER",*kwargs["scope"][1:]]),
                    dict(original_refs=[dict(kwargs["original_refs"][0],payload_hash="0"*64),
                                        *kwargs["original_refs"][1:]]),
                    dict(action_receipt_sha256="0"*64),
                    dict(comparison_run_id=kwargs["original_run_id"])):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                verify_recovery(**(kwargs|bad))

    def test_verify_rejects_changed_original_and_out_of_order_recovery(self):
        from recovery_verify import verify_recovery
        for index,change in ((0,{"occurred_at":"2026-01-01T09:00:01Z"}),
                             (4,{"occurred_at":"2026-01-01T09:00:03Z"}),
                             (3,{"message":"client hash only"})):
            kwargs,snapshots,_=self.fixture()
            snapshots[kwargs["comparison_run_id"]][1]["verified_signals"][index]["signal"]["enterprise"].update(change)
            with self.subTest(index=index),self.assertRaises(ValueError):
                verify_recovery(**kwargs)

    def test_verify_rejects_original_mutation_during_read(self):
        from recovery_verify import verify_recovery
        kwargs,snapshots,_=self.fixture()
        read=kwargs["read_context"]
        def changing(rid):
            result=read(rid)
            if rid==kwargs["comparison_run_id"]:
                snapshots[kwargs["original_run_id"]][0]["run"]["status"]="CHANGED"
            return result
        kwargs["read_context"]=changing
        with self.assertRaises(ValueError):
            verify_recovery(**kwargs)


    def test_verify_rejects_noncanonical_signal_shape(self):
        from recovery_verify import verify_recovery
        for changes in ({"id":"base"}, {"sha256":"broken"}, {"source":"untyped"},
                        {"event_id":"../bad"}, {"tenant":"other"}):
            kwargs,snapshots,_=self.fixture()
            row=snapshots[kwargs["original_run_id"]][1]["verified_signals"][0]
            row["signal"].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                verify_recovery(**kwargs)


    def test_e17_gamma_projection_uses_trusted_worker_and_evidence(self):
        from e17_readback import project_recovery
        from copy import deepcopy
        kwargs,_,receipt=self.fixture()
        projection={"classification":"V3_E17_WORKER_RECEIPT_READBACK",
                    "run_id":kwargs["original_run_id"],"action_receipt":receipt,
                    "action_receipt_sha256":kwargs["action_receipt_sha256"],
                    "operational_decision":"DENY","production_authorized":False,
                    "core_business_stages_qualified":False,"activities_completed":1,
                    "history_events":11}
        request=dict(read_context=kwargs["read_context"],
                     original_run_id=kwargs["original_run_id"],
                     comparison_run_id=kwargs["comparison_run_id"])
        calls=[]
        def read(rid):
            calls.append(rid)
            return deepcopy(projection)
        result=project_recovery(read_receipt=read,**request)
        self.assertEqual(calls,[kwargs["original_run_id"]])
        self.assertEqual(result["verification"]["status"],"RECOVERED")
        self.assertEqual(result["worker"],projection)
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["tenant_acl_qualified"])
        for bad in ({"action_receipt_sha256":"0"*64},{"run_id":kwargs["comparison_run_id"]},
                    {"production_authorized":True},{"activities_completed":2},
                    {"core_business_stages_qualified":True}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                project_recovery(read_receipt=lambda rid:projection|bad,**request)
        with self.assertRaises(ValueError):
            project_recovery(read_receipt=read,**(request|{"comparison_run_id":kwargs["original_run_id"]}))


class MeasuredAdmissionTest(unittest.TestCase):
    def fixture(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        now=datetime(2026,1,1,9,0,10,tzinfo=timezone.utc)
        common=dict(resource="NODE-CI-ROOT",source="qa-http",tenant="synthetic-demo",
                    synthetic=True,severity="warning")
        scope=dict(asset_id="NODE-CI-ENT-ASSET-PAR",application_id="NODE-CI-ENT-APP-PAY")
        def metric(phase,v,at):
            return dict(common,id=phase,kind="metric",enterprise=dict(scope,occurred_at=at,
                measurement=dict(classification="MEASURED_SYNTHETIC_LAB",
                    method="HTTP_MONOTONIC_MEDIAN_5",samples_ms=[v]*5)),
                observation=dict(metric="latency_ms",phase=phase,value=v))
        rows=[metric("baseline",10,"2026-01-01T09:00:00Z"),
              metric("incident",100,"2026-01-01T09:00:02Z"),
              dict(common,id="log",kind="log",enterprise=dict(scope,occurred_at="2026-01-01T09:00:02Z",message="HTTP request observed"))]
        graph=Mock()
        return rows,graph,now

    def test_admit_measured_pair_and_exact_duplicates(self):
        from incident_admission import admit
        rows,graph,now=self.fixture()
        result=admit(rows+rows,graph,now=now)
        self.assertTrue(result["admitted"])
        self.assertEqual(result["disposition"],"MEASURED_INCIDENT_CANDIDATE")
        self.assertEqual((result["received"],result["unique"]),(6,3))
        self.assertEqual(result["root_cause"],"UNKNOWN")
        self.assertFalse(result["production_authorized"])
        self.assertEqual(graph.validate_signal.call_count,3)

    def test_admission_suppresses_nominal_incomplete_and_ambiguous(self):
        from incident_admission import admit
        from copy import deepcopy
        rows,graph,now=self.fixture()
        nominal=deepcopy(rows)
        nominal[1]["observation"]["value"]=11
        nominal[1]["enterprise"]["measurement"]["samples_ms"]=[11]*5
        simultaneous=deepcopy(rows)
        simultaneous[1]["enterprise"]["occurred_at"]=rows[0]["enterprise"]["occurred_at"]
        repeated=deepcopy(rows[1]); repeated["id"]="different-incident-sample"
        foreign_scope=deepcopy(rows);foreign_scope[2]["enterprise"]["application_id"]="NODE-CI-ENT-APP-CRM"
        for batch,expected in ((nominal,"NOMINAL_OBSERVATION"),(rows[1:],"INSUFFICIENT_EVIDENCE"),
                               (rows[:2],"INSUFFICIENT_EVIDENCE"),(simultaneous,"AMBIGUOUS_EVIDENCE"),
                               (rows+[repeated],"AMBIGUOUS_EVIDENCE"),(foreign_scope,"AMBIGUOUS_EVIDENCE")):
            with self.subTest(expected=expected):
                result=admit(batch,graph,now=now)
                self.assertFalse(result["admitted"])
                self.assertEqual(result["disposition"],expected)

    def test_admission_rejects_stale_untrusted_or_conflicting_samples(self):
        from datetime import timedelta
        from incident_admission import admit
        from copy import deepcopy
        rows,graph,now=self.fixture()
        self.assertEqual(admit(rows,graph,now=now+timedelta(seconds=121))["disposition"],"STALE_OR_FUTURE_EVIDENCE")
        for bad in (dict(rows[0],tenant="foreign"),dict(rows[0],synthetic=False),
                    dict(rows[0],severity="critical")):
            with self.assertRaises(ValueError):
                admit(rows+[bad],graph,now=now)
        graph.validate_signal.side_effect=ValueError("foreign topology")
        with self.assertRaises(ValueError):
            admit(rows,graph,now=now)
