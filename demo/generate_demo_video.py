"""Generate a complete, deterministic AIOps demo video from synthetic STAR scenes.

Requires Playwright + Chromium and ffmpeg. espeak-ng is optional (French narration).
No application endpoints are contacted. The output is explicitly marked SIMULATION.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from html import escape

SCENES = [
    ("01", "DÉTECTION", "Une alerte de perte de redondance SAN est simulée.", "GRAFANA", "ALERTE P1", "Détection", "Événement synthétique — aucun runtime interrogé."),
    ("02", "CORRÉLATION", "Les événements Fibre Channel et multipath sont rapprochés dans une chronologie fictive.", "N8N", "CORRÉLATION", "Corrélation", "Flux illustratif — aucune exécution n8n revendiquée."),
    ("03", "CONTEXTE & CMDB", "Le scénario présente les dépendances applicatives et les ressources supposées impactées.", "CMDB", "IMPACT À ÉVALUER", "Contexte", "Dépendances de démonstration — non vérifiées en production."),
    ("04", "ANALYSE IA", "Une hypothèse de cause est confrontée à une contre-analyse critique.", "DGX / IA", "HYPOTHÈSE", "Analyse et critique", "Texte narratif synthétique — aucune attestation DGX."),
    ("05", "INCIDENT GLPI", "La démonstration montre les informations qu’un ticket d’incident devrait contenir.", "GLPI", "TICKET ILLUSTRATIF", "Ticket", "Aucun ticket GLPI n’est créé ni modifié."),
    ("06", "VALIDATION HUMAINE", "La politique impose une validation explicite avant toute action sensible.", "HITL / POLICY", "APPROBATION REQUISE", "Décision humaine", "Aucune approbation réelle n’est demandée ou enregistrée."),
    ("07", "REMÉDIATION SIMULÉE", "Une action de remédiation fictive est présentée sans envoyer de commande.", "SIMULATEUR", "DRY-RUN", "Remédiation", "Aucune commande ni modification de production."),
    ("08", "VÉRIFICATION", "Les indicateurs avant et après sont comparés à titre illustratif.", "OBSERVABILITÉ", "RÉSULTAT SIMULÉ", "Vérification", "Aucune restauration réelle n’est affirmée."),
    ("09", "BILAN & PREUVES", "Le bilan distingue les éléments simulés, les preuves absentes et les qualifications restantes.", "EVIDENCE CENTER", "SIMULATION — NON LIVE", "Bilan", "Les captures ne constituent pas une preuve de runtime."),
]
WIDTH, HEIGHT = 1920, 1080
DURATION = 8

def scenes_for(scenario: str) -> list[tuple[str, ...]]:
    if scenario == "SAN_FABRIC_P1":
        return list(SCENES)
    if scenario != "PAYMENTS_P2":
        raise ValueError(f"Scénario inconnu : {scenario}")
    replacements = {
        0: ("01", "DÉGRADATION PAYMENTS", "Une hausse synthétique de latence et d'erreurs Payments est présentée comme incident P2.", "GRAFANA", "ALERTE P2", "Détection", "Événement synthétique — aucun runtime interrogé."),
        1: ("02", "CORRÉLATION DES SIGNAUX", "La chronologie fictive rapproche latence, erreurs applicatives et événements d'infrastructure.", "N8N", "CORRÉLATION P2", "Corrélation", "Flux illustratif — aucune exécution n8n revendiquée."),
        2: ("03", "CONTEXTE PAYMENTS", "Le scénario expose les dépendances Payments et les pistes stockage ou applicatives à départager.", "CMDB", "IMPACT À ÉVALUER", "Contexte", "Dépendances de démonstration — non vérifiées en production."),
        3: ("04", "HYPOTHÈSES & CRITIQUE", "L'analyse compare des hypothèses de cause sans présenter de diagnostic réel ni de réponse DGX attestée.", "DGX / IA", "HYPOTHÈSES P2", "Analyse et critique", "Texte narratif synthétique — aucune attestation DGX."),
        6: ("07", "TEST DE REMÉDIATION SIMULÉ", "Une action fictive de diagnostic et de remédiation est présentée sans envoyer de commande.", "SIMULATEUR", "DRY-RUN P2", "Remédiation", "Aucune commande ni modification de production."),
        7: ("08", "COMPARAISON DES SLO", "Les valeurs illustratives avant et après sont comparées sans supposer un retour à la normale.", "OBSERVABILITÉ", "RÉSULTAT SIMULÉ", "Vérification", "Aucune restauration réelle n’est affirmée."),
    }
    return [replacements.get(i, scene) for i, scene in enumerate(scenes)]


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Commande requise introuvable : {name}")
    return path


def scene_html(scene: tuple[str, ...], index: int, total: int) -> str:
    number, title, narration, system, status, phase, disclaimer = scene
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width={WIDTH},initial-scale=1">
<style>
*{{box-sizing:border-box}}html,body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;overflow:hidden}}
body{{font:30px 'Arial',sans-serif;color:#f2f7ff;background:radial-gradient(ellipse at 75% 20%,#173e60 0,#0b1c30 45%,#06101d 100%);padding:78px}}
.top{{display:flex;justify-content:space-between;color:#7ec8ff;font-size:24px;letter-spacing:4px}}
h1{{font-size:66px;line-height:1.05;max-width:1300px;margin:92px 0 30px}}
p{{line-height:1.5;max-width:1320px;color:#c4d7e8}}
.card{{margin-top:50px;border:2px solid #2e5474;border-radius:24px;background:#102940;padding:36px 42px;width:1420px}}
.kicker{{font-size:22px;letter-spacing:3px;color:#8ccfff}}
.status{{font-size:38px;font-weight:bold;color:#f5c86a;margin-top:18px}}
.bottom{{position:absolute;left:78px;right:78px;bottom:55px;border-top:1px solid #29445d;padding-top:22px;display:flex;justify-content:space-between;color:#93aabe;font-size:20px}}
.pill{{border:1px solid #d7a94e;color:#ffd67a;border-radius:8px;padding:12px 18px;font-size:20px;letter-spacing:2px}}
.bar{{height:7px;background:#20384e;margin-top:30px}}.fill{{height:7px;width:{int((index+1)/total*100)}%;background:#64c2ff}}
</style></head><body>
<div class="top"><span>AIOPS · DEMO CENTER</span><span class="pill">MODE DÉMONSTRATION · SIMULATION</span></div>
<h1>{escape(title)}</h1><p>{escape(narration)}</p>
<div class="card"><div class="kicker">{escape(system)} · PARCOURS STAR</div><div class="status">{escape(status)}</div><p>{escape(disclaimer)}</p></div>
<div class="bar"><div class="fill"></div></div>
<div class="bottom"><span>{escape(phase)} · SCÉNARIO SYNTHÉTIQUE</span><span>SCÈNE {index+1:02d} / {total:02d}</span><span>AIOPS · READ-ONLY</span></div>
</body></html>"""


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def generate(output: Path, scenario: str = "SAN_FABRIC_P1", voice: bool = True) -> dict:
    ffmpeg = require_command("ffmpeg")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright Python absent. Installez-le puis installez Chromium.") from exc

    scenes = scenes_for(scenario)
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("Le répertoire de sortie ne doit pas être un lien symbolique.")
    video = output / "AIOps-Demo-Complete.mp4"
    subtitles = output / "AIOps-Demo-Complete.srt"
    report_path = output / "AIOps-Demo-Complete.manifest.json"
    for path in (video, subtitles, report_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refus d'écraser un fichier existant : {path}")
    with tempfile.TemporaryDirectory(prefix="aiops-demo-video-") as tmp:
        root = Path(tmp)
        frames = root / "frames"
        frames.mkdir()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            for index, scene in enumerate(SCENES):
                page.set_content(scene_html(scene, index, len(scenes)), wait_until="load")
                page.screenshot(path=str(frames / f"{index:03d}.png"), full_page=True, animations="disabled")
            browser.close()

        concat = root / "video.ffconcat"
        lines = ["ffconcat version 1.0"]
        for index in range(len(scenes)):
            lines += [f"file '{(frames / f'{index:03d}.png').as_posix()}'", f"duration {DURATION}"]
        lines.append(f"file '{(frames / f'{len(SCENES)-1:03d}.png').as_posix()}'")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

        srt_lines = []
        for i, scene in enumerate(SCENES):
            start, end = i * DURATION, (i + 1) * DURATION
            def stamp(seconds: int) -> str:
                return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d},000"
            srt_lines.extend([str(i+1), f"{stamp(start)} --> {stamp(end)}", scene[2], scene[6], ""])
        subtitles.write_text("\ufeff" + "\n".join(srt_lines), encoding="utf-8")

        audio_args: list[str] = []
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        narration_status = "disabled"
        audio_file = root / "narration.wav"
        if voice and espeak:
            wavs = []
            for i, scene in enumerate(SCENES):
                raw_wav = root / f"voice-raw-{i:02d}.wav"
                wav = root / f"voice-{i:02d}.wav"
                run([espeak, "-v", "fr", "-s", "145", "-w", str(raw_wav), scene[2] + " " + scene[6]])
                # Keep every narration segment aligned to its 8-second scene.
                run([ffmpeg, "-y", "-i", str(raw_wav), "-af", f"apad=pad_dur={DURATION},atrim=duration={DURATION}",
                     "-ac", "2", "-ar", "44100", str(wav)])
                wavs.append(wav)
            audio_concat = root / "audio.ffconcat"
            audio_concat.write_text("ffconcat version 1.0\\n" + "".join(f"file '{p.as_posix()}'\\n" for p in wavs), encoding="utf-8")
            run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat), "-ac", "2", "-ar", "44100", str(audio_file)])
            audio_args = ["-i", str(audio_file)]
            narration_status = "espeak_french_scene_aligned"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), *audio_args,
             "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
             "-crf", "21", *(["-c:a", "aac", "-shortest"] if audio_args else ["-an"]),
             "-movflags", "+faststart", str(video)])

    manifest = {
        "schema": "aiops-demo-video-manifest-v1",
        "scenario": scenario,
        "provenance": "SIMULATED_TARGET",
        "scene_count": len(SCENES),
        "duration_target_seconds": len(SCENES) * DURATION,
        "video": video.name,
        "subtitles": subtitles.name,
        "narration": narration_status,
        "runtime_authenticated": False,
        "dgx_independently_attested": False,
        "live_execution_qualified": False,
        "live_action_authorized": False,
        "notice": "Complete synthetic demo; no runtime endpoint or production action was used.",
    }
    report_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a complete synthetic AIOps demo video")
    parser.add_argument("--out", type=Path, default=Path("dist/aiops-demo-video"))
    parser.add_argument("--scenario", choices=("SAN_FABRIC_P1", "PAYMENTS_P2"), default="SAN_FABRIC_P1")
    parser.add_argument("--no-voice", action="store_true", help="Create video and subtitles without optional French TTS")
    args = parser.parse_args()
    manifest = generate(args.out, args.scenario, not args.no_voice)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
