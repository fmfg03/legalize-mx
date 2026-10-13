from __future__ import annotations

if __package__:
    from . import validate_legal_authority as authority
    from . import validate_jurisprudence_grounding as grounding
else:
    import validate_legal_authority as authority
    import validate_jurisprudence_grounding as grounding

def evaluate_release_gates(*, bundle, root, grounding_policy, authority_policy, provider_registry, live_fixture=None):
    """Single gate boundary shared by the CLI and persistent backend."""
    legislation_chunks, jurisprudence_chunks = grounding.load_indexes(root)
    authority_result = authority.evaluate_bundle(
        bundle=bundle, root=root, policy=authority_policy,
        live_fixture=live_fixture, provider_registry=provider_registry,
    )
    supplemental = authority_result[3]
    grounding_result = grounding.evaluate_bundle(
        bundle=bundle, policy=grounding_policy,
        legislation_chunks=legislation_chunks, jurisprudence_chunks=jurisprudence_chunks,
        supplemental_legislation_chunks=supplemental["legislation_chunks"],
        supplemental_jurisprudence_chunks=supplemental["jurisprudence_chunks"],
    )
    return authority_result, grounding_result
