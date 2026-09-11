$ErrorActionPreference = "Stop"

Set-Location C:\ai-platform

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-A A2e BELT_WIDTH COUNTERFACTUAL V1" -ForegroundColor Cyan
Write-Host " SAME PROCESS / 200 TESTS / READ ONLY" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$Container = "ai-platform-api-1"
$ContractPath = "C:\ai-platform\artifacts\golden_testset_v1\phase_a_test_contract_v2.csv"

$ExpectedContractHash = "EE02DDC2FE72501F31DB80B97C4555B8D3E261A7C64A53079FAB5FB85F545529"

$ExpectedHashes = [ordered]@{
    "models.py" = "CFAA831CCF5CFA39FBBA98800376F1099E587C8047EE552BCA0D6D815E852374"
    "understanding.py" = "2F3F4588E7DBBE7D60DC561165795895597ED035C5FB8678094361F224F22581"
    "planner.py" = "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"
    "band_candidate_shadow.py" = "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484"
    "query_classification.py" = "193C690E4D62798566B57D84BD590DB04655357FD6DE86AE4F56EB5E16E35576"
    "normalizer.py" = "3AC3E4381FDB3501FF01E1D19BE317CBDCB03B214034409284E29A2D1303DDDB"
    "complexity.py" = "1A479E52DD552F92086D3A4D199FC54F9D0BAE77CC6B15924962570B9B425022"
    "service.py" = "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"
    "executor.py" = "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"
}

Write-Host ""
Write-Host "=== FROZEN INPUT GUARDS ==="

$ContractHash = (Get-FileHash $ContractPath -Algorithm SHA256).Hash
Write-Host "CONTRACT_SHA256=$ContractHash"

if ($ContractHash -ne $ExpectedContractHash) {
    throw "Golden contract hash mismatch."
}

foreach ($Name in $ExpectedHashes.Keys) {
    $ContainerPath = "/app/app/orchestrator/$Name"

    $Raw = @(
        docker exec `
            $Container `
            python `
            -c `
            "import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest().upper())" `
            $ContainerPath
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Container hashcheck mislukt: $Name"
    }

    $Actual = ($Raw -join "").Trim()

    Write-Host "$Name=$Actual"

    if ($Actual -ne $ExpectedHashes[$Name]) {
        throw "Frozen runtime hash mismatch: $Name"
    }
}

Write-Host "A2E_BELT_WIDTH_CF_RUNTIME_HASHES_OK" -ForegroundColor Green


# ============================================================
# Contract payload
# ============================================================

$Rows = @(Import-Csv $ContractPath)

if ($Rows.Count -ne 200) {
    throw "Golden contract count=$($Rows.Count), verwacht 200."
}

$Tests = @(
    foreach ($Row in $Rows) {
        [pscustomobject]@{
            test_id = [string]$Row.test_id
            question = [string]$Row.question
        }
    }
)

$Payload = $Tests | ConvertTo-Json -Depth 4 -Compress


# ============================================================
# Same-process baseline versus process-local counterfactual
# ============================================================

$Python = @'
import json
import re
import sys
from enum import Enum

import app.orchestrator.understanding as understanding

from app.orchestrator.complexity import (
    assess_research_requirement,
)

from app.orchestrator.planner import (
    build_execution_plan,
)


tests = json.load(sys.stdin)

if len(tests) != 200:
    raise RuntimeError(
        f"tests={len(tests)}, expected 200"
    )


def plain(value):

    if isinstance(value, Enum):
        return value.value

    if hasattr(value, "model_dump"):
        return plain(
            value.model_dump()
        )

    if hasattr(value, "dict") and callable(value.dict):
        return plain(
            value.dict()
        )

    if isinstance(value, dict):
        return {
            str(key): plain(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            plain(item)
            for item in value
        ]

    return value


def run_plan(question):

    plan = understanding.understand_query(
        question
    )

    plan = assess_research_requirement(
        plan
    )

    plan = build_execution_plan(
        plan
    )

    return plain(plan)


original_detect = understanding.detect_belt_width


def counterfactual_detect(normalized):

    current = original_detect(
        normalized
    )

    if current is not None:
        return current


    pattern = re.compile(
        r"\bband\s+van\s+(\d{3,4})\s*mm\b",
        flags=re.IGNORECASE,
    )

    match = pattern.search(
        normalized
    )

    if match is None:
        return None


    # Counterfactual only:
    # feed an equivalent form already supported by the
    # frozen detector. No EntityCandidate is constructed here.
    transformed = (
        normalized[:match.start()]
        + match.group(1)
        + " mm band"
        + normalized[match.end():]
    )


    return original_detect(
        transformed
    )


results = []


for test in tests:

    question = test["question"]


    # Frozen current behavior.
    understanding.detect_belt_width = (
        original_detect
    )

    baseline = run_plan(
        question
    )


    # Process-local counterfactual.
    understanding.detect_belt_width = (
        counterfactual_detect
    )

    counterfactual = run_plan(
        question
    )


    # Restore after every test.
    understanding.detect_belt_width = (
        original_detect
    )


    results.append(
        {
            "test_id":
                str(test["test_id"]),

            "question":
                question,

            "baseline":
                baseline,

            "counterfactual":
                counterfactual,
        }
    )


understanding.detect_belt_width = (
    original_detect
)


print(
    json.dumps(
        results,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
)
'@


$HelperPath = "/data/promati_a2e_belt_width_cf_v1.py"

$Python |
    docker exec `
        -i `
        $Container `
        sh `
        -c `
        "cat > $HelperPath"

if ($LASTEXITCODE -ne 0) {
    throw "Counterfactual helper schrijven mislukt."
}


try {
    docker exec `
        $Container `
        python `
        -c `
        "import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_text()); print('A2E_BELT_WIDTH_CF_HELPER_SYNTAX_OK')" `
        $HelperPath

    if ($LASTEXITCODE -ne 0) {
        throw "Counterfactual helper syntaxcheck mislukt."
    }

    $Raw = @(
        $Payload |
            docker exec `
                -e PYTHONPATH=/app `
                -w /app `
                -i `
                $Container `
                python `
                $HelperPath
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Counterfactual runtime mislukt."
    }
}
finally {
    docker exec `
        $Container `
        rm `
        -f `
        $HelperPath `
        2>$null |
        Out-Null
}


$Json = ($Raw -join [Environment]::NewLine).Trim()

if ([string]::IsNullOrWhiteSpace($Json)) {
    throw "Counterfactual gaf geen JSON."
}

Write-Host "A2E_BELT_WIDTH_CF_200_COMPLETE=TRUE"
Write-Host "TEMP_HELPER_REMOVED=TRUE"


# ============================================================
# Artifact
# ============================================================

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputDir = Join-Path `
    "C:\ai-platform\artifacts\golden_testset_v1" `
    "a2e_belt_width_counterfactual_$Stamp"

New-Item `
    -ItemType Directory `
    -Path $OutputDir `
    -Force |
    Out-Null

$ResultPath = Join-Path `
    $OutputDir `
    "a2e_belt_width_counterfactual_200.json"

Set-Content `
    -Path $ResultPath `
    -Value $Json `
    -Encoding UTF8


# ============================================================
# Host-side comparison
# ============================================================

$ComparePython = @'
import json
import pathlib
import sys


path = pathlib.Path(sys.argv[1])


with path.open(
    "r",
    encoding="utf-8-sig",
) as handle:
    rows = json.load(handle)


if len(rows) != 200:
    raise RuntimeError(
        f"rows={len(rows)}, expected 200"
    )


def diff_paths(
    left,
    right,
    prefix="",
):

    diffs = []


    if type(left) is not type(right):

        diffs.append(
            prefix or "<root>"
        )

        return diffs


    if isinstance(left, dict):

        keys = sorted(
            set(left)
            | set(right)
        )

        for key in keys:

            path = (
                f"{prefix}.{key}"
                if prefix
                else key
            )

            if key not in left:

                diffs.append(
                    path + " [ADDED]"
                )

                continue


            if key not in right:

                diffs.append(
                    path + " [REMOVED]"
                )

                continue


            diffs.extend(
                diff_paths(
                    left[key],
                    right[key],
                    path,
                )
            )


        return diffs


    if isinstance(left, list):

        if left != right:
            diffs.append(
                prefix
                or "<root>"
            )

        return diffs


    if left != right:

        diffs.append(
            prefix
            or "<root>"
        )


    return diffs


def entity_value(
    plan,
    key,
):

    entity = (
        plan.get(
            "entities",
            {}
        )
        or {}
    ).get(key)


    if isinstance(
        entity,
        dict,
    ):
        return entity.get(
            "value"
        )

    return entity


changed = []
queryclass_failures = []
control_failures = []
diagnostics_domain_changes = []


controls = {
    "118",
    "154",
    "185",
    "196",
}


for row in rows:

    test_id = str(
        row["test_id"]
    )

    baseline = row[
        "baseline"
    ]

    cf = row[
        "counterfactual"
    ]


    if (
        baseline.get(
            "query_class"
        )
        != cf.get(
            "query_class"
        )
    ):
        queryclass_failures.append(
            test_id
        )


    base_diag = entity_value(
        baseline,
        "diagnostics_domain",
    )

    cf_diag = entity_value(
        cf,
        "diagnostics_domain",
    )


    if base_diag != cf_diag:

        diagnostics_domain_changes.append(
            test_id
        )


    diffs = diff_paths(
        baseline,
        cf,
    )


    if diffs:

        changed.append(
            {
                "test_id":
                    test_id,

                "question":
                    row["question"],

                "changed_paths":
                    diffs,
            }
        )


    if (
        test_id in controls
        and baseline != cf
    ):

        control_failures.append(
            test_id
        )


changed_ids = [
    row["test_id"]
    for row in changed
]


target_ids = {
    "6",
    "48",
}


target_rows = {
    str(row["test_id"]):
        row
    for row in rows
    if str(
        row["test_id"]
    ) in target_ids
}


target_width_ok = True


for test_id in sorted(
    target_ids,
    key=int,
):

    row = target_rows[
        test_id
    ]

    baseline = row[
        "baseline"
    ]

    cf = row[
        "counterfactual"
    ]


    baseline_width = entity_value(
        baseline,
        "belt_width_mm",
    )

    cf_width = entity_value(
        cf,
        "belt_width_mm",
    )


    if (
        baseline_width is not None
        or cf_width != 1200
    ):
        target_width_ok = False


    print("")
    print(
        "--------------------------------------------------"
    )

    print(
        f"TEST_ID={test_id}"
    )

    print(
        "BASELINE_BELT_WIDTH="
        + repr(
            baseline_width
        )
    )

    print(
        "CF_BELT_WIDTH="
        + repr(
            cf_width
        )
    )

    print(
        "BASELINE_PRIMARY_DOMAIN="
        + repr(
            baseline.get(
                "primary_domain"
            )
        )
    )

    print(
        "CF_PRIMARY_DOMAIN="
        + repr(
            cf.get(
                "primary_domain"
            )
        )
    )

    print(
        "BASELINE_INTENT="
        + repr(
            baseline.get(
                "intent"
            )
        )
    )

    print(
        "CF_INTENT="
        + repr(
            cf.get(
                "intent"
            )
        )
    )

    print(
        "BASELINE_CONFIDENCE="
        + repr(
            baseline.get(
                "confidence"
            )
        )
    )

    print(
        "CF_CONFIDENCE="
        + repr(
            cf.get(
                "confidence"
            )
        )
    )

    print(
        "BASELINE_CLARIFICATION="
        + repr(
            baseline.get(
                "clarification_required"
            )
        )
    )

    print(
        "CF_CLARIFICATION="
        + repr(
            cf.get(
                "clarification_required"
            )
        )
    )

    print(
        "BASELINE_STEP_COUNT="
        + str(
            len(
                baseline.get(
                    "execution_steps"
                )
                or []
            )
        )
    )

    print(
        "CF_STEP_COUNT="
        + str(
            len(
                cf.get(
                    "execution_steps"
                )
                or []
            )
        )
    )

    changed_row = next(
        (
            item
            for item in changed
            if item["test_id"]
                == test_id
        ),
        None,
    )

    print(
        "CHANGED_PATHS="
        + repr(
            (
                changed_row[
                    "changed_paths"
                ]
                if changed_row
                else []
            )
        )
    )


exact_scope = (
    set(changed_ids)
    == target_ids
)


invariants_198 = (
    len(changed_ids) == 2
    and exact_scope
)


print("")
print("=== A2e BELT_WIDTH COUNTERFACTUAL ===")

print("TOTAL=200")

print(
    f"CHANGED_TEST_COUNT="
    f"{len(changed_ids)}"
)

print(
    "CHANGED_TEST_IDS="
    + ",".join(
        sorted(
            changed_ids,
            key=int,
        )
    )
)

print(
    f"INVARIANT_TEST_COUNT="
    f"{200-len(changed_ids)}"
)

print(
    "QUERYCLASS_CHANGES="
    + str(
        len(
            queryclass_failures
        )
    )
)

print(
    "A2C_A2D_CONTROL_FAILURES="
    + str(
        len(
            control_failures
        )
    )
)

print(
    "DIAGNOSTICS_DOMAIN_CHANGES="
    + str(
        len(
            diagnostics_domain_changes
        )
    )
)


print("")
print(
    "BELT_WIDTH_CF_EXACT_TARGET_SCOPE_6_48="
    + str(
        exact_scope
    ).upper()
)

print(
    "BELT_WIDTH_CF_TARGET_WIDTH_1200_FIXED="
    + str(
        target_width_ok
    ).upper()
)

print(
    "BELT_WIDTH_CF_INVARIANTS_198="
    + str(
        invariants_198
    ).upper()
)

print(
    "BELT_WIDTH_CF_QUERYCLASS_200_INVARIANT="
    + str(
        len(
            queryclass_failures
        ) == 0
    ).upper()
)

print(
    "BELT_WIDTH_CF_A2C_A2D_CONTROLS_INVARIANT="
    + str(
        len(
            control_failures
        ) == 0
    ).upper()
)

print(
    "BELT_WIDTH_CF_DIAGNOSTICS_DOMAIN_INVARIANT="
    + str(
        len(
            diagnostics_domain_changes
        ) == 0
    ).upper()
)


safe_candidate = (
    exact_scope
    and target_width_ok
    and invariants_198
    and not queryclass_failures
    and not control_failures
    and not diagnostics_domain_changes
)


print("")
print(
    "BELT_WIDTH_MINIMAL_DETECTOR_PATCH_CANDIDATE="
    + str(
        safe_candidate
    ).upper()
)


if safe_candidate:

    print(
        "A2E_BELT_WIDTH_NEXT_STEP="
        "STRUCTURAL_LOCAL_PATCH_DESIGN"
    )

else:

    print(
        "A2E_BELT_WIDTH_NEXT_STEP="
        "DO_NOT_PATCH_REVIEW_COUNTERFACTUAL_DELTAS"
    )


print("")
print("NO_APP_CODE_CHANGED=TRUE")
print("NO_EXECUTOR_CALLED=TRUE")
print("NO_SPECIALIST_CALLED=TRUE")
print("NO_RESEARCH_PROVIDER_CALLED=TRUE")
print("NO_DB_WRITES=TRUE")
print("PHASE_A_A2E_BELT_WIDTH_COUNTERFACTUAL_OK")
'@


$CompareOutput = @(
    $ComparePython |
        & python - `
            $ResultPath
)

$CompareExit = $LASTEXITCODE

$CompareOutput | ForEach-Object {
    Write-Host $_
}

if ($CompareExit -ne 0) {
    throw "Counterfactual comparator mislukt."
}


# ============================================================
# Final runtime hash guards
# ============================================================

foreach ($Name in $ExpectedHashes.Keys) {
    $ContainerPath = "/app/app/orchestrator/$Name"

    $RawHash = @(
        docker exec `
            $Container `
            python `
            -c `
            "import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest().upper())" `
            $ContainerPath
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Final runtime hashcheck mislukt: $Name"
    }

    $Actual = ($RawHash -join "").Trim()

    if ($Actual -ne $ExpectedHashes[$Name]) {
        throw "Runtime veranderde tijdens counterfactual: $Name"
    }
}

Write-Host ""
Write-Host "RUNTIME_ARTIFACT=$ResultPath"
Write-Host "RUNTIME_ARTIFACT_SHA256=$((Get-FileHash $ResultPath -Algorithm SHA256).Hash)"

Write-Host "PROMATI_APP_CODE_CHANGED=FALSE"
Write-Host "PROCESS_LOCAL_MONKEYPATCH_RESTORED=TRUE"
Write-Host "TEMP_HELPER_REMOVED=TRUE"
Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_EXECUTOR_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_RESEARCH_PROVIDER_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"

Write-Host "PHASE_A_A2E_BELT_WIDTH_COUNTERFACTUAL_COMPLETE" -ForegroundColor Green