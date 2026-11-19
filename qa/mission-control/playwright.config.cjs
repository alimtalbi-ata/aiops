const {defineConfig}=require('@playwright/test');
const base=process.env.BASE_URL;
if(!base) throw Error('BASE_URL required');
const url=new URL(base);
if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||url.hash) throw Error('Unsafe BASE_URL');
module.exports=defineConfig({testDir:'../../tests/e2e/mission-control',workers:1,retries:0,timeout:30000,reporter:[['list'],['html',{outputFolder:'artifacts/html',open:'never'}],['json',{outputFile:'artifacts/results.json'}],['junit',{outputFile:'artifacts/junit.xml'}]],outputDir:'artifacts/results',use:{baseURL:url.origin,trace:'retain-on-failure',screenshot:'only-on-failure',video:'off'},projects:[{name:'chromium',use:{browserName:'chromium'}},{name:'mobile',use:{browserName:'chromium',viewport:{width:360,height:800},isMobile:true,hasTouch:true}}]});