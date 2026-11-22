#!/usr/bin/env python3
"""Build an offline, synthetic ACME Digital Twin demonstration.

No credentials, Docker, network calls, production database or LIVE remediations.
The output is one standalone HTML file, not a runtime E2E qualification.
"""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from portal.ui_theme import shell, panel, pretty
from portal.twin_graph import graph_panel

NODES=[
    {"node_id":"ACME-SAN-FABRIC-A","name":"Fabric FC A","type":"SAN_FABRIC","site":"PARIS","state":"DEGRADED"},
    {"node_id":"ACME-STORAGE-A","name":"Stockage A","type":"STORAGE","site":"PARIS","state":"DEGRADED"},
    {"node_id":"ACME-ESXI-01","name":"ESXi 01","type":"HYPERVISOR","site":"PARIS","state":"HEALTHY"},
    {"node_id":"ACME-SVC-PAYMENTS","name":"Paiement ACME","type":"SERVICE","site":"PARIS","state":"HEALTHY"},
    {"node_id":"ACME-SAN-FABRIC-B","name":"Fabric FC B","type":"SAN_FABRIC","site":"PARIS","state":"HEALTHY"},
]
EDGES=[
    {"source_id":"ACME-SAN-FABRIC-A","target_id":"ACME-STORAGE-A","relation_type":"SUPPORTS"},
    {"source_id":"ACME-STORAGE-A","target_id":"ACME-ESXI-01","relation_type":"SERVES"},
    {"source_id":"ACME-ESXI-01","target_id":"ACME-SVC-PAYMENTS","relation_type":"HOSTS"},
    {"source_id":"ACME-SAN-FABRIC-B","target_id":"ACME-STORAGE-A","relation_type":"REDUNDANT_PATH"},
]
IMPACT={"root":"ACME-SAN-FABRIC-A","affected":[
    {"node_id":"ACME-SAN-FABRIC-A"},{"node_id":"ACME-STORAGE-A"},
    {"node_id":"ACME-ESXI-01"},{"node_id":"ACME-SVC-PAYMENTS"}]}
EVENTS=[
    ("01","Détection","Erreur de port FC détectée","Événement synthétique"),
    ("02","Topologie","Dépendances SAN / stockage / ESXi / Paiement","Données inventées pour cette démo"),
    ("03","Analyse","Hypothèse de perturbation multipath","Aucune inférence IA réelle"),
    ("04","Critic","Validation refusée (simulation)","Aucune invocation d'un modèle"),
    ("05","Policy","BLOCKED — approbation humaine nécessaire","Aucun effet ni action LIVE"),
]
def build():
    graph={"nodes":NODES,"edges":EDGES}
    timeline='<div class="timeline">'+''.join(
      '<article class="event"><small>Étape '+n+'</small><h3>'+title+'</h3><p>'+desc+'</p><span class="chip">'+label+'</span></article>'
      for n,title,desc,label in EVENTS)+'</div>'
    intro=panel("Conditions de démonstration",
      '<p><strong>DONNÉES 100 % SYNTHÉTIQUES</strong> — graphe ACME fictif, événements inventés, '
      'sans API, sans jeton et sans remédiation réelle. '
      'Les équipements listés ne proviennent pas du registre opérationnel.</p>')
    return shell("/twin","Digital Twin ACME — DEMO OFFLINE",
      "Scénario de dégradation SAN et dépendances métiers — maquette interactive sans infrastructure.",
      intro+graph_panel(graph,impact=IMPACT)+panel("Chronologie explicative — simulation",timeline)
      +panel("Preuve et limites",pretty({"data_origin":"SYNTHETIC_FIXTURE",
      "worker_temporal_tested":False,"llm_inference_tested":False,
      "production_qualified":False,"automated_remediation":False})),
      mode="DEMO OFFLINE SYNTHETIC")
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"reports"/"acme-demo-offline.html")
    args=parser.parse_args()
    dest=args.output.resolve()
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(build(),encoding="utf-8")
    print("ACME_OFFLINE_DEMO_HTML="+str(dest))
    print("ACME_OFFLINE_DEMO_DATA=SYNTHETIC_ONLY")
    print("ACME_OFFLINE_DEMO_LIVE_EFFECTS=NONE")
if __name__=="__main__":
    main()
