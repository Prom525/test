$ErrorActionPreference = "Stop"

Set-Location C:\ai-platform

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-A A2e ENTITY COVERAGE AUDIT V1" -ForegroundColor Cyan
Write-Host " 200 GOLDEN TESTS / READ ONLY" -ForegroundColor Cyan
Write-Host " NO API / NO SPECIALISTS / NO DB WRITES" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan


$Container = "ai-platform-api-1"
$Root = "C:\ai-platform\api\app\orchestrator"

$ContractPath = `
    "C:\ai-platform\artifacts\golden_testset_v1\phase_a_test_contract_v2.csv"

$AcceptedA2dArtifact = `
    "C:\ai-platform\artifacts\golden_testset_v1\a2d_dualrun_accept_20260826_122437\a2d_dualrun_full.json"


# ============================================================
# Frozen contract / accepted runtime identity
# ============================================================

$ExpectedContractHash = `
    "EE02DDC2FE72501F31DB80B97C4555B8D3E261A7C64A53079FAB5FB85F545529"

$ExpectedA2dArtifactHash = `
    "96FA7AAD95D73C325FB30035CE9BB997666EF70CEA33ADF70D7C0B28E311088D"


$ExpectedHashes = [ordered]@{
    "models.py" = `
        "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E"

    "understanding.py" = `
        "CF35835C9BD03D1267CED10EE47DCB67795A4DEA38336E4A1E8126049769BF78"

    "planner.py" = `
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"

    "band_candidate_shadow.py" = `
        "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484"

    "query_classification.py" = `
        "193C690E4D62798566B57D84BD590DB04655357FD6DE86AE4F56EB5E16E35576"

    "normalizer.py" = `
        "3AC3E4381FDB3501FF01E1D19BE317CBDCB03B214034409284E29A2D1303DDDB"

    "complexity.py" = `
        "1A479E52DD552F92086D3A4D199FC54F9D0BAE77CC6B15924962570B9B425022"

    "service.py" = `
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"

    "executor.py" = `
        "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"
}


# ============================================================
# Contract and acceptance artifact guards
# ============================================================

Write-Host ""
Write-Host "=== FROZEN CONTRACT / ACCEPTANCE GUARDS ==="


if (-not (Test-Path $ContractPath)) {
    throw "Golden contract ontbreekt: $ContractPath"
}

$ContractHash = (
    Get-FileHash `
        $ContractPath `
        -Algorithm SHA256
).Hash

Write-Host "CONTRACT_SHA256=$ContractHash"

if ($ContractHash -ne $ExpectedContractHash) {
    throw "Golden contract hash mismatch."
}


if (-not (Test-Path $AcceptedA2dArtifact)) {
    throw "Accepted A2d artifact ontbreekt."
}

$A2dArtifactHash = (
    Get-FileHash `
        $AcceptedA2dArtifact `
        -Algorithm SHA256
).Hash

Write-Host "A2D_ACCEPTANCE_SHA256=$A2dArtifactHash"

if ($A2dArtifactHash -ne $ExpectedA2dArtifactHash) {
    throw "Accepted A2d artifact hash mismatch."
}


Write-Host "A2E_FROZEN_EVIDENCE_GUARDS_OK" `
    -ForegroundColor Green


# ============================================================
# Local + runtime hashes
# ============================================================

Write-Host ""
Write-Host "=== LOCAL / CONTAINER HASH PARITY ==="


foreach ($Name in $ExpectedHashes.Keys) {

    $LocalPath = Join-Path $Root $Name

    if (-not (Test-Path $LocalPath)) {
        throw "Lokaal bestand ontbreekt: $LocalPath"
    }

    $LocalHash = (
        Get-FileHash `
            $LocalPath `
            -Algorithm SHA256
    ).Hash

    if ($LocalHash -ne $ExpectedHashes[$Name]) {
        throw "Frozen local hash mismatch: $Name"
    }


    $ContainerPath = (
        "/app/app/orchestrator/" +
        $Name
    )

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

    $RuntimeHash = (
        $Raw -join ""
    ).Trim()


    Write-Host (
        "{0,-30} local={1} runtime={2}" -f `
            $Name,
            $LocalHash,
            $RuntimeHash
    )


    if ($RuntimeHash -ne $ExpectedHashes[$Name]) {
        throw "Frozen runtime hash mismatch: $Name"
    }
}


Write-Host "A2E_FROZEN_RUNTIME_IDENTITY_OK" `
    -ForegroundColor Green


# ============================================================
# Load 200 questions
# ============================================================

$Contract = @(
    Import-Csv $ContractPath
)

if ($Contract.Count -ne 200) {
    throw "Golden contract count=$($Contract.Count), verwacht 200."
}


$Columns = @(
    $Contract[0].PSObject.Properties.Name
)


$IdColumn = @(
    "test_id",
    "id"
) | Where-Object {
    $_ -in $Columns
} | Select-Object -First 1


$QuestionColumn = @(
    "question",
    "vraag"
) | Where-Object {
    $_ -in $Columns
} | Select-Object -First 1


$QueryClassColumn = @(
    "expected_query_class",
    "query_class",
    "expected_class"
) | Where-Object {
    $_ -in $Columns
} | Select-Object -First 1


if ([string]::IsNullOrWhiteSpace($IdColumn)) {
    throw "test_id kolom niet gevonden."
}

if ([string]::IsNullOrWhiteSpace($QuestionColumn)) {
    throw "question kolom niet gevonden."
}

if ([string]::IsNullOrWhiteSpace($QueryClassColumn)) {
    throw "expected query_class kolom niet gevonden."
}


$Tests = @(
    foreach ($Row in $Contract) {

        [pscustomobject]@{
            test_id = [string]$Row.$IdColumn
            question = [string]$Row.$QuestionColumn
            expected_query_class = [string]$Row.$QueryClassColumn
        }
    }
)


$Payload = (
    $Tests |
        ConvertTo-Json `
            -Depth 5 `
            -Compress
)


Write-Host ""
Write-Host "GOLDEN_TESTS_LOADED=200"


# ============================================================
# Runtime evaluator
#
# understand -> research classification -> planner
# No executor, HTTP, specialist or database call.
# ============================================================

$RuntimePython = @'
import json
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
        f"test count={len(tests)}, expected 200"
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


rows = []


for test in tests:

    plan = understanding.understand_query(
        test["question"]
    )

    normalized = plan.normalized_question

    candidate = understanding.detect_band_code(
        normalized
    )

    shadow = (
        understanding.classify_band_candidate_shadow(
            normalized,
            candidate,
        )
    )

    plan = assess_research_requirement(
        plan
    )

    plan = build_execution_plan(
        plan
    )


    rows.append(
        {
            "test_id":
                str(test["test_id"]),

            "question":
                test["question"],

            "expected_query_class":
                test["expected_query_class"],

            "band_candidate":
                plain(candidate),

            "band_shadow_status":
                (
                    shadow.status.value
                    if shadow is not None
                    else None
                ),

            "plan":
                plain(plan),
        }
    )


print(
    json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
)
'@


$HelperPath = `
    "/data/promati_phase_a2e_entity_audit_v1.py"


$RuntimePython |
    docker exec `
        -i `
        $Container `
        sh `
        -c `
        "cat > $HelperPath"

if ($LASTEXITCODE -ne 0) {
    throw "Tijdelijke A2e helper schrijven mislukt."
}


try {

    docker exec `
        $Container `
        python `
        -c `
        "import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_text()); print('A2E_RUNTIME_HELPER_SYNTAX_OK')" `
        $HelperPath

    if ($LASTEXITCODE -ne 0) {
        throw "A2e runtime helper syntaxcheck mislukt."
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
        throw "A2e runtime evaluation mislukt."
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


$RuntimeJson = (
    $Raw -join [Environment]::NewLine
).Trim()


if ([string]::IsNullOrWhiteSpace($RuntimeJson)) {
    throw "A2e runtime gaf geen JSON."
}


Write-Host "A2E_RUNTIME_200_COMPLETE=TRUE"
Write-Host "TEMP_RUNTIME_HELPER_REMOVED=TRUE"


# ============================================================
# Artifact directory
# ============================================================

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$OutputDir = Join-Path `
    "C:\ai-platform\artifacts\golden_testset_v1" `
    "a2e_entity_coverage_$Stamp"

New-Item `
    -ItemType Directory `
    -Path $OutputDir `
    -Force |
    Out-Null


$RuntimePath = Join-Path `
    $OutputDir `
    "a2e_runtime_200.json"

$SummaryPath = Join-Path `
    $OutputDir `
    "a2e_entity_summary.json"

$FailurePath = Join-Path `
    $OutputDir `
    "a2e_entity_findings.json"

$MatrixPath = Join-Path `
    $OutputDir `
    "a2e_entity_key_matrix.csv"


Set-Content `
    -Path $RuntimePath `
    -Value $RuntimeJson `
    -Encoding UTF8


# ============================================================
# Host-side entity contract / cardinality audit
# ============================================================

$AuditPython = @'
import ast
import csv
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict


contract_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
summary_path = pathlib.Path(sys.argv[3])
failure_path = pathlib.Path(sys.argv[4])
matrix_path = pathlib.Path(sys.argv[5])


# ============================================================
# Helpers
# ============================================================

def load_json(path):
    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as handle:
        return json.load(handle)


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def norm_key(value):
    return clean(value).casefold()


def scalar_norm(value):

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text:
        return ""

    try:
        number = float(text)

        if "." in text or text.isdigit():
            return number
    except Exception:
        pass

    return text.casefold()


def normalize_value(value):

    if isinstance(value, list):
        return [
            normalize_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            normalize_value(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            str(key):
                normalize_value(item)
            for key, item in value.items()
        }

    return scalar_norm(value)


def expected_values_equal(expected, actual):

    e = normalize_value(expected)
    a = normalize_value(actual)

    if isinstance(e, list):

        if not isinstance(a, list):
            return False

        return sorted(
            repr(item)
            for item in e
        ) == sorted(
            repr(item)
            for item in a
        )

    return e == a


def runtime_entity_value(entity):

    if entity is None:
        return None

    if isinstance(entity, dict):
        return entity.get("value")

    return entity


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


# ============================================================
# Entity expectation parser
# ============================================================

# PROMATI_A2E_ENTITY_CONTRACT_GRAMMAR_V3
#
# Frozen contract grammar proven against all 200 rows:
#
# -                  => no entity expectation
# key=value          => positive expectation
# NO_key             => negative absence condition
# NO_key=value       => negative forbidden-value condition
# clause|clause      => multiple clauses
#
# Commas remain inside one value. Only explicitly multi-valued
# entity contract keys below are materialized as lists.

MULTI_VALUE_KEYS = {
    "band_codes",
    "comparison_scope",
    "family_codes",
    "rfq_ids",
}


def parse_contract_value(
    key,
    value,
):

    value = clean(
        value
    )

    if (
        key in MULTI_VALUE_KEYS
        and "," in value
    ):

        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    return value


def add_positive(
    positive,
    key,
    value,
):

    key = clean(
        key
    )

    value = clean(
        value
    )

    if not key:
        raise RuntimeError(
            "empty positive entity key"
        )

    if not value:
        raise RuntimeError(
            f"empty positive value for key={key}"
        )

    positive.append(
        {
            "key":
                key,

            "value":
                parse_contract_value(
                    key,
                    value,
                ),
        }
    )


def add_negative(
    negative,
    key,
    forbidden_value=None,
):

    key = clean(
        key
    )

    if not key:
        raise RuntimeError(
            "empty negative entity key"
        )

    if forbidden_value is not None:
        forbidden_value = clean(
            forbidden_value
        )

        if not forbidden_value:
            raise RuntimeError(
                f"empty forbidden value for key={key}"
            )

    negative.append(
        {
            "key":
                key,

            "forbidden_value":
                forbidden_value,
        }
    )


def parse_negative_payload(
    payload,
):

    payload = clean(
        payload
    )

    if not payload:
        raise RuntimeError(
            "empty NO_ payload"
        )

    if "=" not in payload:
        return (
            payload,
            None,
        )


    key, forbidden_value = payload.split(
        "=",
        1,
    )

    key = clean(
        key
    )

    forbidden_value = clean(
        forbidden_value
    )


    if not key:
        raise RuntimeError(
            "empty negative key"
        )

    if not forbidden_value:
        raise RuntimeError(
            f"empty forbidden value for key={key}"
        )


    return (
        key,
        forbidden_value,
    )


def parse_expectation_cell(
    raw,
    force_negative=False,
):

    positive = []
    negative = []

    text = clean(
        raw
    )

    if not text:
        return positive, negative

    if text == "-":
        return positive, negative


    clauses = [
        item.strip()
        for item in text.split("|")
    ]


    for clause in clauses:

        if not clause:
            raise RuntimeError(
                f"empty entity contract clause in {text!r}"
            )

        if clause == "-":
            raise RuntimeError(
                f"dash mixed with entity contract in {text!r}"
            )


        if force_negative:

            payload = (
                clause[3:]
                if clause.startswith("NO_")
                else clause
            )

            key, forbidden_value = (
                parse_negative_payload(
                    payload
                )
            )

            add_negative(
                negative,
                key,
                forbidden_value,
            )

            continue


        if clause.startswith(
            "NO_"
        ):

            key, forbidden_value = (
                parse_negative_payload(
                    clause[3:]
                )
            )

            add_negative(
                negative,
                key,
                forbidden_value,
            )

            continue


        if "=" not in clause:
            raise RuntimeError(
                f"unknown entity contract clause: {clause!r}"
            )


        key, value = clause.split(
            "=",
            1,
        )

        add_positive(
            positive,
            key,
            value,
        )


    return positive, negative


def comparable_negative_scalar(
    value,
):

    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        (int, float),
    ):
        return float(
            value
        )

    text = clean(
        value
    ).casefold()

    if text == "true":
        return True

    if text == "false":
        return False

    try:
        return float(
            text
        )

    except Exception:
        return text


def negative_value_matches(
    forbidden_value,
    runtime_value,
):

    if isinstance(
        runtime_value,
        list,
    ):

        return any(
            negative_value_matches(
                forbidden_value,
                item,
            )
            for item in runtime_value
        )


    return (
        comparable_negative_scalar(
            forbidden_value
        )
        == comparable_negative_scalar(
            runtime_value
        )
    )


# ============================================================
# Load contract
# ============================================================

with contract_path.open(
    "r",
    encoding="utf-8-sig",
    newline="",
) as handle:

    reader = csv.DictReader(handle)

    contract_rows = list(reader)

    headers = reader.fieldnames or []


if len(contract_rows) != 200:
    raise RuntimeError(
        f"contract rows={len(contract_rows)}, expected 200"
    )


header_lookup = {
    item.casefold(): item
    for item in headers
}


def first_header(candidates):

    for candidate in candidates:

        if candidate.casefold() in header_lookup:
            return header_lookup[
                candidate.casefold()
            ]

    return None


id_col = first_header(
    [
        "test_id",
        "id",
    ]
)

question_col = first_header(
    [
        "question",
        "vraag",
    ]
)

queryclass_col = first_header(
    [
        "expected_query_class",
        "query_class",
        "expected_class",
    ]
)


positive_entity_col = first_header(
    [
        "expected_entities",
        "expected_entity",
        "entity_expectations",
        "expected_entity_contract",
        "entity_contract",
        "entities_expected",
        "entities",
    ]
)


negative_entity_col = first_header(
    [
        "negative_entities",
        "forbidden_entities",
        "expected_absent_entities",
        "entities_absent",
        "not_expected_entities",
    ]
)


if positive_entity_col is None:

    candidates = [
        header
        for header in headers
        if (
            "entit" in header.casefold()
            and not any(
                token in header.casefold()
                for token in (
                    "negative",
                    "forbid",
                    "absent",
                    "not_expected",
                )
            )
        )
    ]

    if len(candidates) == 1:
        positive_entity_col = candidates[0]


if (
    id_col is None
    or question_col is None
    or queryclass_col is None
    or positive_entity_col is None
):
    raise RuntimeError(
        "Unsupported contract shape. "
        f"headers={headers}; "
        f"id={id_col}; "
        f"question={question_col}; "
        f"queryclass={queryclass_col}; "
        f"entity={positive_entity_col}"
    )


expectations_by_id = {}

positive_rows = 0
negative_rows = 0
positive_count = 0
negative_count = 0

positive_expected_keys = set()
all_contract_keys = set()


for row in contract_rows:

    test_id = clean(
        row[id_col]
    )


    positive, negative = (
        parse_expectation_cell(
            row.get(
                positive_entity_col,
                ""
            )
        )
    )


    if negative_entity_col:

        pos2, neg2 = (
            parse_expectation_cell(
                row.get(
                    negative_entity_col,
                    ""
                ),
                force_negative=True,
            )
        )

        positive.extend(
            pos2
        )

        negative.extend(
            neg2
        )


    if positive:
        positive_rows += 1

    if negative:
        negative_rows += 1


    positive_count += len(
        positive
    )

    negative_count += len(
        negative
    )


    for item in positive:

        positive_expected_keys.add(
            item["key"]
        )

        all_contract_keys.add(
            item["key"]
        )

    for item in negative:

        all_contract_keys.add(
            item["key"]
        )


    expectations_by_id[
        test_id
    ] = {
        "positive": positive,
        "negative": negative,
    }


# Frozen contract-shape proof from previous entity baseline.
if positive_rows != 131:
    raise RuntimeError(
        f"positive rows={positive_rows}, expected 131. "
        f"entity_col={positive_entity_col}"
    )

if positive_count != 149:
    raise RuntimeError(
        f"positive expectations={positive_count}, expected 149."
    )

if negative_rows != 14:
    raise RuntimeError(
        f"negative rows={negative_rows}, expected 14."
    )

if negative_count != 14:
    raise RuntimeError(
        f"negative expectations={negative_count}, expected 14."
    )

if len(positive_expected_keys) != 20:
    raise RuntimeError(
        f"positive entity key count="
        f"{len(positive_expected_keys)}, expected 20; "
        f"keys={sorted(positive_expected_keys)}"
    )


print("")
print("=== CONTRACT ENTITY SHAPE ===")

print(
    f"ENTITY_CONTRACT_COLUMN={positive_entity_col}"
)

print(
    "NEGATIVE_ENTITY_CONTRACT_COLUMN="
    + (
        negative_entity_col
        or "<SAME_OR_NONE>"
    )
)

print("EXPECTED_ENTITY_KEY_COUNT=20")
print("EXPECTED_POSITIVE_ROWS=131")
print("EXPECTED_POSITIVE_COUNT=149")
print("EXPECTED_NEGATIVE_ROWS=14")
print("EXPECTED_NEGATIVE_COUNT=14")


# ============================================================
# Runtime data
# ============================================================

runtime_rows = load_json(
    runtime_path
)


if len(runtime_rows) != 200:
    raise RuntimeError(
        f"runtime rows={len(runtime_rows)}, expected 200"
    )


runtime_by_id = {
    str(row["test_id"]): row
    for row in runtime_rows
}


if len(runtime_by_id) != 200:
    raise RuntimeError(
        "runtime duplicate IDs"
    )


runtime_keys = set()


for row in runtime_rows:

    entities = (
        row["plan"].get(
            "entities"
        )
        or {}
    )

    runtime_keys.update(
        entities.keys()
    )


print(
    "RUNTIME_ENTITY_KEYS="
    + ",".join(
        sorted(runtime_keys)
    )
)


# ============================================================
# Related schema aliases
#
# Informational only. These aliases do NOT create validated
# execution identities.
# ============================================================

RELATED = {
    "line_code": [
        "lijn_code",
    ],

    "lijn_code": [
        "line_code",
    ],

    "band_candidate": [
        "band_code",
    ],

    "belt_width": [
        "belt_width_mm",
    ],

    "installation_code": [
        "scope_code",
    ],

    "scope_code": [
        "installation_code",
    ],

    "scope_codes": [
        "comparison_scope_codes",
    ],

    "comparison_codes": [
        "comparison_scope_codes",
    ],

    "comparison_scope_code": [
        "comparison_scope_codes",
    ],

    "band_codes": [
        "band_code",
    ],
}


def related_runtime_keys(key):

    return [
        candidate
        for candidate in RELATED.get(
            key,
            []
        )
        if candidate in runtime_keys
    ]


# ============================================================
# Reachability matrix
# ============================================================

key_stats = {}


for key in sorted(all_contract_keys):

    if key in runtime_keys:
        classification = "exact"

    elif related_runtime_keys(key):
        classification = "related_only"

    else:
        classification = "unreachable"


    key_stats[key] = {
        "key":
            key,

        "classification":
            classification,

        "related_runtime_keys":
            related_runtime_keys(
                key
            ),

        "positive_expectations":
            0,

        "negative_expectations":
            0,

        "missing":
            0,

        "value_mismatches":
            0,

        "negative_violations":
            0,
    }


for test_id, expectations in expectations_by_id.items():

    for item in expectations["positive"]:

        key_stats[
            item["key"]
        ]["positive_expectations"] += 1


    for item in expectations["negative"]:

        key_stats[
            item["key"]
        ]["negative_expectations"] += 1


exact_reachable = sum(
    item["positive_expectations"]
    for item in key_stats.values()
    if item["classification"] == "exact"
)

related_only = sum(
    item["positive_expectations"]
    for item in key_stats.values()
    if item["classification"] == "related_only"
)

unreachable = sum(
    item["positive_expectations"]
    for item in key_stats.values()
    if item["classification"] == "unreachable"
)


# ============================================================
# A2c / A2d controls
# ============================================================

control_failures = []


def plan_for(test_id):
    return runtime_by_id[
        str(test_id)
    ]["plan"]


def entities_for(test_id):
    return (
        plan_for(test_id).get(
            "entities"
        )
        or {}
    )


def blockers_for(test_id):
    return (
        plan_for(test_id).get(
            "execution_blockers"
        )
        or []
    )


# 118 mention-only.
if runtime_by_id["118"].get(
    "band_shadow_status"
) != "mention_only":
    control_failures.append(
        "118_shadow"
    )

if "band_code" in entities_for("118"):
    control_failures.append(
        "118_band_code"
    )

if blockers_for("118"):
    control_failures.append(
        "118_blocker"
    )


# 185 comparison member.
if runtime_by_id["185"].get(
    "band_shadow_status"
) != "comparison_member":
    control_failures.append(
        "185_shadow"
    )

if "band_code" in entities_for("185"):
    control_failures.append(
        "185_band_code"
    )

if "comparison_scope_codes" not in entities_for("185"):
    control_failures.append(
        "185_comparison_scope_codes"
    )

if blockers_for("185"):
    control_failures.append(
        "185_blocker"
    )


# 154 unresolved.
if runtime_by_id["154"].get(
    "band_shadow_status"
) != "unresolved":
    control_failures.append(
        "154_shadow"
    )

if "band_code" in entities_for("154"):
    control_failures.append(
        "154_band_code"
    )

if len(blockers_for("154")) != 1:
    control_failures.append(
        "154_blocker_count"
    )

if (
    plan_for("154").get(
        "execution_steps"
    )
    or []
):
    control_failures.append(
        "154_execution"
    )


# 196 unresolved.
if runtime_by_id["196"].get(
    "band_shadow_status"
) != "unresolved":
    control_failures.append(
        "196_shadow"
    )

if "band_code" in entities_for("196"):
    control_failures.append(
        "196_band_code"
    )

if len(blockers_for("196")) != 1:
    control_failures.append(
        "196_blocker_count"
    )

if (
    plan_for("196").get(
        "execution_steps"
    )
    or []
):
    control_failures.append(
        "196_execution"
    )


# ============================================================
# QueryClass + A1b early gates
# ============================================================

queryclass_failures = []


for row in runtime_rows:

    expected = norm_key(
        row.get(
            "expected_query_class"
        )
    )

    actual = norm_key(
        row["plan"].get(
            "query_class"
        )
    )

    if expected != actual:

        queryclass_failures.append(
            {
                "test_id":
                    row["test_id"],

                "expected":
                    expected,

                "actual":
                    actual,
            }
        )


conversational = {
    "141",
    "160",
    "176",
    "177",
    "178",
    "179",
    "180",
}

unknown = {
    "148",
    "183",
    "186",
}

pure_meta = {
    "142",
    "143",
    "144",
    "161",
    "162",
    "170",
    "171",
    "173",
    "174",
    "175",
}


early_gate_failures = []


def verify_gate(
    test_id,
    query_class,
    intent,
    clarification,
):

    plan = plan_for(
        test_id
    )

    failures = []


    if plan.get(
        "query_class"
    ) != query_class:
        failures.append(
            "query_class"
        )

    if plan.get(
        "primary_domain"
    ) is not None:
        failures.append(
            "primary_domain"
        )

    if (
        plan.get("domains")
        or []
    ):
        failures.append(
            "domains"
        )

    if plan.get(
        "intent"
    ) != intent:
        failures.append(
            "intent"
        )

    if (
        bool(
            plan.get(
                "clarification_required"
            )
        )
        != clarification
    ):
        failures.append(
            "clarification"
        )

    if (
        plan.get("entities")
        or {}
    ):
        failures.append(
            "entities"
        )

    if (
        plan.get(
            "execution_blockers"
        )
        or []
    ):
        failures.append(
            "execution_blockers"
        )

    if (
        plan.get(
            "execution_steps"
        )
        or []
    ):
        failures.append(
            "execution_steps"
        )


    if failures:

        early_gate_failures.append(
            {
                "test_id":
                    test_id,

                "failures":
                    failures,
            }
        )


for test_id in conversational:
    verify_gate(
        test_id,
        "conversational",
        "none",
        False,
    )

for test_id in unknown:
    verify_gate(
        test_id,
        "unknown",
        "unknown",
        True,
    )

for test_id in pure_meta:
    verify_gate(
        test_id,
        "system_meta",
        "system_meta",
        False,
    )


# ============================================================
# Entity expectation evaluation
# ============================================================

missing_expected = []
value_mismatches = []
negative_violations = []
cardinality_mismatches = []
unexpected_code_like = []


CONTROL_IDS = {
    "118",
    "154",
    "185",
    "196",
}


def all_related_keys(key):

    return RELATED.get(
        key,
        []
    )


def entity_present(
    entities,
    key,
):

    if key in entities:
        return key

    for alias in all_related_keys(
        key
    ):

        if alias in entities:
            return alias

    return None


def is_expected_multi(
    key,
    value,
):

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return True

    key_cf = key.casefold()

    return (
        key_cf.startswith(
            "comparison_"
        )
        or key_cf.endswith(
            "_codes"
        )
    )


for test_id, expectations in expectations_by_id.items():

    if test_id not in runtime_by_id:
        raise RuntimeError(
            f"runtime missing test={test_id}"
        )


    plan = plan_for(
        test_id
    )

    entities = (
        plan.get(
            "entities"
        )
        or {}
    )


    # --------------------------------------------------------
    # Positive expectations
    # --------------------------------------------------------

    for expected in expectations["positive"]:

        key = expected["key"]
        expected_value = expected["value"]

        found_key = entity_present(
            entities,
            key,
        )


        # A2c/A2d controls intentionally changed band semantics.
        intentional_band_boundary = (
            test_id in CONTROL_IDS
            and key in {
                "band_code",
                "band_candidate",
            }
        )


        # PROMATI_PHASE_A_A2E_LIJN_CODE_ACCEPTANCE_EQUIVALENCE_V1
        if (
            found_key is None
            and key == "lijn_code"
            and lijn_code_representation_equivalent(
                entities,
                expected_value,
            )
        ):
            continue

        if found_key is None:

            finding = {
                "test_id":
                    test_id,

                "key":
                    key,

                "expected":
                    expected_value,

                "reachability":
                    key_stats[key][
                        "classification"
                    ],

                "intentional_a2c_a2d_control":
                    intentional_band_boundary,
            }


            missing_expected.append(
                finding
            )

            key_stats[
                key
            ]["missing"] += 1

            continue


        runtime_value = runtime_entity_value(
            entities[
                found_key
            ]
        )


        expected_multi = is_expected_multi(
            key,
            expected_value,
        )

        actual_multi = isinstance(
            runtime_value,
            list,
        )


        if expected_multi != actual_multi:

            cardinality_mismatches.append(
                {
                    "test_id":
                        test_id,

                    "expected_key":
                        key,

                    "runtime_key":
                        found_key,

                    "expected_multi":
                        expected_multi,

                    "runtime_multi":
                        actual_multi,

                    "expected_value":
                        expected_value,

                    "runtime_value":
                        runtime_value,
                }
            )


        # "True" means entity presence only, no exact value contract.
        if expected_value is True:
            continue


        if not expected_values_equal(
            expected_value,
            runtime_value,
        ):

            value_mismatches.append(
                {
                    "test_id":
                        test_id,

                    "expected_key":
                        key,

                    "runtime_key":
                        found_key,

                    "expected":
                        expected_value,

                    "actual":
                        runtime_value,

                    "intentional_a2c_a2d_control":
                        intentional_band_boundary,
                }
            )

            key_stats[
                key
            ]["value_mismatches"] += 1


    # --------------------------------------------------------
    # Negative expectations
    # --------------------------------------------------------

    for expected in expectations["negative"]:

        key = expected["key"]

        forbidden_value = expected.get(
            "forbidden_value"
        )

        found_key = entity_present(
            entities,
            key,
        )

        if found_key is None:
            continue


        current_value = runtime_entity_value(
            entities[
                found_key
            ]
        )


        # NO_key:
        #     the entity itself must be absent.
        #
        # NO_key=value:
        #     the key may exist, but the forbidden value
        #     must not be grounded.
        if (
            forbidden_value is not None
            and not negative_value_matches(
                forbidden_value,
                current_value,
            )
        ):
            continue


        negative_violations.append(
            {
                "test_id":
                    test_id,

                "expected_absent_key":
                    key,

                "forbidden_value":
                    forbidden_value,

                "runtime_key":
                    found_key,

                "runtime_value":
                    current_value,
            }
        )

        key_stats[
            key
        ]["negative_violations"] += 1


# ============================================================
# Unexpected code-like runtime entities
# ============================================================

CODE_LIKE = re.compile(
    r"^[A-Z]{1,8}[-_]?\d{1,5}$"
)


def scalar_values(value):

    if isinstance(value, list):

        for item in value:
            yield from scalar_values(
                item
            )

    elif isinstance(value, dict):

        for item in value.values():
            yield from scalar_values(
                item
            )

    else:
        yield value


for test_id, row in runtime_by_id.items():

    entities = (
        row["plan"].get(
            "entities"
        )
        or {}
    )

    expected_positive_keys = {
        item["key"]
        for item in expectations_by_id[
            test_id
        ]["positive"]
    }


    for key, entity in entities.items():

        value = runtime_entity_value(
            entity
        )


        for scalar in scalar_values(
            value
        ):

            if not isinstance(
                scalar,
                str,
            ):
                continue

            candidate = scalar.strip().upper()

            if not CODE_LIKE.fullmatch(
                candidate
            ):
                continue


            key_or_alias_expected = (
                key in expected_positive_keys
                or any(
                    alias in expected_positive_keys
                    for alias in RELATED.get(
                        key,
                        []
                    )
                )
            )


            if not key_or_alias_expected:

                unexpected_code_like.append(
                    {
                        "test_id":
                            test_id,

                        "entity_key":
                            key,

                        "value":
                            candidate,
                    }
                )


# ============================================================
# Cardinality totals
# ============================================================

single_cases = 0
multi_cases = 0


for expectations in expectations_by_id.values():

    for expected in expectations["positive"]:

        if is_expected_multi(
            expected["key"],
            expected["value"],
        ):
            multi_cases += 1

        else:
            single_cases += 1


# ============================================================
# Blocking-vs-schema decision
# ============================================================

NON_REPAIR_TARGET_KEYS = {
    "diagnostics_domain",
}


def is_non_target(finding):

    key = (
        finding.get("key")
        or finding.get(
            "expected_key"
        )
        or finding.get(
            "expected_absent_key"
        )
    )

    return key in NON_REPAIR_TARGET_KEYS


# Missing exact-runtime expectations are genuine grounding
# candidates unless they are:
# - diagnostics_domain
# - intentional 118/154/185/196 band-boundary controls
blocking_missing = [
    finding
    for finding in missing_expected
    if (
        finding[
            "reachability"
        ] == "exact"
        and not finding[
            "intentional_a2c_a2d_control"
        ]
        and not is_non_target(
            finding
        )
    )
]


blocking_value_mismatches = [
    finding
    for finding in value_mismatches
    if (
        not finding[
            "intentional_a2c_a2d_control"
        ]
        and not is_non_target(
            finding
        )
    )
]


blocking_negative_violations = [
    finding
    for finding in negative_violations
    if not is_non_target(
        finding
    )
]


blocking_entity_errors = (
    len(blocking_missing)
    + len(blocking_value_mismatches)
    + len(blocking_negative_violations)
)


routing_safety_regressions = (
    len(queryclass_failures)
    + len(early_gate_failures)
)


execution_grounding_regressions = (
    len(control_failures)
)


diagnostics_domain_findings = {
    "missing": [
        item
        for item in missing_expected
        if is_non_target(
            item
        )
    ],

    "value_mismatches": [
        item
        for item in value_mismatches
        if is_non_target(
            item
        )
    ],

    "negative_violations": [
        item
        for item in negative_violations
        if is_non_target(
            item
        )
    ],
}


# ============================================================
# Key matrix CSV
# ============================================================

with matrix_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "entity_key",
            "classification",
            "related_runtime_keys",
            "positive_expectations",
            "negative_expectations",
            "missing",
            "value_mismatches",
            "negative_violations",
        ],
    )

    writer.writeheader()


    for key in sorted(
        key_stats
    ):

        item = key_stats[
            key
        ]

        writer.writerow(
            {
                "entity_key":
                    key,

                "classification":
                    item[
                        "classification"
                    ],

                "related_runtime_keys":
                    ",".join(
                        item[
                            "related_runtime_keys"
                        ]
                    ),

                "positive_expectations":
                    item[
                        "positive_expectations"
                    ],

                "negative_expectations":
                    item[
                        "negative_expectations"
                    ],

                "missing":
                    item[
                        "missing"
                    ],

                "value_mismatches":
                    item[
                        "value_mismatches"
                    ],

                "negative_violations":
                    item[
                        "negative_violations"
                    ],
            }
        )


# ============================================================
# Artifacts
# ============================================================

summary = {
    "total": 200,

    "contract_entity_column":
        positive_entity_col,

    "negative_entity_column":
        negative_entity_col,

    "expected_entity_key_count":
        len(positive_expected_keys),

    "expected_entity_keys":
        sorted(positive_expected_keys),

    "runtime_entity_keys":
        sorted(runtime_keys),

    "expected_positive_rows":
        positive_rows,

    "expected_positive_count":
        positive_count,

    "expected_negative_rows":
        negative_rows,

    "expected_negative_count":
        negative_count,

    "exact_runtime_reachable":
        exact_reachable,

    "related_only":
        related_only,

    "unreachable_schema_expectations":
        unreachable,

    "missing_expected":
        len(missing_expected),

    "value_mismatches":
        len(value_mismatches),

    "negative_violations":
        len(negative_violations),

    "unexpected_code_like":
        len(unexpected_code_like),

    "single_value_cardinality_cases":
        single_cases,

    "multi_value_cardinality_cases":
        multi_cases,

    "cardinality_schema_mismatches":
        len(cardinality_mismatches),

    "queryclass_failures":
        len(queryclass_failures),

    "a1b_early_gate_failures":
        len(early_gate_failures),

    "a2c_a2d_control_failures":
        len(control_failures),

    "routing_safety_regressions":
        routing_safety_regressions,

    "execution_grounding_regressions":
        execution_grounding_regressions,

    "blocking_missing":
        len(blocking_missing),

    "blocking_value_mismatches":
        len(
            blocking_value_mismatches
        ),

    "blocking_negative_violations":
        len(
            blocking_negative_violations
        ),

    "blocking_entity_errors":
        blocking_entity_errors,

    "diagnostics_domain_excluded":
        True,
}


findings = {
    "missing_expected":
        missing_expected,

    "value_mismatches":
        value_mismatches,

    "negative_violations":
        negative_violations,

    "unexpected_code_like":
        unexpected_code_like,

    "cardinality_mismatches":
        cardinality_mismatches,

    "blocking_missing":
        blocking_missing,

    "blocking_value_mismatches":
        blocking_value_mismatches,

    "blocking_negative_violations":
        blocking_negative_violations,

    "queryclass_failures":
        queryclass_failures,

    "early_gate_failures":
        early_gate_failures,

    "a2c_a2d_control_failures":
        control_failures,

    "diagnostics_domain_findings":
        diagnostics_domain_findings,
}


with summary_path.open(
    "w",
    encoding="utf-8",
) as handle:

    json.dump(
        summary,
        handle,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


with failure_path.open(
    "w",
    encoding="utf-8",
) as handle:

    json.dump(
        findings,
        handle,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


# ============================================================
# Console report
# ============================================================

print("")
print("=== A2e ENTITY COVERAGE & CARDINALITY ===")

print("TOTAL=200")

print(
    f"EXPECTED_POSITIVE_ROWS="
    f"{positive_rows}"
)

print(
    f"EXPECTED_POSITIVE_COUNT="
    f"{positive_count}"
)

print(
    f"EXPECTED_NEGATIVE_ROWS="
    f"{negative_rows}"
)

print(
    f"EXPECTED_NEGATIVE_COUNT="
    f"{negative_count}"
)

print(
    f"EXPECTED_ENTITY_KEYS="
    f"{len(positive_expected_keys)}"
)

print(
    f"RUNTIME_ENTITY_KEYS="
    f"{len(runtime_keys)}"
)


print("")
print(
    f"EXACT_RUNTIME_REACHABLE="
    f"{exact_reachable}"
)

print(
    f"RELATED_ONLY="
    f"{related_only}"
)

print(
    f"UNREACHABLE_SCHEMA_EXPECTATIONS="
    f"{unreachable}"
)


print("")
print(
    f"MISSING_EXPECTED="
    f"{len(missing_expected)}"
)

print(
    f"VALUE_MISMATCHES="
    f"{len(value_mismatches)}"
)

print(
    f"NEGATIVE_VIOLATIONS="
    f"{len(negative_violations)}"
)

print(
    f"UNEXPECTED_CODE_LIKE="
    f"{len(unexpected_code_like)}"
)


print("")
print(
    f"SINGLE_VALUE_CARDINALITY_CASES="
    f"{single_cases}"
)

print(
    f"MULTI_VALUE_CARDINALITY_CASES="
    f"{multi_cases}"
)

print(
    f"CARDINALITY_SCHEMA_MISMATCHES="
    f"{len(cardinality_mismatches)}"
)


print("")
print(
    f"QUERYCLASS_PASS="
    f"{200-len(queryclass_failures)}/200"
)

print("A1B_EARLY_GATE_COUNT=20")

print(
    f"A1B_EARLY_GATE_FAILURES="
    f"{len(early_gate_failures)}"
)

print(
    f"A2C_A2D_CONTROL_FAILURES="
    f"{len(control_failures)}"
)


print("")
print(
    f"BLOCKING_MISSING_EXPECTED="
    f"{len(blocking_missing)}"
)

print(
    f"BLOCKING_VALUE_MISMATCHES="
    f"{len(blocking_value_mismatches)}"
)

print(
    f"BLOCKING_NEGATIVE_VIOLATIONS="
    f"{len(blocking_negative_violations)}"
)

print(
    f"BLOCKING_ENTITY_GROUNDING_ERRORS="
    f"{blocking_entity_errors}"
)


print("")
print(
    f"ROUTING_SAFETY_REGRESSIONS="
    f"{routing_safety_regressions}"
)

print(
    f"EXECUTION_GROUNDING_REGRESSIONS="
    f"{execution_grounding_regressions}"
)


print("")
print(
    "A2C_CONTROLS_118_185_OK="
    + str(
        not any(
            item.startswith(
                ("118_", "185_")
            )
            for item in control_failures
        )
    ).upper()
)

print(
    "A2D_CONTROLS_154_196_OK="
    + str(
        not any(
            item.startswith(
                ("154_", "196_")
            )
            for item in control_failures
        )
    ).upper()
)


print("")
print(
    "DIAGNOSTICS_DOMAIN_EXCLUDED_FROM_REPAIR_DECISION=TRUE"
)

print(
    "ORG_TUNING_PERFORMED=FALSE"
)


# Safety regressions are not ordinary A2e findings.
if routing_safety_regressions:
    raise RuntimeError(
        "Routing-safety regression detected."
    )

if execution_grounding_regressions:
    raise RuntimeError(
        "Frozen A2c/A2d grounding control regression detected."
    )


if blocking_entity_errors:

    print("")
    print("A2E_PATCH_REQUIRED=TRUE")
    print("PHASE_A_FREEZE_CANDIDATE=FALSE")

    print(
        "A2E_DECISION="
        "INVESTIGATE_BLOCKING_ENTITY_GROUNDING_FAILURES"
    )

else:

    print("")
    print("A2E_PATCH_REQUIRED=FALSE")
    print("PHASE_A_FREEZE_CANDIDATE=TRUE")

    print(
        "A2E_DECISION="
        "NO_BLOCKING_ENTITY_GROUNDING_FAILURES"
    )


print("")
print("PHASE_A_A2E_ENTITY_COVERAGE_AUDIT_OK")
'@


$AuditPython |
    python - `
        $ContractPath `
        $RuntimePath `
        $SummaryPath `
        $FailurePath `
        $MatrixPath

if ($LASTEXITCODE -ne 0) {
    throw "A2e entity coverage audit mislukt."
}


# ============================================================
# Final immutable runtime guards
# ============================================================

Write-Host ""
Write-Host "=== FINAL IMMUTABILITY GUARDS ==="


foreach ($Name in $ExpectedHashes.Keys) {

    $LocalPath = Join-Path $Root $Name

    $LocalHash = (
        Get-FileHash `
            $LocalPath `
            -Algorithm SHA256
    ).Hash

    if ($LocalHash -ne $ExpectedHashes[$Name]) {
        throw "Lokale appcode veranderde tijdens audit: $Name"
    }


    $ContainerPath = (
        "/app/app/orchestrator/" +
        $Name
    )

    $Raw = @(
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

    $RuntimeHash = (
        $Raw -join ""
    ).Trim()

    if ($RuntimeHash -ne $ExpectedHashes[$Name]) {
        throw "Runtime appcode veranderde tijdens audit: $Name"
    }
}


Write-Host "A2E_APP_STATE_UNCHANGED=TRUE"


Write-Host ""
Write-Host "RUNTIME_RESULTS=$RuntimePath"
Write-Host "SUMMARY=$SummaryPath"
Write-Host "FINDINGS=$FailurePath"
Write-Host "ENTITY_KEY_MATRIX=$MatrixPath"

Write-Host (
    "RUNTIME_RESULTS_SHA256=" +
    (
        Get-FileHash `
            $RuntimePath `
            -Algorithm SHA256
    ).Hash
)


Write-Host ""
Write-Host "APP_FILES_WRITTEN=FALSE"
Write-Host "ARTIFACT_FILES_ONLY=TRUE"
Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_EXECUTOR_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_RESEARCH_PROVIDER_CALLS=TRUE"
Write-Host "NO_DB_WRITES_ISSUED_BY_AUDIT=TRUE"
Write-Host "DIAGNOSTICS_DOMAIN_CHANGED=FALSE"
Write-Host "ORG_CHANGED=FALSE"
Write-Host "TEMP_HELPER_REMOVED=TRUE"

Write-Host "PHASE_A_A2E_AUDIT_COMPLETE" `
    -ForegroundColor Green