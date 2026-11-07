#!/usr/bin/env bash
# FS1138: GLPI authenticated API discovery using existing technical token.
# No tickets created; no secret contents printed or copied to host.
set -euo pipefail
echo "FS1138_MODE=AUTHENTICATED_GLPI_API_READ_ONLY"
echo "FS1138_PRODUCTION_TICKETS_CREATED=0"
echo "FS1138_PORTAL_7777_MUTATION=NONE"
docker inspect aiops2-rebuild-glpi --format '{{.State.Running}}' | grep -qx true
docker exec -i aiops2-rebuild-glpi php <<'PHP'
<?php
error_reporting(0);
function out($x) { echo json_encode($x,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE).PHP_EOL; }
$file='/var/glpi/aiops-tech-api.token';
if (!is_readable($file)) { out(['type'=>'fatal','code'=>'TECH_TOKEN_FILE_UNREADABLE']); exit(2); }
$raw=trim(file_get_contents($file));
if ($raw==='') { out(['type'=>'fatal','code'=>'TECH_TOKEN_FILE_EMPTY']); exit(2); }
$parsed=json_decode($raw,true);
$userToken='';
$appToken='';
if (is_array($parsed)) {
  foreach (['user_token','userToken','token','api_token'] as $key) {
    if (isset($parsed[$key]) && is_string($parsed[$key])) { $userToken=trim($parsed[$key]); break; }
  }
  foreach (['app_token','appToken'] as $key) {
    if (isset($parsed[$key]) && is_string($parsed[$key])) { $appToken=trim($parsed[$key]); break; }
  }
} else {
  // A single-line file is treated as a user token; other formats are not guessed.
  if (!str_contains($raw,"\n") && !str_contains($raw,"\r") && strlen($raw)<=512) $userToken=$raw;
}
if ($userToken==='') {
  out(['type'=>'diagnostic','code'=>'TOKEN_FORMAT_UNRECOGNIZED','file_exists'=>true,
       'json_object'=>is_array($parsed),'mutation'=>'NONE']);
  exit(0);
}
out(['type'=>'configuration','file_exists'=>true,'user_token_present'=>true,
     'app_token_present'=>($appToken!==''),'secret_values_exposed'=>false]);
function callApi($method,$path,$headers,$body=null) {
  $ch=curl_init('http://127.0.0.1'.$path);
  curl_setopt_array($ch,[
    CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,
    CURLOPT_CONNECTTIMEOUT=>4,CURLOPT_TIMEOUT=>12,
    CURLOPT_CUSTOMREQUEST=>$method,CURLOPT_HTTPHEADER=>$headers
  ]);
  if ($body!==null) curl_setopt($ch,CURLOPT_POSTFIELDS,$body);
  $data=curl_exec($ch);
  $code=curl_getinfo($ch,CURLINFO_HTTP_CODE);
  $error=curl_errno($ch);
  curl_close($ch);
  return [$code,$error,is_string($data)?json_decode($data,true):null];
}
$headers=['Authorization: user_token '.$userToken,'Content-Type: application/json'];
if ($appToken!=='') $headers[]='App-Token: '.$appToken;
$routes=['/apirest.php/initSession','/api.php/v1/initSession'];
$session='';
$selected='';
foreach ($routes as $route) {
  [$status,$error,$data]=callApi('GET',$route,$headers);
  $ok=($status===200 && is_array($data) && !empty($data['session_token']));
  out(['type'=>'authentication_probe','path'=>$route,'http_status'=>$status,
       'transport_error'=>($error!==0),'session_established'=>$ok,
       'response_code'=>is_array($data)?($data[0]??null):null]);
  if ($ok) { $session=$data['session_token']; $selected=$route; break; }
}
if ($session==='') {
  out(['type'=>'summary','result'=>'NOT_AUTHENTICATED',
       'reason'=>'API_PERMISSION_OR_TOKEN_FORMAT_OR_APP_TOKEN_CONFIGURATION',
       'tickets_created'=>0,'mutation'=>'NONE']);
  exit(0);
}
$base=substr($selected,0,-strlen('/initSession'));
$sessionHeaders=['Session-Token: '.$session,'Content-Type: application/json'];
if ($appToken!=='') $sessionHeaders[]='App-Token: '.$appToken;
foreach (['/getMyProfiles','/Ticket?range=0-0'] as $suffix) {
  [$status,$error,$data]=callApi('GET',$base.$suffix,$sessionHeaders);
  out(['type'=>'read_permission_probe','path'=>$base.$suffix,
       'http_status'=>$status,'transport_error'=>($error!==0),
       'read_allowed'=>($status>=200 && $status<300)]);
}
[$status,$error,$data]=callApi('GET',$base.'/killSession',$sessionHeaders);
out(['type'=>'summary','result'=>'AUTHENTICATED_READ_ONLY',
     'api_base'=>$base,'tickets_created'=>0,'mutation'=>'NONE']);
PHP
echo "FS1138_FINAL_STATUS=READ_ONLY_DIAGNOSTIC_COMPLETE"
