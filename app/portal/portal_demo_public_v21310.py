"""Public synthetic-only demo center and opt-in local video renderer.

Video generation never contacts operational services and is disabled unless
AIOPS_DEMO_VIDEO_ENABLED=true is explicitly set for the portal process.
"""
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = Path(__file__).resolve().parent / "public_demo_assets" / "AIOPS-EXECUTIVE-THEATER-PUBLIC.html"
RUNS_ROOT = REPO_ROOT / "dist" / "demo-video-runs"
SCENARIOS = {"SAN_FABRIC_P1", "PAYMENTS_P2"}
ARTIFACTS = {
    "video": ("AIOps-Demo-Complete.mp4", "video/mp4"),
    "subtitles": ("AIOps-Demo-Complete.srt", "application/x-subrip"),
    "manifest": ("AIOps-Demo-Complete.manifest.json", "application/json"),
}
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self' 'unsafe-inline' data:; connect-src 'self'; frame-ancestors 'self'",
}
_jobs = {}
_jobs_lock = threading.Lock()
_recent_starts = []
MAX_CONCURRENT_JOBS = 1
MIN_START_INTERVAL_SECONDS = 30
MAX_STARTS_PER_HOUR = 8


def _video_enabled():
    return os.getenv("AIOPS_DEMO_VIDEO_ENABLED", "").lower() == "true"


def _job_snapshot(job_id, job):
    proc = job["process"]
    code = proc.poll()
    if code is not None and job["status"] == "running":
        job["status"] = "completed" if code == 0 else "failed"
        job["return_code"] = code
        job["finished_at"] = int(time.time())
        manifest = job["output"] / ARTIFACTS["manifest"][0]
        if code == 0:
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                video = job["output"] / ARTIFACTS["video"][0]
                subtitles = job["output"] / ARTIFACTS["subtitles"][0]
                def sha256_file(path):
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        while True:
                            chunk = stream.read(1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                    return digest.hexdigest()
                files_valid = all(
                    path.is_file() and not path.is_symlink()
                    and path.resolve().parent == job["output"].resolve()
                    and path.stat().st_size > 0
                    for path in (manifest, video, subtitles)
                )
                valid = (
                    files_valid
                    and data.get("provenance") == "SIMULATED_TARGET"
                    and data.get("runtime_authenticated") is False
                    and data.get("dgx_independently_attested") is False
                    and data.get("live_execution_qualified") is False
                    and data.get("live_action_authorized") is False
                    and data.get("scenario") == job["scenario"]
                    and data.get("scene_count") == 9
                    and data.get("duration_target_seconds") == 72
                    and data.get("resolution") == "1920x1080"
                    and data.get("video_size_bytes") == video.stat().st_size
                    and data.get("video_sha256") == sha256_file(video)
                    and data.get("subtitles_sha256") == sha256_file(subtitles)
                )
                if not valid:
                    job["status"] = "failed"
                    job["error"] = "manifest_or_artifact_integrity_validation_failed"
            except (OSError, ValueError, TypeError):
                job["status"] = "failed"
                job["error"] = "manifest_missing_or_invalid"
    return {
        "job_id": job_id,
        "scenario": job["scenario"],
        "status": job["status"],
        "created_at": job["created_at"],
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "provenance": "SIMULATED_TARGET",
        "runtime_authenticated": False,
        "dgx_independently_attested": False,
        "live_execution_qualified": False,
        "live_action_authorized": False,
        "artifacts": {
            name: f"/demo/video/{job_id}/artifact/{name}"
            for name in ARTIFACTS
        } if job["status"] == "completed" else {},
    }


@router.get("/demo/", response_class=HTMLResponse)
def catalog():
    html = """<!doctype html><html lang="fr"><meta charset="utf-8"><title>AIOps Demo Center</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body{font:16px system-ui;max-width:920px;margin:2rem auto;padding:1rem;background:#101827;color:#e8eef8}
    .card{background:#1d2a3d;padding:1rem 1.2rem;border-radius:12px;margin:1rem 0}
    button,select{font:inherit;padding:.65rem .9rem;border-radius:8px;border:1px solid #7185a5}
    button{cursor:pointer;background:#6dd6bb;color:#102032;font-weight:700}button:disabled{opacity:.5;cursor:wait}
    a{color:#8bd5ff}code{overflow-wrap:anywhere}.muted{color:#bdc9da}
    </style>
    <a href="/demo-studio">← Demo Studio</a> · <a href="/">Portail AIOps</a>
    <h1>Demo Center — vidéo de démonstration</h1>
    <div class="card"><strong>FICTIF / SIMULATION UNIQUEMENT</strong>
    <p class="muted">Génération locale d'un film de 72 secondes en 1080p avec sous-titres et manifeste de provenance.
    Aucun endpoint AIOps, Grafana, n8n, GLPI ou DGX n'est appelé ; aucune remédiation réelle n'est déclenchée.</p>
    <label for="scenario">Scénario : </label><select id="scenario">
    <option value="SAN_FABRIC_P1">SAN Fabric — incident P1</option>
    <option value="PAYMENTS_P2">Payments — incident P2</option></select>
    <button id="start" type="button">Générer la vidéo complète</button>
    <p id="status" role="status" aria-live="polite">Prêt. La génération est désactivée par défaut côté serveur.</p>
    <div id="artifacts"></div></div>
    <div class="card"><h2>Storyboard STAR en lecture seule</h2>
    <p><a href="/demo/star">Ouvrir Executive Theater STAR</a></p>
    <p class="muted">Les replays Core et Evidence opérationnels restent protégés et désactivés.</p></div>
    <script>
    (() => {
      const start=document.getElementById('start'), scenario=document.getElementById('scenario');
      const status=document.getElementById('status'), artifacts=document.getElementById('artifacts');
      let timer=null;
      function showFiles(files){
        artifacts.replaceChildren();
        const labels={video:'Télécharger la vidéo MP4',subtitles:'Télécharger les sous-titres SRT',manifest:'Télécharger le manifeste JSON'};
        for(const [key,url] of Object.entries(files)){
          const p=document.createElement('p'), a=document.createElement('a');
          a.href=url;a.textContent=labels[key]||key;p.appendChild(a);artifacts.appendChild(p);
        }
      }
      async function poll(id){
        try{
          const response=await fetch('/demo/video/'+encodeURIComponent(id),{cache:'no-store'});
          const data=await response.json();
          if(!response.ok) throw new Error(data.detail||'status_unavailable');
          status.textContent='Scénario '+data.scenario+' — état : '+data.status;
          if(data.status==='completed'){showFiles(data.artifacts);start.disabled=false;return;}
          if(data.status==='failed'){status.textContent+=' — génération échouée. Vérifier les dépendances du serveur.';start.disabled=false;return;}
          timer=setTimeout(()=>poll(id),1500);
        }catch(e){status.textContent='Suivi indisponible : '+String(e.message||e);start.disabled=false;}
      }
      start.addEventListener('click',async()=>{
        if(timer)clearTimeout(timer);
        start.disabled=true;artifacts.replaceChildren();status.textContent='Demande de génération…';
        try{
          const response=await fetch('/demo/video',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:scenario.value})});
          const data=await response.json();
          if(!response.ok) throw new Error(data.detail||'generation_not_available');
          status.textContent='Génération démarrée — '+data.job_id;
          poll(data.job_id);
        }catch(e){status.textContent='Impossible de démarrer : '+String(e.message||e);start.disabled=false;}
      });
    })();
    </script></html>"""
    return HTMLResponse(html, headers=HEADERS)


@router.post("/demo/video")
def start_video(request: dict):
    if not isinstance(request, dict) or set(request) - {"scenario"}:
        raise HTTPException(422, "invalid_video_request")
    scenario = request.get("scenario", "SAN_FABRIC_P1")
    if not isinstance(scenario, str) or scenario not in SCENARIOS:
        raise HTTPException(422, "scenario_not_allowed")
    if not _video_enabled():
        raise HTTPException(503, "video_generation_disabled_set_AIOPS_DEMO_VIDEO_ENABLED_true")
    if not (REPO_ROOT / "demo" / "generate_demo_video.py").is_file():
        raise HTTPException(503, "video_generator_unavailable")
    with _jobs_lock:
        now = time.time()
        _recent_starts[:] = [stamp for stamp in _recent_starts if now - stamp < 3600]
        if _recent_starts and now - _recent_starts[-1] < MIN_START_INTERVAL_SECONDS:
            raise HTTPException(429, "video_generation_rate_limited")
        if len(_recent_starts) >= MAX_STARTS_PER_HOUR:
            raise HTTPException(429, "video_generation_hourly_limit")
        active = [j for j in _jobs.values() if j["status"] == "running" and j["process"].poll() is None]
        if len(active) >= MAX_CONCURRENT_JOBS:
            raise HTTPException(409, "video_generation_already_running")
        job_id = uuid.uuid4().hex
        output = RUNS_ROOT / job_id
        if RUNS_ROOT.is_symlink():
            raise HTTPException(503, "unsafe_output_directory")
        RUNS_ROOT.mkdir(parents=True, exist_ok=True)
        if RUNS_ROOT.resolve() != (REPO_ROOT.resolve() / "dist" / "demo-video-runs"):
            raise HTTPException(503, "unsafe_output_directory")
        output.mkdir(mode=0o750)
        if output.is_symlink() or output.resolve().parent != RUNS_ROOT.resolve():
            raise HTTPException(503, "unsafe_output_directory")
        log = (output / "generator.log").open("xb")
        command = [
            sys.executable, "-m", "demo.generate_demo_video",
            "--scenario", scenario, "--out", str(output),
        ]
        try:
            proc = subprocess.Popen(
                command, cwd=str(REPO_ROOT), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, close_fds=True,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except OSError as exc:
            log.close()
            raise HTTPException(503, "video_generator_could_not_start") from exc
        log.close()
        _recent_starts.append(now)
        _jobs[job_id] = {
            "process": proc, "output": output, "scenario": scenario,
            "status": "running", "created_at": int(now),
        }
        return JSONResponse(_job_snapshot(job_id, _jobs[job_id]), status_code=202, headers=HEADERS)


@router.get("/demo/video/{job_id}")
def video_status(job_id: str):
    if not re_full_hex_id(job_id):
        raise HTTPException(404, "video_job_not_found")
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "video_job_not_found")
        return JSONResponse(_job_snapshot(job_id, job), headers=HEADERS)


def re_full_hex_id(value):
    return len(value) == 32 and all(ch in "0123456789abcdef" for ch in value)


@router.get("/demo/video/{job_id}/artifact/{artifact}")
def video_artifact(job_id: str, artifact: str):
    if not re_full_hex_id(job_id) or artifact not in ARTIFACTS:
        raise HTTPException(404, "video_artifact_not_found")
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "video_job_not_found")
        snapshot = _job_snapshot(job_id, job)
        if snapshot["status"] != "completed":
            raise HTTPException(409, "video_artifact_not_ready")
        filename, media_type = ARTIFACTS[artifact]
        path = job["output"] / filename
        if path.is_symlink() or not path.is_file() or path.resolve().parent != job["output"].resolve():
            raise HTTPException(404, "video_artifact_not_found")
        return FileResponse(path, media_type=media_type, filename=filename, headers=HEADERS)


@router.get("/demo/star")
def star():
    if not ASSET.is_file() or ASSET.is_symlink():
        raise HTTPException(503, "synthetic demo asset unavailable")
    return FileResponse(ASSET, media_type="text/html", headers=HEADERS)
