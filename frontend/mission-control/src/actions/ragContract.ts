export type RagCitation={doc_id:string;doc_sha256:string;asset:string;event_key:string;sample:string;runbook:string[];provenance:string};
export function qualifiedCitations(value:unknown,asset:string):RagCitation[]|null {
 if(!value||typeof value!=="object")return null;
 const d=value as Record<string,unknown>;
 if(d.schema!=="aiops.noc-demo-rag-drilldown.v1"||d.asset!==asset||d.state!=="SYNTHETIC_REFERENCE_ONLY"||d.data_classification!=="SYNTHETIC_SIMULATION_ONLY"||d.llm_inference_performed!==false||d.source_runtime_observed!==false||d.live_remediation_authorized!==false||!Array.isArray(d.citations)||!d.citations.length)return null;
 const digest=(x:unknown)=>typeof x==="string"&&/^[a-f0-9]{64}$/.test(x);
 if(!digest(d.catalog_sha256))return null;
 const seen=new Set<string>();
 for(const c of d.citations){
 if(!c||typeof c.doc_id!=="string"||!c.doc_id||seen.has(c.doc_id)||!digest(c.doc_sha256)||c.asset!==asset||c.provenance!=="SYNTHETIC_SIMULATION_ONLY"||typeof c.event_key!=="string"||typeof c.sample!=="string"||!c.sample.startsWith("DEMO ONLY:")||!Array.isArray(c.runbook)||!c.runbook.length||!c.runbook.every((s:unknown)=>typeof s==="string"&&s.length>0))return null;
 seen.add(c.doc_id);
 }
 return d.citations as RagCitation[];
}
export function searchCitations(rows:RagCitation[],question:string):RagCitation[]{
 const terms=question.toLowerCase().trim().split(/\s+/).filter(Boolean);
 return terms.length?rows.filter(c=>terms.every(t=>[c.doc_id,c.event_key,c.sample,...c.runbook].join(" ").toLowerCase().includes(t))):rows;
}
