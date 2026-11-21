"""Evidence-backed, read-only explanation of ACME Analyst/Critic decisions."""
from html import escape


def _obj(value):
    return value if isinstance(value, dict) else {}


def _seq(value):
    return value if isinstance(value, list) else []


def render_critic_explanation(ledger):
    ledger = _obj(ledger)
    analyses = _seq(ledger.get("analyses"))
    critiques = _seq(ledger.get("critiques"))
    if not critiques:
        return '<p class="muted">Aucune critique enregistrée pour ce run. Aucune décision ne peut être déduite.</p>'
    critique = _obj(critiques[-1])
    output = _obj(critique.get("output"))
    analysis = _obj(_obj(analyses[-1]).get("output")) if analyses else {}
    checks = [_obj(x) for x in _seq(output.get("claim_checks"))]
    issues = [_obj(x) for x in _seq(output.get("issues") or critique.get("issues"))]
    supported = sum(x.get("supported") is True for x in checks)
    model = escape(str(critique.get("model") or "INCONNU"))
    rec = escape(str(output.get("final_recommendation") or "INCONNU"))
    severity = escape(str(analysis.get("severity") or "INCONNU"))
    validated = critique.get("validated") is True
    parts = [
        '<p><strong>Scénario synthétique, raisonnement IA réellement enregistré.</strong> '
        'Les preuves simulées ne décrivent pas un équipement physique réel.</p>',
        f'<p><strong>Modèle :</strong> {model} · '
        f'<strong>Sévérité Analyst :</strong> {severity} · '
        f'<strong>Critic :</strong> {"VALIDÉ" if validated else "NON VALIDÉ"} · '
        f'<strong>Recommandation :</strong> {rec}</p>',
        f'<p><strong>Affirmations soutenues :</strong> {supported}/{len(checks)}. '
        'Le niveau de confiance du modèle n’est pas une probabilité calibrée.</p>',
    ]
    if checks:
        parts.append('<h3>Vérification des affirmations</h3><ul>')
        for item in checks[:40]:
            label = "Étayée" if item.get("supported") is True else "Non étayée"
            claim = escape(str(item.get("claim") or "Affirmation sans description")[:600])
            refs = ", ".join(escape(str(ref)) for ref in _seq(item.get("supporting_evidence_ids"))[:15])
            parts.append(f'<li><strong>{label}</strong> — {claim} <small>Preuves : {refs or "aucune"}</small></li>')
        parts.append('</ul>')
    if issues:
        parts.append('<h3>Objections du Critic</h3><ul>')
        for issue in issues[:40]:
            code = escape(str(issue.get("code") or "UNKNOWN")[:100])
            desc = escape(str(issue.get("description") or "")[:800])
            refs = ", ".join(escape(str(ref)) for ref in _seq(issue.get("evidence_ids"))[:15])
            parts.append(f'<li><strong>{code}</strong> — {desc} <small>Preuves : {refs or "aucune"}</small></li>')
        parts.append('</ul>')
    unsafe = _seq(output.get("unsafe_actions"))
    if unsafe:
        parts.append(f'<p><strong>Actions contestées :</strong> {len(unsafe)}. '
                     'Aucune action ni approbation n’est proposée depuis cette page.</p>')
    if not ledger.get("policy_decisions"):
        parts.append('<p><strong>Policy :</strong> aucune décision Policy enregistrée ; '
                     'le Critic peut avoir interrompu le parcours avant cette étape.</p>')
    return "".join(parts)
