'use strict';
// Contract fixtures only; production adapter must be wired separately.
const base={schema:'aiops.mission-data.view.v2',mode:'PLATFORM',state:'AVAILABLE',data:{value:0},reason:null,provenance:{origin:'OBSERVED',domain:'PLATFORM_TECHNICAL',source:'mock-prometheus',source_sha256:null,observed_at:null,evaluated_at:1700000000,retrieved_at:1700000001,freshness:'UNKNOWN',tenant_acl_qualified:false,runtime_attested:false},coverage:{observed:1,expected:2,ratio:0.5}};
const fixture=(patch={},provenance={})=>({...structuredClone(base),...patch,provenance:{...base.provenance,...provenance}});
module.exports={valid:[
 {id:'zero',value:fixture()},
 {id:'null',value:fixture({data:{value:null}})},
 {id:'qualified-empty',value:fixture({mode:'OPERATIONAL',data:[]},{domain:'BUSINESS',tenant_acl_qualified:true})},
 {id:'denied',value:fixture({mode:'OPERATIONAL',state:'UNKNOWN',data:null,reason:'TENANT_ACL_NOT_QUALIFIED'},{domain:'BUSINESS'})},
], invalid:[
 {id:'ratio-mismatch',value:fixture({coverage:{observed:1,expected:2,ratio:1}})},
 {id:'zero-expected',value:fixture({coverage:{observed:0,expected:0,ratio:0}})},
 {id:'denied-as-empty',value:fixture({state:'UNKNOWN',data:[],reason:'AGGREGATE_AUTHORIZATION_NOT_QUALIFIED'})},
 {id:'fresh-without-observation',value:fixture({}, {freshness:'FRESH'})},
 {id:'synthetic-operational',value:fixture({mode:'OPERATIONAL'}, {origin:'SYNTHETIC'})},
 {id:'business-without-acl',value:fixture({mode:'OPERATIONAL'}, {domain:'BUSINESS'})},
 {id:'aggregate-without-grant',value:fixture({}, {domain:'PLATFORM_AGGREGATE'})},
], weighted:{parts:[{observed:1,expected:2},{observed:0,expected:8}],expected:{observed:1,expected:10,ratio:0.1}},identity:{expected:{incident_id:'mock-i',run_id:'mock-r',source_sha256:'a'.repeat(64)},differentRun:{incident_id:'mock-i',run_id:'other-r',source_sha256:'a'.repeat(64)},receipt_sha256:'b'.repeat(64)}};
