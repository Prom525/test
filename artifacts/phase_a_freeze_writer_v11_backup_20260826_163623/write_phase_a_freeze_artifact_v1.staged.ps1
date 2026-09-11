$ErrorActionPreference = "Stop"

Set-Location C:\ai-platform

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-A FORMAL FREEZE ARTIFACT V1" -ForegroundColor Cyan
Write-Host " NEW ARTIFACT ONLY / NO SOURCE MODIFICATION" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan


# ============================================================
# Paths
# ============================================================

$ArtifactRoot = "C:\ai-platform\artifacts"

$LatestA2eDir = "C:\ai-platform\artifacts\golden_testset_v1\a2e_entity_coverage_20260826_162549"

$RuntimePath = Join-Path $LatestA2eDir "a2e_runtime_200.json"
$SummaryPath = Join-Path $LatestA2eDir "a2e_entity_summary.json"
$FindingsPath = Join-Path $LatestA2eDir "a2e_entity_findings.json"
$MatrixPath = Join-Path $LatestA2eDir "a2e_entity_key_matrix.csv"

$ContractPath = "C:\ai-platform\artifacts\golden_testset_v1\phase_a_test_contract_v2.csv"

$EvaluatorPath = "C:\ai-platform\audit_phase_a2e_entity_coverage_cardinality_v1.ps1"

$A2cPath = "C:\ai-platform\artifacts\golden_testset_v1\a2c_dualrun_accept_20260826_114355\a2c_dualrun_full.json"

$A2dPath = "C:\ai-platform\artifacts\golden_testset_v1\a2d_dualrun_accept_20260826_122437\a2d_dualrun_full.json"

$Band192CfPath = "C:\ai-platform\artifacts\golden_testset_v1\a2e_band_codes_192_counterfactual_20260826_151425\a2e_band_codes_192_counterfactual_200.json"

$AppRoot = "C:\ai-platform\api\app\orchestrator"


# ============================================================
# Frozen hashes
# ============================================================

$ExpectedRuntimeHash =
    "27D1C63B024D2EE26198F009AF95749DF92DE32A9E7E690E47D97FC1F0970016"

$ExpectedSummaryHash =
    "37AF885A1A823A6826C54B1034117C5669E94CFBB2D459B7166ECA332640FE23"

$ExpectedFindingsHash =
    "D09C9853A9C8A70FD3282285DB969D7CAF8538D9D055FCEA51FC03EC78D015A5"

$ExpectedMatrixHash =
    "F75CA56CF52EDFAD605F413FE814E3D3A018FFD91D63038FE672311B510E32A0"

$ExpectedContractHash =
    "EE02DDC2FE72501F31DB80B97C4555B8D3E261A7C64A53079FAB5FB85F545529"

$ExpectedEvaluatorHash =
    "FDCE2E6E62685BF891216644B0ACC0530350267DCAFDE984F69E2CC899438A0B"

$ExpectedA2cHash =
    "EEC621E1696BFA9E77CA627031EDECC4E01A9EEAF1C9F5D2A96B5954A09FD266"

$ExpectedA2dHash =
    "96FA7AAD95D73C325FB30035CE9BB997666EF70CEA33ADF70D7C0B28E311088D"

$ExpectedBand192CfHash =
    "090EDE8CB10EEFB680C4B740BFC6D92211A3B503BF36D703D2435E8CD054D0DF"


$ExpectedAppHashes = [ordered]@{
    "models.py" =
        "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E"

    "understanding.py" =
        "CF35835C9BD03D1267CED10EE47DCB67795A4DEA38336E4A1E8126049769BF78"

    "planner.py" =
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"

    "band_candidate_shadow.py" =
        "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484"

    "query_classification.py" =
        "193C690E4D62798566B57D84BD590DB04655357FD6DE86AE4F56EB5E16E35576"

    "normalizer.py" =
        "3AC3E4381FDB3501FF01E1D19BE317CBDCB03B214034409284E29A2D1303DDDB"

    "complexity.py" =
        "1A479E52DD552F92086D3A4D199FC54F9D0BAE77CC6B15924962570B9B425022"

    "service.py" =
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"

    "executor.py" =
        "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"
}


# ============================================================
# Required input presence
# ============================================================

Write-Host ""
Write-Host "=== PRE-FREEZE INPUT GUARDS ==="

$RequiredFiles = @(
    $RuntimePath,
    $SummaryPath,
    $FindingsPath,
    $MatrixPath,
    $ContractPath,
    $EvaluatorPath,
    $A2cPath,
    $A2dPath,
    $Band192CfPath
)

foreach ($Path in $RequiredFiles) {

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Freeze input ontbreekt: $Path"
    }
}

if (-not (Test-Path -LiteralPath $ArtifactRoot -PathType Container)) {
    throw "Artifact root ontbreekt."
}


# ============================================================
# Input hash guards
# ============================================================

$RuntimeHash = (
    Get-FileHash $RuntimePath -Algorithm SHA256
).Hash

$SummaryHash = (
    Get-FileHash $SummaryPath -Algorithm SHA256
).Hash

$FindingsHash = (
    Get-FileHash $FindingsPath -Algorithm SHA256
).Hash

$MatrixHash = (
    Get-FileHash $MatrixPath -Algorithm SHA256
).Hash

$ContractHash = (
    Get-FileHash $ContractPath -Algorithm SHA256
).Hash

$EvaluatorHash = (
    Get-FileHash $EvaluatorPath -Algorithm SHA256
).Hash

$A2cHash = (
    Get-FileHash $A2cPath -Algorithm SHA256
).Hash

$A2dHash = (
    Get-FileHash $A2dPath -Algorithm SHA256
).Hash

$Band192CfHash = (
    Get-FileHash $Band192CfPath -Algorithm SHA256
).Hash


Write-Host "RUNTIME_RESULTS_SHA256=$RuntimeHash"
Write-Host "SUMMARY_SHA256=$SummaryHash"
Write-Host "FINDINGS_SHA256=$FindingsHash"
Write-Host "ENTITY_KEY_MATRIX_SHA256=$MatrixHash"
Write-Host "CONTRACT_SHA256=$ContractHash"
Write-Host "EVALUATOR_SHA256=$EvaluatorHash"
Write-Host "A2C_ACCEPTANCE_SHA256=$A2cHash"
Write-Host "A2D_ACCEPTANCE_SHA256=$A2dHash"
Write-Host "BAND192_COUNTERFACTUAL_SHA256=$Band192CfHash"


if ($RuntimeHash -ne $ExpectedRuntimeHash) {
    throw "Runtime results hash mismatch."
}

if ($SummaryHash -ne $ExpectedSummaryHash) {
    throw "Summary hash mismatch."
}

if ($FindingsHash -ne $ExpectedFindingsHash) {
    throw "Findings hash mismatch."
}

if ($MatrixHash -ne $ExpectedMatrixHash) {
    throw "Entity matrix hash mismatch."
}

if ($ContractHash -ne $ExpectedContractHash) {
    throw "Golden contract hash mismatch."
}

if ($EvaluatorHash -ne $ExpectedEvaluatorHash) {
    throw "Evaluator hash mismatch."
}

if ($A2cHash -ne $ExpectedA2cHash) {
    throw "A2c acceptance hash mismatch."
}

if ($A2dHash -ne $ExpectedA2dHash) {
    throw "A2d acceptance hash mismatch."
}

if ($Band192CfHash -ne $ExpectedBand192CfHash) {
    throw "Band192 counterfactual hash mismatch."
}


foreach ($Name in $ExpectedAppHashes.Keys) {

    $Path = Join-Path $AppRoot $Name

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "PROMATI appbestand ontbreekt: $Name"
    }

    $Actual = (
        Get-FileHash $Path -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Actual"

    if ($Actual -ne $ExpectedAppHashes[$Name]) {
        throw "PROMATI app hash mismatch: $Name"
    }
}

Write-Host "PHASE_A_FREEZE_PRESTATE_HASHES_OK=TRUE" -ForegroundColor Green


# ============================================================
# Evaluator PowerShell parser
# ============================================================

$Tokens = $null
$Errors = $null

[System.Management.Automation.Language.Parser]::ParseFile(
    $EvaluatorPath,
    [ref]$Tokens,
    [ref]$Errors
) | Out-Null

Write-Host "EVALUATOR_PARSE_ERROR_COUNT=$($Errors.Count)"

if ($Errors.Count -ne 0) {
    throw "Evaluator PowerShell parse failure."
}

Write-Host "EVALUATOR_POWERSHELL_PARSE_OK=TRUE"


# ============================================================
# New artifact paths
# ============================================================

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$CreatedLocal = (
    Get-Date
).ToString("o")

$CreatedUtc = (
    Get-Date
).ToUniversalTime().ToString("o")

$FinalDir = Join-Path `
    $ArtifactRoot `
    "phase_a_freeze_v1_$Stamp"

$TempDir = Join-Path `
    $ArtifactRoot `
    (
        ".phase_a_freeze_v1_{0}.tmp_{1}" -f `
            $Stamp,
            ([guid]::NewGuid().ToString("N"))
    )


if (Test-Path -LiteralPath $FinalDir) {
    throw "Freeze artifact directory bestaat al: $FinalDir"
}

if (Test-Path -LiteralPath $TempDir) {
    throw "Temp freeze directory bestaat onverwacht al."
}


New-Item `
    -ItemType Directory `
    -Path $TempDir |
    Out-Null


$JsonName = "phase_a_freeze_v1.json"
$TextName = "phase_a_freeze_v1.txt"
$ManifestName = "phase_a_freeze_v1.sha256"

$JsonTempPath = Join-Path $TempDir $JsonName
$TextTempPath = Join-Path $TempDir $TextName
$ManifestTempPath = Join-Path $TempDir $ManifestName


# ============================================================
# Generate + semantically validate freeze package
# ============================================================

$WriterPython = @'
import ast
import hashlib
import json
import pathlib
import re
import sys


runtime_path = pathlib.Path(sys.argv[1])
summary_path = pathlib.Path(sys.argv[2])
findings_path = pathlib.Path(sys.argv[3])
matrix_path = pathlib.Path(sys.argv[4])
contract_path = pathlib.Path(sys.argv[5])
evaluator_path = pathlib.Path(sys.argv[6])
a2c_path = pathlib.Path(sys.argv[7])
a2d_path = pathlib.Path(sys.argv[8])
band192_path = pathlib.Path(sys.argv[9])
app_root = pathlib.Path(sys.argv[10])

json_out = pathlib.Path(sys.argv[11])
text_out = pathlib.Path(sys.argv[12])

final_dir = sys.argv[13]
created_local = sys.argv[14]
created_utc = sys.argv[15]


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest().upper()


expected_hashes = {
    "runtime_results":
        "27D1C63B024D2EE26198F009AF95749DF92DE32A9E7E690E47D97FC1F0970016",

    "summary":
        "37AF885A1A823A6826C54B1034117C5669E94CFBB2D459B7166ECA332640FE23",

    "findings":
        "D09C9853A9C8A70FD3282285DB969D7CAF8538D9D055FCEA51FC03EC78D015A5",

    "entity_key_matrix":
        "F75CA56CF52EDFAD605F413FE814E3D3A018FFD91D63038FE672311B510E32A0",

    "contract":
        "EE02DDC2FE72501F31DB80B97C4555B8D3E261A7C64A53079FAB5FB85F545529",

    "evaluator":
        "FDCE2E6E62685BF891216644B0ACC0530350267DCAFDE984F69E2CC899438A0B",

    "a2c_acceptance":
        "EEC621E1696BFA9E77CA627031EDECC4E01A9EEAF1C9F5D2A96B5954A09FD266",

    "a2d_acceptance":
        "96FA7AAD95D73C325FB30035CE9BB997666EF70CEA33ADF70D7C0B28E311088D",

    "band192_counterfactual":
        "090EDE8CB10EEFB680C4B740BFC6D92211A3B503BF36D703D2435E8CD054D0DF",
}


evidence_paths = {
    "runtime_results": runtime_path,
    "summary": summary_path,
    "findings": findings_path,
    "entity_key_matrix": matrix_path,
    "contract": contract_path,
    "evaluator": evaluator_path,
    "a2c_acceptance": a2c_path,
    "a2d_acceptance": a2d_path,
    "band192_counterfactual": band192_path,
}


actual_evidence_hashes = {}


for name, path in evidence_paths.items():

    actual = sha256(path)
    expected = expected_hashes[name]

    if actual != expected:
        raise RuntimeError(
            f"{name} hash mismatch"
        )

    actual_evidence_hashes[name] = actual


expected_app_hashes = {
    "models.py":
        "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E",

    "understanding.py":
        "CF35835C9BD03D1267CED10EE47DCB67795A4DEA38336E4A1E8126049769BF78",

    "planner.py":
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68",

    "band_candidate_shadow.py":
        "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484",

    "query_classification.py":
        "193C690E4D62798566B57D84BD590DB04655357FD6DE86AE4F56EB5E16E35576",

    "normalizer.py":
        "3AC3E4381FDB3501FF01E1D19BE317CBDCB03B214034409284E29A2D1303DDDB",

    "complexity.py":
        "1A479E52DD552F92086D3A4D199FC54F9D0BAE77CC6B15924962570B9B425022",

    "service.py":
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761",

    "executor.py":
        "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A",
}


actual_app_hashes = {}


for name, expected in expected_app_hashes.items():

    path = app_root / name

    actual = sha256(path)

    if actual != expected:
        raise RuntimeError(
            f"production app hash mismatch: {name}"
        )

    actual_app_hashes[name] = actual


# ============================================================
# Latest official summary acceptance
# ============================================================

with summary_path.open(
    "r",
    encoding="utf-8-sig",
) as handle:
    summary = json.load(handle)


with findings_path.open(
    "r",
    encoding="utf-8-sig",
) as handle:
    findings = json.load(handle)


required_summary = {
    "total": 200,
    "missing_expected": 69,
    "value_mismatches": 1,
    "negative_violations": 0,
    "queryclass_failures": 0,
    "a1b_early_gate_failures": 0,
    "a2c_a2d_control_failures": 0,
    "routing_safety_regressions": 0,
    "execution_grounding_regressions": 0,
    "blocking_missing": 0,
    "blocking_value_mismatches": 0,
    "blocking_negative_violations": 0,
    "blocking_entity_errors": 0,
    "diagnostics_domain_excluded": True,
}


for key, expected in required_summary.items():

    actual = summary.get(key)

    if actual != expected:
        raise RuntimeError(
            f"freeze summary mismatch for {key}: "
            f"{actual!r} != {expected!r}"
        )


for key in (
    "blocking_missing",
    "blocking_value_mismatches",
    "blocking_negative_violations",
    "queryclass_failures",
    "early_gate_failures",
    "a2c_a2d_control_failures",
):

    value = findings.get(key)

    if not isinstance(value, list):
        raise RuntimeError(
            f"findings {key} is not list"
        )

    if value:
        raise RuntimeError(
            f"blocking finding not empty: {key}"
        )


# ============================================================
# Evaluator semantic freeze
# ============================================================

evaluator_text = evaluator_path.read_text(
    encoding="utf-8-sig",
).replace(
    "\r\n",
    "\n",
)


pattern = re.compile(
    r"(?ms)^\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*=\s*@'\n"
    r"(?P<body>.*?)"
    r"^\s*'@\s*$"
)


matches = [
    match
    for match in pattern.finditer(
        evaluator_text
    )
    if match.group("name") == "AuditPython"
]


if len(matches) != 1:
    raise RuntimeError(
        "AuditPython here-string count != 1"
    )


body = matches[0].group("body")

tree = ast.parse(body)

compile(
    body,
    "<AuditPython-freeze-writer>",
    "exec",
)


helper_hits = [
    node
    for node in ast.walk(tree)
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
    and node.name
        == "lijn_code_representation_equivalent"
]


if len(helper_hits) != 1:
    raise RuntimeError(
        "lijn equivalence helper count != 1"
    )


expected_helper = '''
def lijn_code_representation_equivalent(
    entities,
    expected_value,
):
    actual_lijn_key = entity_present(
        entities,
        "lijn_code",
    )

    if actual_lijn_key is not None:
        return expected_values_equal(
            expected_value,
            runtime_entity_value(
                entities[
                    actual_lijn_key
                ]
            ),
        )

    scope_code_key = entity_present(
        entities,
        "scope_code",
    )
    scope_type_key = entity_present(
        entities,
        "scope_type",
    )

    if (
        scope_code_key is None
        or scope_type_key is None
    ):
        return False

    scope_code = runtime_entity_value(
        entities[
            scope_code_key
        ]
    )
    scope_type = runtime_entity_value(
        entities[
            scope_type_key
        ]
    )

    if not expected_values_equal(
        expected_value,
        scope_code,
    ):
        return False

    if scope_type == "area":
        area_code_key = entity_present(
            entities,
            "area_code",
        )

        if area_code_key is None:
            return False

        return expected_values_equal(
            expected_value,
            runtime_entity_value(
                entities[
                    area_code_key
                ]
            ),
        )

    if scope_type == "installation":
        installation_code_key = entity_present(
            entities,
            "installation_code",
        )

        if installation_code_key is None:
            return False

        return expected_values_equal(
            expected_value,
            runtime_entity_value(
                entities[
                    installation_code_key
                ]
            ),
        )

    return False
'''


expected_helper_node = ast.parse(
    expected_helper
).body[0]


helper_dump = ast.dump(
    helper_hits[0],
    include_attributes=False,
)

expected_helper_dump = ast.dump(
    expected_helper_node,
    include_attributes=False,
)


if helper_dump != expected_helper_dump:
    raise RuntimeError(
        "lijn equivalence helper AST mismatch"
    )


parent = {}


for node in ast.walk(tree):

    for child in ast.iter_child_nodes(node):
        parent[id(child)] = node


def enclosing_for(node):

    current = parent.get(id(node))

    while current is not None:

        if isinstance(current, ast.For):
            return current

        current = parent.get(id(current))

    return None


equivalence_calls = []


for node in ast.walk(tree):

    if not isinstance(node, ast.Call):
        continue

    if (
        isinstance(node.func, ast.Name)
        and node.func.id
            == "lijn_code_representation_equivalent"
    ):
        equivalence_calls.append(node)


if len(equivalence_calls) != 1:
    raise RuntimeError(
        "lijn equivalence call count != 1"
    )


call = equivalence_calls[0]

current = parent.get(id(call))
precheck_if = None


while current is not None:

    if isinstance(current, ast.If):
        precheck_if = current
        break

    current = parent.get(id(current))


if precheck_if is None:
    raise RuntimeError(
        "equivalence call not owned by if"
    )


loop = enclosing_for(precheck_if)

if loop is None:
    raise RuntimeError(
        "equivalence precheck not in for-loop"
    )


loop_iter = ast.unparse(loop.iter)
precheck_test = ast.unparse(
    precheck_if.test
)


if loop_iter != "expectations['positive']":
    raise RuntimeError(
        "equivalence precheck not positive-only"
    )


for fragment in (
    "found_key is None",
    "key == 'lijn_code'",
    "lijn_code_representation_equivalent(entities, expected_value)",
):

    if fragment not in precheck_test:
        raise RuntimeError(
            "equivalence precheck mismatch"
        )


negative_calls = 0


for call_node in equivalence_calls:

    call_loop = enclosing_for(
        call_node
    )

    if (
        call_loop is not None
        and ast.unparse(
            call_loop.iter
        ) == "expectations['negative']"
    ):
        negative_calls += 1


if negative_calls != 0:
    raise RuntimeError(
        "equivalence leaked into negative expectations"
    )


blocking_assignments = []


for node in ast.walk(tree):

    if not isinstance(node, ast.Assign):
        continue

    if len(node.targets) != 1:
        continue

    target = node.targets[0]

    if (
        isinstance(target, ast.Name)
        and target.id == "blocking_missing"
    ):
        blocking_assignments.append(node)


if len(blocking_assignments) != 1:
    raise RuntimeError(
        "blocking_missing assignment count != 1"
    )


blocking_source = (
    ast.get_source_segment(
        body,
        blocking_assignments[0],
    )
    or ""
)


if "for finding in missing_expected" not in blocking_source:
    raise RuntimeError(
        "blocking_missing derivation changed"
    )


helper_ast_hash = hashlib.sha256(
    helper_dump.encode("utf-8")
).hexdigest().upper()


precheck_ast_dump = ast.dump(
    precheck_if,
    include_attributes=False,
)


precheck_ast_hash = hashlib.sha256(
    precheck_ast_dump.encode("utf-8")
).hexdigest().upper()


blocking_derivation_ast_hash = hashlib.sha256(
    ast.dump(
        blocking_assignments[0],
        include_attributes=False,
    ).encode("utf-8")
).hexdigest().upper()


equivalence_rule = (
    "lijn_code=X OR "
    "(lijn_code absent AND scope_code=X AND "
    "((scope_type=area AND area_code=X) OR "
    "(scope_type=installation AND installation_code=X)))"
)


# ============================================================
# Freeze object
# ============================================================

freeze = {
    "schema":
        "promati.phase_a.freeze.v1",

    "freeze_status":
        "FROZEN",

    "phase":
        "PHASE_A_ROUTING_CORRECTNESS_AND_GROUNDING",

    "created_at_local":
        created_local,

    "created_at_utc":
        created_utc,

    "artifact_directory":
        final_dir,

    "freeze_basis":
        {
            "golden_tests": 200,

            "official_decision":
                "NO_BLOCKING_ENTITY_GROUNDING_FAILURES",

            "a2e_patch_required":
                False,

            "phase_a_freeze_candidate":
                True,

            "blocking_entity_errors":
                0,

            "routing_safety_regressions":
                0,

            "execution_grounding_regressions":
                0,
        },

    "acceptance_metrics":
        {
            "total":
                summary["total"],

            "missing_expected_nonblocking":
                summary["missing_expected"],

            "value_mismatches_nonblocking":
                summary["value_mismatches"],

            "negative_violations":
                summary["negative_violations"],

            "queryclass_failures":
                summary["queryclass_failures"],

            "a1b_early_gate_failures":
                summary["a1b_early_gate_failures"],

            "a2c_a2d_control_failures":
                summary["a2c_a2d_control_failures"],

            "routing_safety_regressions":
                summary["routing_safety_regressions"],

            "execution_grounding_regressions":
                summary[
                    "execution_grounding_regressions"
                ],

            "blocking_missing":
                summary["blocking_missing"],

            "blocking_value_mismatches":
                summary[
                    "blocking_value_mismatches"
                ],

            "blocking_negative_violations":
                summary[
                    "blocking_negative_violations"
                ],

            "blocking_entity_errors":
                summary["blocking_entity_errors"],
        },

    "lijn_code_acceptance_equivalence":
        {
            "rule":
                equivalence_rule,

            "scope":
                "positive_expectations_only",

            "exact_runtime_lijn_code_remains_valid":
                True,

            "typed_area_scope_equivalent":
                True,

            "typed_installation_scope_equivalent":
                True,

            "negative_expectations_unchanged":
                True,

            "blocking_missing_derivation_unchanged":
                True,

            "helper_ast_sha256":
                helper_ast_hash,

            "positive_precheck_ast_sha256":
                precheck_ast_hash,

            "blocking_derivation_ast_sha256":
                blocking_derivation_ast_hash,

            "evaluator_call_count":
                1,

            "negative_evaluator_call_count":
                0,
        },

    "scope_exclusions":
        {
            "diagnostics_domain":
                {
                    "excluded_from_phase_a_repair_decision":
                        True,

                    "changed_by_phase_a_freeze":
                        False,
                },

            "org":
                {
                    "tuning_performed":
                        False,

                    "changed_by_phase_a_freeze":
                        False,
                },
        },

    "evidence_hashes_sha256":
        actual_evidence_hashes,

    "production_app_hashes_sha256":
        actual_app_hashes,

    "immutability_model":
        {
            "source_inputs_are_hash_guarded":
                True,

            "freeze_package_is_new_only":
                True,

            "golden_contract_modified":
                False,

            "production_app_modified":
                False,

            "evaluator_modified_by_freeze_writer":
                False,

            "runtime_modified":
                False,

            "artifact_files_read_only_after_commit":
                True,
        },

    "next_phase":
        {
            "id":
                "PHASE_B_EXECUTION_CONTRACTS",

            "recommendation":
                "Define specialist registry and typed execution result contracts before evidence orchestration.",

            "phase_a_router_should_remain_frozen":
                True,
        },
}


canonical = json.dumps(
    freeze,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
) + "\n"


json_out.write_text(
    canonical,
    encoding="utf-8",
)


# Re-read canonical JSON immediately.
with json_out.open(
    "r",
    encoding="utf-8",
) as handle:
    reread = json.load(handle)


if reread != freeze:
    raise RuntimeError(
        "freeze JSON reread mismatch"
    )


text_lines = [
    "PROMATI PHASE-A FORMAL FREEZE V1",
    "================================",
    "",
    "STATUS=FROZEN",
    "PHASE=PHASE_A_ROUTING_CORRECTNESS_AND_GROUNDING",
    f"CREATED_AT_LOCAL={created_local}",
    f"CREATED_AT_UTC={created_utc}",
    "",
    "OFFICIAL_GOLDEN_TESTS=200",
    "A2E_PATCH_REQUIRED=FALSE",
    "PHASE_A_FREEZE_CANDIDATE=TRUE",
    "A2E_DECISION=NO_BLOCKING_ENTITY_GROUNDING_FAILURES",
    "",
    "BLOCKING_MISSING=0",
    "BLOCKING_VALUE_MISMATCHES=0",
    "BLOCKING_NEGATIVE_VIOLATIONS=0",
    "BLOCKING_ENTITY_ERRORS=0",
    "ROUTING_SAFETY_REGRESSIONS=0",
    "EXECUTION_GROUNDING_REGRESSIONS=0",
    "QUERYCLASS_FAILURES=0",
    "A1B_EARLY_GATE_FAILURES=0",
    "A2C_A2D_CONTROL_FAILURES=0",
    "",
    "NONBLOCKING_MISSING_EXPECTED=69",
    "NONBLOCKING_VALUE_MISMATCHES=1",
    "",
    "LIJN_CODE_EQUIVALENCE_RULE=" + equivalence_rule,
    "LIJN_CODE_EQUIVALENCE_SCOPE=POSITIVE_EXPECTATIONS_ONLY",
    "NEGATIVE_EXPECTATIONS_UNCHANGED=TRUE",
    "BLOCKING_MISSING_DERIVATION_UNCHANGED=TRUE",
    "",
    "DIAGNOSTICS_DOMAIN_EXCLUDED_FROM_PHASE_A_REPAIR_DECISION=TRUE",
    "ORG_TUNING_PERFORMED=FALSE",
    "",
    "CONTRACT_SHA256=" + actual_evidence_hashes["contract"],
    "EVALUATOR_SHA256=" + actual_evidence_hashes["evaluator"],
    "RUNTIME_RESULTS_SHA256=" + actual_evidence_hashes["runtime_results"],
    "SUMMARY_SHA256=" + actual_evidence_hashes["summary"],
    "FINDINGS_SHA256=" + actual_evidence_hashes["findings"],
    "ENTITY_KEY_MATRIX_SHA256=" + actual_evidence_hashes["entity_key_matrix"],
    "A2C_ACCEPTANCE_SHA256=" + actual_evidence_hashes["a2c_acceptance"],
    "A2D_ACCEPTANCE_SHA256=" + actual_evidence_hashes["a2d_acceptance"],
    "BAND192_COUNTERFACTUAL_SHA256=" + actual_evidence_hashes["band192_counterfactual"],
    "",
    "NEXT_PHASE=PHASE_B_EXECUTION_CONTRACTS",
    "PHASE_A_ROUTER_SHOULD_REMAIN_FROZEN=TRUE",
    "",
]


text_out.write_text(
    "\n".join(text_lines),
    encoding="utf-8",
)


print("FREEZE_JSON_GENERATED=TRUE")
print("FREEZE_TEXT_GENERATED=TRUE")
print("FREEZE_JSON_REREAD_VALIDATED=TRUE")
print("FREEZE_ACCEPTANCE_METRICS_VALIDATED=TRUE")
print("FREEZE_EQUIVALENCE_HELPER_AST_VALIDATED=TRUE")
print("FREEZE_EQUIVALENCE_POSITIVE_PRECHECK_VALIDATED=TRUE")
print("FREEZE_NEGATIVE_EQUIVALENCE_CALL_COUNT=0")
print("FREEZE_BLOCKING_DERIVATION_VALIDATED=TRUE")
print(
    "LIJN_EQUIVALENCE_HELPER_AST_SHA256="
    + helper_ast_hash
)
print(
    "LIJN_EQUIVALENCE_PRECHECK_AST_SHA256="
    + precheck_ast_hash
)
print(
    "BLOCKING_MISSING_DERIVATION_AST_SHA256="
    + blocking_derivation_ast_hash
)
'@


$WriterOutput = @(
    $WriterPython |
        & python - `
            $RuntimePath `
            $SummaryPath `
            $FindingsPath `
            $MatrixPath `
            $ContractPath `
            $EvaluatorPath `
            $A2cPath `
            $A2dPath `
            $Band192CfPath `
            $AppRoot `
            $JsonTempPath `
            $TextTempPath `
            $FinalDir `
            $CreatedLocal `
            $CreatedUtc
)

$WriterExit = $LASTEXITCODE

$WriterOutput | ForEach-Object {
    Write-Host $_
}

if ($WriterExit -ne 0) {
    throw "Freeze artifact generation mislukt."
}


if (-not (Test-Path -LiteralPath $JsonTempPath -PathType Leaf)) {
    throw "Freeze JSON ontbreekt."
}

if (-not (Test-Path -LiteralPath $TextTempPath -PathType Leaf)) {
    throw "Freeze text ontbreekt."
}


# ============================================================
# Freeze file hashes + manifest
# ============================================================

$JsonHash = (
    Get-FileHash $JsonTempPath -Algorithm SHA256
).Hash

$TextHash = (
    Get-FileHash $TextTempPath -Algorithm SHA256
).Hash


$ManifestText = @(
    "$JsonHash *$JsonName"
    "$TextHash *$TextName"
) -join "`r`n"

$ManifestText = $ManifestText + "`r`n"


[System.IO.File]::WriteAllText(
    $ManifestTempPath,
    $ManifestText,
    [System.Text.ASCIIEncoding]::new()
)


$ManifestHash = (
    Get-FileHash $ManifestTempPath -Algorithm SHA256
).Hash


Write-Host ""
Write-Host "=== STAGED FREEZE PACKAGE ==="

Write-Host "FREEZE_JSON_SHA256=$JsonHash"
Write-Host "FREEZE_TEXT_SHA256=$TextHash"
Write-Host "FREEZE_MANIFEST_SHA256=$ManifestHash"


# ============================================================
# Independent staged package verification
# ============================================================

$VerifyPython = @'
import hashlib
import json
import pathlib
import sys


directory = pathlib.Path(sys.argv[1])

json_path = directory / "phase_a_freeze_v1.json"
text_path = directory / "phase_a_freeze_v1.txt"
manifest_path = directory / "phase_a_freeze_v1.sha256"


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest().upper()


with json_path.open(
    "r",
    encoding="utf-8",
) as handle:
    freeze = json.load(handle)


if freeze.get("schema") != "promati.phase_a.freeze.v1":
    raise RuntimeError(
        "freeze schema mismatch"
    )


if freeze.get("freeze_status") != "FROZEN":
    raise RuntimeError(
        "freeze status mismatch"
    )


basis = freeze.get(
    "freeze_basis",
    {}
)


if basis.get("golden_tests") != 200:
    raise RuntimeError(
        "golden test count mismatch"
    )


if basis.get("blocking_entity_errors") != 0:
    raise RuntimeError(
        "blocking entity errors not zero"
    )


if (
    basis.get("official_decision")
    != "NO_BLOCKING_ENTITY_GROUNDING_FAILURES"
):
    raise RuntimeError(
        "official decision mismatch"
    )


rule = (
    freeze.get(
        "lijn_code_acceptance_equivalence",
        {}
    ).get("rule")
)


expected_rule = (
    "lijn_code=X OR "
    "(lijn_code absent AND scope_code=X AND "
    "((scope_type=area AND area_code=X) OR "
    "(scope_type=installation AND installation_code=X)))"
)


if rule != expected_rule:
    raise RuntimeError(
        "frozen equivalence rule mismatch"
    )


if (
    freeze.get(
        "next_phase",
        {}
    ).get("id")
    != "PHASE_B_EXECUTION_CONTRACTS"
):
    raise RuntimeError(
        "next phase mismatch"
    )


manifest_lines = [
    line.strip()
    for line in manifest_path.read_text(
        encoding="ascii"
    ).splitlines()
    if line.strip()
]


manifest = {}


for line in manifest_lines:

    digest, filename = line.split(
        " *",
        1,
    )

    manifest[
        filename
    ] = digest.upper()


for path in (
    json_path,
    text_path,
):

    actual = sha256(path)

    expected = manifest.get(
        path.name
    )

    if expected is None:
        raise RuntimeError(
            f"manifest missing {path.name}"
        )

    if actual != expected:
        raise RuntimeError(
            f"manifest hash mismatch: {path.name}"
        )


print("FREEZE_JSON_SCHEMA_VALID=TRUE")
print("FREEZE_STATUS_VALID=TRUE")
print("FREEZE_OFFICIAL_DECISION_VALID=TRUE")
print("FREEZE_BLOCKING_ENTITY_ERRORS_ZERO=TRUE")
print("FREEZE_EQUIVALENCE_RULE_VALID=TRUE")
print("FREEZE_NEXT_PHASE_VALID=TRUE")
print("FREEZE_MANIFEST_VALID=TRUE")
'@


$VerifyOutput = @(
    $VerifyPython |
        & python - `
            $TempDir
)

$VerifyExit = $LASTEXITCODE

$VerifyOutput | ForEach-Object {
    Write-Host $_
}

if ($VerifyExit -ne 0) {
    throw "Staged freeze package verification mislukt."
}


# ============================================================
# Atomic-ish same-volume directory promotion
# ============================================================

Write-Host ""
Write-Host "=== FREEZE PACKAGE COMMIT ==="

$Moved = $false
$FinalVerified = $false


try {

    if (Test-Path -LiteralPath $FinalDir) {
        throw "Final freeze directory bestaat al."
    }


    Move-Item `
        -LiteralPath $TempDir `
        -Destination $FinalDir

    $Moved = $true


    if (-not (Test-Path -LiteralPath $FinalDir -PathType Container)) {
        throw "Freeze directory promotion mislukt."
    }


    # Independent verification after promotion.
    $FinalVerifyOutput = @(
        $VerifyPython |
            & python - `
                $FinalDir
    )

    $FinalVerifyExit = $LASTEXITCODE

    $FinalVerifyOutput | ForEach-Object {
        Write-Host $_
    }

    if ($FinalVerifyExit -ne 0) {
        throw "Final freeze package verification mislukt."
    }


    $FinalJsonPath = Join-Path $FinalDir $JsonName
    $FinalTextPath = Join-Path $FinalDir $TextName
    $FinalManifestPath = Join-Path $FinalDir $ManifestName


    $FinalJsonHashBeforeReadonly = (Get-FileHash $FinalJsonPath -Algorithm SHA256).Hash

    if ($FinalJsonHashBeforeReadonly -ne $JsonHash) {
        throw "Final JSON hash mismatch."
    }


    $FinalTextHashBeforeReadonly = (Get-FileHash $FinalTextPath -Algorithm SHA256).Hash

    if ($FinalTextHashBeforeReadonly -ne $TextHash) {
        throw "Final text hash mismatch."
    }


    $FinalManifestHashBeforeReadonly = (Get-FileHash $FinalManifestPath -Algorithm SHA256).Hash

    if ($FinalManifestHashBeforeReadonly -ne $ManifestHash) {
        throw "Final manifest hash mismatch."
    }


    # Mark only the newly-created freeze files read-only.
    foreach ($Path in @(
        $FinalJsonPath,
        $FinalTextPath,
        $FinalManifestPath
    )) {

        $Item = Get-Item -LiteralPath $Path
        $Item.IsReadOnly = $true
    }


    $ReadonlyFailures = @(
        foreach ($Path in @(
            $FinalJsonPath,
            $FinalTextPath,
            $FinalManifestPath
        )) {

            if (-not (Get-Item -LiteralPath $Path).IsReadOnly) {
                $Path
            }
        }
    )


    if ($ReadonlyFailures.Count -ne 0) {
        throw "Niet alle freeze files zijn read-only."
    }


    # Hashes must remain identical after read-only attributes.
    $FinalJsonHashAfterReadonly = (Get-FileHash $FinalJsonPath -Algorithm SHA256).Hash

    if ($FinalJsonHashAfterReadonly -ne $JsonHash) {
        throw "JSON veranderde na read-only markering."
    }


    $FinalTextHashAfterReadonly = (Get-FileHash $FinalTextPath -Algorithm SHA256).Hash

    if ($FinalTextHashAfterReadonly -ne $TextHash) {
        throw "Text veranderde na read-only markering."
    }


    $FinalManifestHashAfterReadonly = (Get-FileHash $FinalManifestPath -Algorithm SHA256).Hash

    if ($FinalManifestHashAfterReadonly -ne $ManifestHash) {
        throw "Manifest veranderde na read-only markering."
    }


    $FinalVerified = $true
}
catch {

    $FinalDirExistsForRollback = Test-Path -LiteralPath $FinalDir

    if ($Moved -and $FinalDirExistsForRollback) {

        Get-ChildItem `
            -LiteralPath $FinalDir `
            -File `
            -ErrorAction SilentlyContinue |
            ForEach-Object {
                $_.IsReadOnly = $false
            }


        Remove-Item `
            -LiteralPath $FinalDir `
            -Recurse `
            -Force

        Write-Host `
            "PHASE_A_FREEZE_ARTIFACT_ROLLBACK_COMPLETE=TRUE" `
            -ForegroundColor Yellow
    }

    throw
}
finally {

    if (Test-Path -LiteralPath $TempDir) {

        Remove-Item `
            -LiteralPath $TempDir `
            -Recurse `
            -Force
    }
}


if (-not $FinalVerified) {
    throw "Freeze artifact final verification niet voltooid."
}


# ============================================================
# Final source/evidence immutability
# ============================================================

Write-Host ""
Write-Host "=== FINAL SOURCE IMMUTABILITY ==="


if ((Get-FileHash $RuntimePath -Algorithm SHA256).Hash -ne $ExpectedRuntimeHash) {
    throw "Runtime evidence veranderde."
}

if ((Get-FileHash $SummaryPath -Algorithm SHA256).Hash -ne $ExpectedSummaryHash) {
    throw "Summary evidence veranderde."
}

if ((Get-FileHash $FindingsPath -Algorithm SHA256).Hash -ne $ExpectedFindingsHash) {
    throw "Findings evidence veranderde."
}

if ((Get-FileHash $MatrixPath -Algorithm SHA256).Hash -ne $ExpectedMatrixHash) {
    throw "Entity matrix veranderde."
}

if ((Get-FileHash $ContractPath -Algorithm SHA256).Hash -ne $ExpectedContractHash) {
    throw "Golden contract veranderde."
}

if ((Get-FileHash $EvaluatorPath -Algorithm SHA256).Hash -ne $ExpectedEvaluatorHash) {
    throw "Evaluator veranderde."
}

if ((Get-FileHash $A2cPath -Algorithm SHA256).Hash -ne $ExpectedA2cHash) {
    throw "A2c evidence veranderde."
}

if ((Get-FileHash $A2dPath -Algorithm SHA256).Hash -ne $ExpectedA2dHash) {
    throw "A2d evidence veranderde."
}

if ((Get-FileHash $Band192CfPath -Algorithm SHA256).Hash -ne $ExpectedBand192CfHash) {
    throw "Band192 evidence veranderde."
}


foreach ($Name in $ExpectedAppHashes.Keys) {

    $Path = Join-Path $AppRoot $Name

    $Actual = (
        Get-FileHash $Path -Algorithm SHA256
    ).Hash

    if ($Actual -ne $ExpectedAppHashes[$Name]) {
        throw "PROMATI appbestand veranderde: $Name"
    }
}


# ============================================================
# Final markers
# ============================================================

Write-Host ""
Write-Host "=== FORMAL FREEZE RESULT ==="

Write-Host "FREEZE_ARTIFACT_DIR=$FinalDir"

Write-Host "FREEZE_JSON_SHA256=$JsonHash"
Write-Host "FREEZE_TEXT_SHA256=$TextHash"
Write-Host "FREEZE_MANIFEST_SHA256=$ManifestHash"

Write-Host "FREEZE_PACKAGE_ATOMIC_DIRECTORY_PROMOTION=TRUE"
Write-Host "FREEZE_PACKAGE_FINAL_VERIFICATION=TRUE"
Write-Host "FREEZE_FILES_READONLY=TRUE"

Write-Host "PHASE_A_FREEZE_EVIDENCE_INPUTS_UNCHANGED=TRUE"
Write-Host "PROMATI_APP_CODE_CHANGED=FALSE"
Write-Host "GOLDEN_CONTRACT_CHANGED=FALSE"
Write-Host "EVALUATOR_CHANGED_BY_FREEZE_WRITER=FALSE"

Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_EXECUTOR_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_RESEARCH_PROVIDER_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"

Write-Host ""
Write-Host "PHASE_A_FREEZE_ARTIFACT_WRITTEN=TRUE" -ForegroundColor Green
Write-Host "PHASE_A_FORMAL_FREEZE_READY=TRUE" -ForegroundColor Green
Write-Host "NEXT_PHASE=PHASE_B_EXECUTION_CONTRACTS" -ForegroundColor Green

Write-Host `
    "PHASE_A_FORMAL_FREEZE_ARTIFACT_COMPLETE" `
    -ForegroundColor Green