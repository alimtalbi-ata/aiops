import {projectMetric,projectLegacyMetric,type View} from './data02-projection';
const v:View={schema:'aiops.mission-data.view.v2',mode:'PLATFORM',state:'AVAILABLE',data:0,reason:null,coverage:{observed:1,expected:2,ratio:.5},provenance:{origin:'OBSERVED',domain:'PLATFORM_TECHNICAL',source:'mock',source_sha256:null,observed_at:null,evaluated_at:100,retrieved_at:101,freshness:'FRESH',tenant_acl_qualified:false,runtime_attested:false}};
function check(ok:boolean){if(!ok)throw Error('DATA02 mock assertion failed');}
check(projectMetric(v,'operational').value===0);
check(projectMetric(v,'operational').freshness==='UNKNOWN');
check(projectMetric({...v,coverage:{observed:1,expected:2,ratio:1}},'operational').reason==='INVALID_COVERAGE');
check(projectMetric({...v,provenance:{...v.provenance,origin:'SYNTHETIC'}},'operational').value===null);
check(projectMetric({...v,mode:'OPERATIONAL',provenance:{...v.provenance,domain:'BUSINESS'}},'operational').reason==='TENANT_ACL_NOT_QUALIFIED');
check(projectMetric({...v,provenance:{...v.provenance,domain:'PLATFORM_AGGREGATE'}},'operational').reason==='AGGREGATE_AUTHORIZATION_NOT_QUALIFIED');
check(projectMetric({...v,state:'UNKNOWN',data:null,reason:'NO_SAMPLES'},'operational').reason==='NO_SAMPLES');
check(projectLegacyMetric(0,'mock').value===null);
console.log('DATA02 projection: 8 mock assertions passed');
