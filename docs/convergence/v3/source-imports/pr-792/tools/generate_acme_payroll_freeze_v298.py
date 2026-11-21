#!/usr/bin/env python3
"""ACME payroll freeze tabletop simulation. No GLPI write, approval or remediation."""
import argparse,json
from datetime import datetime,timedelta,timezone

def generate():
    base=datetime(2026,10,29,9,10,tzinfo=timezone.utc)
    case="ACME-DEMO-PAYROLL-FREEZE-001"
    def event(minutes,actor,kind,message,**other):
        return {"timestamp":(base+timedelta(minutes=minutes)).isoformat(),
          "scope":"ACME","synthetic":True,"scenario_id":case,
          "actor":actor,"kind":kind,"message":message,**other}
    events=[
      event(0,"Claire / équipe Paie","human_message",
            "Je ne peux plus accéder à l'outil PAYROLL-X. Clôture des paies prioritaire.",
            service_id="ACME-SVC-PAYROLL"),
      event(1,"AIOps","triage","Incident reçu ; impact métier et fenêtre de changement à vérifier.",
            decision="INVESTIGATE"),
      event(2,"ACME-LB-PAYROLL-01","metric","Upstream healthy backends: 0/2",
            metric="healthy_backends",value=0,unit="backends"),
      event(2,"ACME-LB-PAYROLL-01","log","Health check failures on payroll backend pool",
            severity="ERROR"),
      event(3,"ACME-SVC-PAYROLL","trace","Login request 503 at reverse proxy",
            http_status=503,operation="payroll_login"),
      event(4,"AIOps Analyst","hypothesis",
            "Défaillance du pool de backends du load balancer suspectée ; redémarrage envisageable après vérification.",
            evidence_required=["health_checks","backend_connectivity","recent_changes"],
            diagnosis_status="HYPOTHESIS_NOT_PROVEN"),
      event(5,"AIOps Policy","policy_decision",
            "Freeze de fin de mois : redémarrage interdit sans dérogation management et validation Change.",
            freeze_active=True,approval_required=True,decision="HUMAN_APPROVAL",
            execution_allowed=False),
      event(6,"AIOps Bot","human_message",
            "Claire, l'accès PAYROLL-X est dégradé. Je poursuis les diagnostics non intrusifs. Une demande de dérogation management est nécessaire avant tout redémarrage.",
            recipient_role="payroll_reporter"),
      event(7,"Management Paie","human_message",
            "Merci de documenter l'impact, le risque et le plan de retour arrière avant décision.",
            simulated_person=True),
      event(8,"AIOps","change_proposal",
            "Proposition de restart LB sous réserve de diagnostic confirmé, tests préalables, approbation management et fenêtre autorisée.",
            proposed_action="RESTART_LOAD_BALANCER",target_ci="ACME-LB-PAYROLL-01",
            action_status="PROPOSED_ONLY",execution_allowed=False,
            rollback="Restore previous LB configuration and validate upstream health",
            glpi_status="NOT_CREATED"),
      event(9,"AIOps Policy","approval_pending",
            "Aucune approbation de management confirmée. Incident non résolu, aucune action exécutée.",
            decision="WAIT_FOR_HUMAN",execution_allowed=False,approval_status="PENDING"),
    ]
    return {"scope":"ACME","synthetic":True,"scenario_id":case,
            "scenario":"PAYROLL_ACCESS_FREEZE","events":events,
            "grounding":{"asset_catalog_status":"TO_VALIDATE_IN_CMDB",
                         "load_balancer_causality":"HYPOTHESIS_NOT_CONFIRMED"},
            "effects":{"restarts":0,"glpi_tickets_created":0,"approvals_granted":0},
            "disclaimer":"Tabletop scenario; all people, statements, evidence and decisions are simulated."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    from pathlib import Path
    result=generate()
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"scenario_id":result["scenario_id"],"events":len(result["events"]),
                       "approval":"PENDING","restart_executed":False}))
if __name__=="__main__":main()
