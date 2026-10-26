# STAR screenshot manifest — stricter offline ingestion

**Status:** source-level hardening; isolated synthetic tests only. This is not runtime authentication or a production release.

## Defect and fix

The historical/cumulative screenshot collector already checked PNG structure, SHA-256, run identity and nine STAR cues. Its CLI reader used ordinary `json.loads`, so a JSON object containing duplicate keys could be interpreted with last-key-wins semantics. Its path handling also followed a symlink for the manifest and read the declared size before opening the file.

`demo/star_capture_evidence.py` now reads a bounded byte buffer from a regular file, refuses a final symlink (and uses `O_NOFOLLOW` where supported), verifies UTF-8, and rejects duplicate JSON keys at every nesting level. It validates that the capture map and each capture record are objects before field access, returning controlled `ValueError` failures rather than leaking incidental `AttributeError`/JSON parsing details. The screenshot byte hash is still computed on the actual PNG file, not trusted from its manifest. The shared PNG verifier now opens once, refuses final-component symlinks, requires a regular file from `fstat`, and compares descriptor metadata before/after parsing so a concurrent append, truncation or modification fails closed. Validation and digesting use that same open descriptor rather than a pre-open path-size check.

## Interface and dependencies

- Input: a local JSON manifest and a local evidence root; no HTTP, browser launch, Docker, credentials, application API or database.
- Output: sanitized integrity summary, with `runtime_authenticated=false`, `business_validated=false`, `human_approval_authenticated=false`, and `live_action_authorized=false`.
- Dependencies: Python standard library, `demo.star_snapshot_choreography`, and `demo.star_png_integrity`.
- Candidate package: the source, direct dependencies, workflow, documentation and regression tests are explicitly admitted to the cumulative source subset and checked byte-for-byte.

## Qualification

Regression tests cover duplicate keys at root and nested record level, symlink refusal, bounded size, invalid UTF-8 and non-object capture records. The existing synthetic PNG suite remains byte-level structure/integrity only. A passing digest does not attest the image source, authenticated session, expected application screen, timestamp origin, or business event.


## Malformed metadata shape handling (26 October 2026)

`validate_capture` is also called by offline adapters on operator-supplied metadata. It now checks that each capture is a mapping, the cue name is a string, and `proof_state` is a string before dictionary lookup or set membership. JSON arrays/objects in these fields are rejected with a controlled `ValueError` instead of leaking incidental `AttributeError`/`TypeError`. The same guard is exercised through `build_timeline`. This is input-shape validation only; it does not authenticate timestamps, browser sessions, source applications, or runtime execution.

## Safety and rollback

The module remains an offline verifier; the change performs no live capture and no external write. Rollback is source-only on the PR branch: revert this commit. Do not run historical F20.13 scripts against Debian or legacy application ports. Production remains blocked until authenticated runtime E2E, nine exact application checkpoints, independent event provenance, backup/restore and explicit release approval are qualified.

## PNG palette conformance (26 October 2026)

The byte-level verifier now also enforces palette constraints that can be established from the PNG chunk stream without decoding pixels: indexed-color images (color type 3) must declare `PLTE` before `IDAT`, and the number of palette entries cannot exceed `2**bit_depth`. Grayscale (type 0) and grayscale+alpha (type 4) images must not contain `PLTE`. The regression suite includes valid and invalid synthetic fixtures for these cases. The verifier still does not decompress image pixels, authenticate a browser session, or attest the application's origin; a passing result means bounded structural integrity only.


## Contrat du bridge navigateur : validation de forme et lecture bornée (26 octobre 2026)


`demo/star_browser_manifest_gate.py` rejette explicitement les contrats canoniques, types de noms, champs de service/vue/provenance et timestamps mal formés. La liste des fichiers est validée avant la déduplication afin qu'un tableau imbriqué ne provoque pas de `TypeError`. Les références canoniques sont validées même lorsque la liste de captures est vide.

Le lecteur bridge ouvre le répertoire puis le manifeste par descripteurs relatifs, refuse les liens symboliques finaux et les fichiers non réguliers, borne la lecture à 16 KiB et compare les métadonnées avant/après. Les plates-formes ne fournissant pas les primitives de non-suivi requises sont refusées explicitement. Le parseur refuse les clés dupliquées, UTF-8 invalide, imbrication excessive et constantes JSON non standard. Des tests ciblés couvrent ces refus.

Le kit cumulatif embarque dorénavant le module complet de bridge Chromium, son adaptateur de storyboard, le gate de replay lié à un SHA indépendant, les modules de réconciliation/identité, les tests et la documentation. La génération du kit est déclenchée par les changements de ces fichiers et exécute les suites de régression correspondantes. Ce changement n'authentifie pas les captures et ne qualifie pas le portail Debian.
