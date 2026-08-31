"""Deterministic tests for KU2D Core Intelligence Quality Foundation v1."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "acquisition") not in sys.path:
    sys.path.insert(0, str(ROOT / "acquisition"))

from core_intelligence_quality import (
    CODEBOOK_SCHEMA,
    NON_AUTHORIZING,
    agreement_rate,
    assess_finding_verification,
    build_semantic_reliability_report,
    codebook_index,
    cohens_kappa,
    validate_analysis_projection,
    validate_analytical_memo,
    validate_codebook,
    validate_coding_chain,
    validate_evidence_chain,
    validate_independent_coding_record,
    validate_negative_case,
    validate_quality_loop,
)
from core_knowledge import validate_candidate_registry, validate_corpus, validate_taxonomy


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def must_fail(fn, message: str) -> None:
    try:
        fn()
        raise AssertionError(message)
    except ValueError:
        pass


taxonomy = load(ROOT / "config" / "core_knowledge_taxonomy.json")
codebook = load(ROOT / "config" / "core_knowledge_codebook.json")
corpus = load(ROOT / "config" / "reviewed_learning_corpus.json")
candidates = load(ROOT / "config" / "candidate_learning_evidence_registry.json")
fixtures = load(ROOT / "fixtures" / "core_intelligence_quality" / "reviewed_examples.json")

# QF1: the backward-compatible codebook and upstream authority records validate.
validate_taxonomy(taxonomy)
validate_corpus(corpus, taxonomy)
validate_candidate_registry(candidates)
assert codebook["schema"] == CODEBOOK_SCHEMA
validate_codebook(codebook, taxonomy)
index = codebook_index(codebook, taxonomy)

# QF2: every applicable code carries complete include/exclude/example/evidence guidance.
for code in codebook["codes"]:
    assert code["code_kind"] == "taxonomy_code"
    assert code["code_family"] in {
        "semantic_interpretation", "acquisition_technique", "failure_boundary_type",
    }
    assert code["definition"]
    for field in (
        "include_when", "exclude_when", "positive_examples", "counter_examples",
        "evidence_required",
    ):
        assert code[field]

# QF3: raw evidence remains visible and immutable after all later stages validate.
raw_snapshots = [deepcopy(item["raw_evidence"]) for item in fixtures["evidence_chains"]]
for chain in fixtures["evidence_chains"]:
    validate_evidence_chain(chain, codebook, taxonomy)
assert raw_snapshots == [item["raw_evidence"] for item in fixtures["evidence_chains"]]
assert all(item["raw_evidence"]["immutable"] is True for item in fixtures["evidence_chains"])

# QF4: descriptor, code, theme, interpretation, and decision remain different stages.
counter_chain = fixtures["evidence_chains"][0]
assert counter_chain["descriptors"][0]["kind"] == "descriptor"
assert counter_chain["codes"][0]["kind"] == "code"
assert counter_chain["themes"][0]["kind"] == "theme"
assert counter_chain["interpretations"][0]["kind"] == "interpretation"
assert counter_chain["decisions"][0]["kind"] == "decision"
assert counter_chain["descriptors"][0]["descriptor_id"] not in index

# QF5: a descriptor cannot silently masquerade as a taxonomy code.
descriptor_as_code = deepcopy(counter_chain)
descriptor_as_code["codes"][0]["kind"] = "descriptor"
must_fail(lambda: validate_evidence_chain(descriptor_as_code, codebook, taxonomy), "descriptor substituted for code")

# QF6: a broad interpretation/theme cannot reuse a code identifier.
theme_as_code = deepcopy(counter_chain)
theme_as_code["interpretations"][0]["interpretation_id"] = "SI-UNKNOWN-COUNTER"
must_fail(lambda: validate_evidence_chain(theme_as_code, codebook, taxonomy), "theme reused a code ID")

# QF7: prepared evidence must reference rather than replace raw evidence.
detached_preparation = deepcopy(counter_chain)
detached_preparation["prepared_evidence"]["raw_evidence_id"] = "RAW-NOT-RETAINED"
must_fail(lambda: validate_evidence_chain(detached_preparation, codebook, taxonomy), "prepared evidence lost raw link")

# QF8: reviewed historical first/second-cycle chains validate.
for coding in fixtures["coding_chains"]:
    validate_coding_chain(coding, codebook, taxonomy)

# QF9: second-cycle revision retains and explicitly references first-cycle coding.
iterative = fixtures["coding_chains"][0]
assert iterative["first_cycle"]["classification"] == "novel_pattern_candidate"
assert iterative["second_cycle"]["classification"] == "coded"
assert iterative["second_cycle"]["refines_coding_id"] == iterative["first_cycle"]["coding_id"]
assert iterative["first_cycle_retained"] is True

# QF10: overwriting or detaching first-cycle history fails closed.
overwritten = deepcopy(iterative)
overwritten["first_cycle_retained"] = False
must_fail(lambda: validate_coding_chain(overwritten, codebook, taxonomy), "first cycle was overwritten")
detached_second = deepcopy(iterative)
detached_second["second_cycle"]["refines_coding_id"] = "CODE-UNKNOWN"
must_fail(lambda: validate_coding_chain(detached_second, codebook, taxonomy), "second cycle lost first-cycle reference")

# QF11: no_existing_code_fits remains a valid, uncoerced ontology-open result.
open_case = deepcopy(fixtures["coding_chains"][2])
open_case["coding_chain_id"] = "KU2D-QC-NO-FIT"
open_case["first_cycle"].update({
    "coding_id": "CODE-NO-FIT", "classification": "no_existing_code_fits",
    "code_ids": [], "novel_pattern_candidate": False,
})
validate_coding_chain(open_case, codebook, taxonomy)

# QF12: novel_pattern_candidate is explicit and non-authoritative.
novel_case = deepcopy(open_case)
novel_case["coding_chain_id"] = "KU2D-QC-NOVEL"
novel_case["first_cycle"].update({
    "coding_id": "CODE-NOVEL", "classification": "novel_pattern_candidate",
    "novel_pattern_candidate": True,
})
validate_coding_chain(novel_case, codebook, taxonomy)
assert novel_case["boundaries"] == NON_AUTHORIZING

# QF13: ontology-open classifications cannot be coerced into a nearby code.
coerced = deepcopy(novel_case)
coerced["first_cycle"]["code_ids"] = ["SI-UNKNOWN-COUNTER"]
must_fail(lambda: validate_coding_chain(coerced, codebook, taxonomy), "novel observation was coerced")

# QF14: analytical memos retain support, counter-evidence, questions, and no authority.
for memo in fixtures["analytical_memos"]:
    validate_analytical_memo(memo)
    assert memo["supporting_evidence"]
    assert memo["counter_evidence_or_negative_cases"]
    assert memo["unresolved_questions"]
    assert memo["boundaries"] == NON_AUTHORIZING

# QF15: a memo cannot silently discard negative cases.
no_counter_memo = deepcopy(fixtures["analytical_memos"][0])
no_counter_memo["counter_evidence_or_negative_cases"] = []
must_fail(lambda: validate_analytical_memo(no_counter_memo), "memo discarded counter-evidence")

# QF16: negative/deviant cases are first-class, alternative-rich learning evidence.
for negative in fixtures["negative_cases"]:
    validate_negative_case(negative)
    assert negative["alternative_explanations"]
    assert negative["discarded_as_failure"] is False

# QF17: finding verification records raw return, provenance, alternatives, negative search, limitations, and human policy gate.
verified = assess_finding_verification(fixtures["finding_verifications"][0])
assert verified["gate_status"] == "eligible_for_separate_review"
assert verified["eligible_for_reviewed_core_knowledge"] is True
assert verified["promoted_to_reviewed_core_knowledge"] is False

# QF18: a required pending or failed gate withholds eligibility.
withheld = deepcopy(fixtures["finding_verifications"][0])
withheld["verification_id"] = "KU2D-FV-WITHHELD"
withheld["checks"][2]["result"] = "pending"
withheld["checks"][2]["evidence_references"] = []
withheld["eligible_for_reviewed_core_knowledge"] = False
assessed_withheld = assess_finding_verification(withheld)
assert assessed_withheld["gate_status"] == "withheld"

# QF19: skipped checks require an explicit justification.
unjustified = deepcopy(fixtures["finding_verifications"][0])
unjustified["checks"][4]["justification"] = ""
must_fail(lambda: assess_finding_verification(unjustified), "unjustified skipped gate was accepted")

# QF20: a policy finding cannot omit Human Confirmation.
no_human = deepcopy(fixtures["finding_verifications"][0])
no_human["checks"] = [item for item in no_human["checks"] if item["check"] != "human_confirmation"]
must_fail(lambda: assess_finding_verification(no_human), "policy finding omitted Human Confirmation")

# QF21: quality foundation can never auto-promote a finding.
promoted = deepcopy(fixtures["finding_verifications"][0])
promoted["promoted_to_reviewed_core_knowledge"] = True
must_fail(lambda: assess_finding_verification(promoted), "finding auto-promoted")

# QF22: independent coding records preserve blinded coder separation without fabricated Assistant/Human labels.
for record in fixtures["independent_coding_records"]:
    validate_independent_coding_record(record, codebook, taxonomy)
    assert record["coder"]["coder_type"] == "deterministic_fixture"
    assert record["agreement_status"] == "not_compared"
assert len({item["coder"]["coder_id"] for item in fixtures["independent_coding_records"]}) == 2

# QF23: disagreement explicitly requires adjudication.
disagreement = deepcopy(fixtures["independent_coding_records"][0])
disagreement["agreement_status"] = "disagreement"
disagreement["adjudication_needed"] = False
must_fail(lambda: validate_independent_coding_record(disagreement, codebook, taxonomy), "disagreement omitted adjudication")
disagreement["adjudication_needed"] = True
validate_independent_coding_record(disagreement, codebook, taxonomy)

# QF24: agreement rate preserves sample size and disagreement cases.
pairs = [
    {"sample_or_episode_id": "S1", "labels_a": ["A"], "labels_b": ["A"]},
    {"sample_or_episode_id": "S2", "labels_a": ["B"], "labels_b": ["A"]},
    {"sample_or_episode_id": "S3", "labels_a": ["B"], "labels_b": ["B"]},
    {"sample_or_episode_id": "S4", "labels_a": ["A"], "labels_b": ["A"]},
]
agreement = agreement_rate(pairs)
assert agreement["sample_size"] == 4
assert agreement["agreement_rate"] == 0.75
assert [item["sample_or_episode_id"] for item in agreement["disagreement_cases"]] == ["S2"]

# QF25: Cohen's kappa is deterministic when categorical assumptions hold.
kappa = cohens_kappa(pairs)
assert kappa["status"] == "calculated"
assert kappa["observed_agreement"] == 0.75
assert -1 <= kappa["kappa"] <= 1

# QF26: kappa returns not_applicable for insufficient, multilabel, or zero-denominator cases.
assert cohens_kappa([])["status"] == "not_applicable"
assert cohens_kappa([pairs[0]])["status"] == "not_applicable"
multilabel = deepcopy(pairs)
multilabel[0]["labels_a"] = ["A", "B"]
assert cohens_kappa(multilabel)["status"] == "not_applicable"
uniform = [
    {"sample_or_episode_id": "U1", "labels_a": ["A"], "labels_b": ["A"]},
    {"sample_or_episode_id": "U2", "labels_a": ["A"], "labels_b": ["A"]},
]
assert cohens_kappa(uniform)["status"] == "not_applicable"

# QF27: task-level reliability is never hidden by one aggregate score.
report = build_semantic_reliability_report(
    report_id="KU2D-SR-TEST", task_pairs={
        "counter_semantics": [dict(item, code_family_a="semantic_interpretation", code_family_b="semantic_interpretation") for item in pairs],
        "price_semantics": [dict(item, code_family_a="semantic_interpretation", code_family_b="semantic_interpretation") for item in uniform],
    },
    task_code_families={"counter_semantics": "semantic_interpretation", "price_semantics": "semantic_interpretation"},
    taxonomy=taxonomy,
    provenance_references=["fixtures/core_intelligence_quality/reviewed_examples.json"],
)
assert report["aggregate_score"] is None
assert report["aggregate_score_hidden"] is False
assert {item["task"] for item in report["task_results"]} == {"counter_semantics", "price_semantics"}
assert all("sample_size" in item and "disagreement_cases" in item for item in report["task_results"])
assert report["human_inter_rater_reliability_claimed"] is False

# QF28: analysis displays link every cell to evidence and confer no authority.
for projection in fixtures["analysis_projections"]:
    validate_analysis_projection(projection)
    assert all(cell["evidence_references"] for cell in projection["cells"])
    assert all(cell["display_confers_authority"] is False for cell in projection["cells"])

# QF29: quality-loop stages are ordered, optional, and do not force every episode to finish.
for loop in fixtures["quality_loops"]:
    validate_quality_loop(loop)
    assert loop["every_episode_must_complete_all_stages"] is False
unordered = deepcopy(fixtures["quality_loops"][0])
unordered["stages"][1], unordered["stages"][2] = unordered["stages"][2], unordered["stages"][1]
must_fail(lambda: validate_quality_loop(unordered), "unordered quality loop validated")

# QF30: all 11 source-history candidates remain candidate-only and unpromoted.
assert len(candidates["candidates"]) == 11
assert fixtures["candidate_source_promotion_count"] == 0
assert all(item["authority"]["candidate_only"] is True for item in candidates["candidates"])
assert all(item["authority"]["reviewed_corpus_authorized"] is False for item in candidates["candidates"])
assert all(item["authority"]["promoted_to_reviewed_episode_id"] is None for item in candidates["candidates"])

candidate_promotion = deepcopy(candidates)
candidate_promotion["candidates"][0]["authority"]["reviewed_corpus_authorized"] = True
must_fail(lambda: validate_candidate_registry(candidate_promotion), "candidate evidence became reviewed authority")

# QF31: sensitive material fails through the shared safe-JSON boundary.
sensitive = deepcopy(fixtures["analytical_memos"][0])
sensitive["cookies"] = "prohibited"
must_fail(lambda: validate_analytical_memo(sensitive), "sensitive memo material validated")

# QF32: all fixture artifacts remain non-authorizing and no live request occurred.
assert fixtures["live_request_count"] == 0
assert fixtures["boundaries"] == {
    "production_authorized": False, "scheduler_action": None,
    "ml_execution_or_export": False, "automatic_runtime_write": False,
}
for collection in (
    "evidence_chains", "coding_chains", "analytical_memos", "negative_cases",
    "finding_verifications", "independent_coding_records", "analysis_projections", "quality_loops",
):
    assert all(item["boundaries"] == NON_AUTHORIZING for item in fixtures[collection])

# QF33: normal runtime and orchestration do not import or auto-write quality records.
for folder in ("api", "control_plane", "repository", "service"):
    for path in (ROOT / folder).rglob("*.py"):
        assert "core_intelligence_quality" not in path.read_text(encoding="utf-8"), path
orchestrator = ROOT / "acquisition" / "acquisition_orchestrator.py"
assert "core_intelligence_quality" not in orchestrator.read_text(encoding="utf-8")

# QF34: validation is deterministic and never mutates caller-owned fixture objects.
snapshot = deepcopy(fixtures["coding_chains"][0])
validate_coding_chain(fixtures["coding_chains"][0], codebook, taxonomy)
assert fixtures["coding_chains"][0] == snapshot

# QF35: reviewed-pattern loop completion cannot bypass Finding Verification.
bypassed = deepcopy(fixtures["quality_loops"][0])
bypassed["stages"] = [item for item in bypassed["stages"] if item["stage"] != "finding_verification"]
must_fail(lambda: validate_quality_loop(bypassed), "Core Knowledge completion bypassed Finding Verification")

# QF36: taxonomy is authoritative for SI, AT, and FB code families.
assert index["SI-UNKNOWN-COUNTER"]["code_family"] == "semantic_interpretation"
assert index["AT-SITEMAP-CANONICAL-DETAIL"]["code_family"] == "acquisition_technique"
assert index["FB-APPLICATION-SHELL"]["code_family"] == "failure_boundary_type"
wrong_at_family = deepcopy(codebook)
next(item for item in wrong_at_family["codes"] if item["code_id"].startswith("AT-"))["code_family"] = "semantic_interpretation"
must_fail(lambda: validate_codebook(wrong_at_family, taxonomy), "AT code masqueraded as semantic interpretation")
wrong_fb_family = deepcopy(codebook)
next(item for item in wrong_fb_family["codes"] if item["code_id"].startswith("FB-"))["code_family"] = "semantic_interpretation"
must_fail(lambda: validate_codebook(wrong_fb_family, taxonomy), "FB code masqueraded as semantic interpretation")

# QF37: Theme is broader than Code, distinct from Interpretation, and non-authoritative.
theme = counter_chain["themes"][0]
assert theme["kind"] == "theme"
assert theme["authority_conferred"] is False
assert theme["theme_id"] in counter_chain["interpretations"][0]["theme_references"]
theme_as_code = deepcopy(counter_chain)
theme_as_code["codes"][0]["kind"] = "theme"
must_fail(lambda: validate_evidence_chain(theme_as_code, codebook, taxonomy), "theme substituted for code")
interpretation_as_theme = deepcopy(counter_chain)
interpretation_as_theme["themes"][0]["kind"] = "interpretation"
must_fail(lambda: validate_evidence_chain(interpretation_as_theme, codebook, taxonomy), "interpretation substituted for theme")

# QF38: task-aware coding rejects a valid code from the wrong taxonomy family.
wrong_task_family = deepcopy(fixtures["coding_chains"][-1])
wrong_task_family["expected_code_family"] = "semantic_interpretation"
must_fail(lambda: validate_coding_chain(wrong_task_family, codebook, taxonomy), "technique code entered semantic task")

# QF39: dimension-aware agreement and kappa refuse incompatible label families.
dimension_pairs = [
    dict(item, code_family_a="semantic_interpretation", code_family_b="semantic_interpretation")
    for item in pairs
]
assert agreement_rate(dimension_pairs, expected_code_family="semantic_interpretation")["status"] == "calculated"
incompatible_pairs = deepcopy(dimension_pairs)
incompatible_pairs[0]["code_family_b"] = "failure_boundary_type"
assert agreement_rate(incompatible_pairs, expected_code_family="semantic_interpretation")["status"] == "not_applicable"
assert cohens_kappa(incompatible_pairs, expected_code_family="semantic_interpretation")["status"] == "not_applicable"

# QF40: coverage metadata states exact partial scope rather than false completeness.
coverage = codebook["coverage"]
assert coverage["taxonomy_id_count"] == 83
assert coverage["guided_id_count"] == len(codebook["codes"]) == 11
assert coverage["full_taxonomy_coverage"] is False
assert coverage["dimensions_covered"] == [
    "acquisition_technique", "failure_boundary_type", "semantic_interpretation",
]
assert coverage["fully_codebooked_dimensions"] == []
assert coverage["not_yet_codebooked_dimensions"]
assert sum(item["guided_id_count"] for item in coverage["dimension_coverage"]) == 11

# QF41: SI family claims and Independent Coding task dimensions also fail closed.
wrong_si_family = deepcopy(codebook)
next(item for item in wrong_si_family["codes"] if item["code_id"].startswith("SI-"))["code_family"] = "acquisition_technique"
must_fail(lambda: validate_codebook(wrong_si_family, taxonomy), "SI code left semantic_interpretation family")
wrong_independent_family = deepcopy(fixtures["independent_coding_records"][0])
wrong_independent_family["expected_code_family"] = "failure_boundary_type"
must_fail(
    lambda: validate_independent_coding_record(wrong_independent_family, codebook, taxonomy),
    "independent semantic coding accepted a failure-boundary task family",
)

# QF42: reliability reports reject invented taxonomy dimensions.
must_fail(
    lambda: build_semantic_reliability_report(
        report_id="KU2D-SR-BAD-DIMENSION", task_pairs={"counter_semantics": dimension_pairs},
        task_code_families={"counter_semantics": "invented_dimension"}, taxonomy=taxonomy,
        provenance_references=["fixtures/core_intelligence_quality/reviewed_examples.json"],
    ),
    "reliability report accepted an invented taxonomy family",
)

print("Core Intelligence Quality Foundation deterministic tests passed (QF1-QF42).")
