$ErrorActionPreference = "Stop"

$ApiRoot   = "C:\ai-platform\api"
$AppRoot   = Join-Path $ApiRoot "app"
$OrchRoot  = Join-Path $AppRoot "orchestrator"
$TestsRoot = Join-Path $ApiRoot "tests"

$ExecutorPath =
    Join-Path $OrchRoot "executor.py"

$TestPath =
    Join-Path $TestsRoot "test_phase_b3g_executor_shadow_local_only.py"

$B3B2FreezeDir =
    "C:\ai-platform\artifacts\phase_b\b3b2_types_registry_shadow_freeze_20260827_074025"

$B3EFreezeDir =
    "C:\ai-platform\artifacts\phase_b\b3e_transport_state_addendum_freeze_20260827_075623"

$B3FScript =
    "C:\ai-platform_temp\phase_b\audit_phase_b3f_local_only_shadow_patch_plan_v1.ps1"


$ExpectedB3FHash =
    "174A81360445B203A215E631B74BE217E3649B7764E7A474CA9EAC91A3D8F8ED"

$ExpectedExecutorPreHash =
    "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"

$ExpectedAcceptedSnippetHash =
    "81C7E7AA922EDD3EDF0CAA90029A3478BC7DB66B1CFF06486810D066E2425C29"

$ExpectedLegacyWrapperHash =
    "295CF18A9E2F56A7D2F44EA6AF6237BE0310C9E94380D28FA392F1FD1D76597E"


# ============================================================
# Frozen provenance
# ============================================================

$B3B2Hashes = [ordered]@{
    "freeze_manifest.json" =
        "0814F0A4B82C405C5BB370E91B77F540A0F028956F2535BC38EE9FC44C66B4D3"

    "freeze_summary.txt" =
        "B463F4C5445A7C706507607853E7FDD74ABA0D96F98E50CDCDA486420F114F55"

    "freeze_hashes.txt" =
        "1FF731366E4D421CB20FF4CB1F887AAF23B1FC28F7B5B0007FED884DB7471095"
}


$B3EHashes = [ordered]@{
    "design_phase_b3e_transport_state_addendum_v1.ps1" =
        "12BF99B55D003555EC41D8738855FA930A0462EFCE9114D328DE9902CD35DEBD"

    "b3e_transport_state_addendum_v1.json" =
        "10E1688D3CAAB617CCCC609EE3C0F43F0FB610DE187F0D061593E3B6FC04D9CA"

    "b3e_transport_state_addendum_summary.txt" =
        "C14B991A1C6E6B4BF0C94B2E958BE350C132A7299CF00D234361FC61130760F8"

    "freeze_manifest.json" =
        "3AD68ED0CAD3087A5714CF42A8E0D651212904CA1221A1B018DD844DDD50AE9B"

    "freeze_hashes.txt" =
        "50390517998747CF4380BF05CE0F86EE0D88A105AC86725DBE230281F5604325"
}


# ============================================================
# Files that B3G may NOT modify
# ============================================================

$ProtectedHashes = [ordered]@{
    "orchestrator\execution_contracts.py" =
        "FF66191BAF057371A8802130AC10D5744C2C3775DC2D51362EBD2658667D660E"

    "orchestrator\specialist_registry.py" =
        "9694B81932F41C1C5B28005D40A8A3586EBD94DFEA9B15D90A65D8086AEF9F8F"

    "orchestrator\execution_shadow.py" =
        "F5122A5DEAB1635DD48CEE352B2BF5216DADF87CCB5D05CC26C75FFD1A311B8A"

    "orchestrator\models.py" =
        "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E"

    "orchestrator\planner.py" =
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"

    "orchestrator\service.py" =
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"

    "orchestrator\research_agent.py" =
        "672F029DDF1AA655CC11EB42ACAB23933918B2835B8D81B724FB9AF18A98BC0D"

    "orchestrator\understanding.py" =
        "CF35835C9BD03D1267CED10EE47DCB67795A4DEA38336E4A1E8126049769BF78"

    "orchestrator\band_candidate_shadow.py" =
        "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484"

    "orchestrator\query_classification.py" =
        "193C690E4D62798566B57D84BD590DB04655357FD6DE86AE4F56EB5E16E35576"

    "orchestrator\normalizer.py" =
        "3AC3E4381FDB3501FF01E1D19BE317CBDCB03B214034409284E29A2D1303DDDB"

    "orchestrator\complexity.py" =
        "1A479E52DD552F92086D3A4D199FC54F9D0BAE77CC6B15924962570B9B425022"

    "routers\hybrid_api.py" =
        "2A5253EFCFC1EAA53DAD874F14D4AA71549E201A98D8BE8A384E7016FB0E657F"

    "routers\analysis_api_v10.py" =
        "6FAD131A4EE06375DCDBECE7018F426D08A2C761FE22C4BD8624A24B9085A6A1"
}


Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-B3G LOCAL-ONLY EXECUTOR SHADOW V1" -ForegroundColor Cyan
Write-Host " ONE EXISTING SOURCE PATCH + ONE NEW UNIT TEST" -ForegroundColor Cyan
Write-Host " NO REBUILD / NO API / NO DB" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan


# ============================================================
# B3F provenance
# ============================================================

Write-Host ""
Write-Host "=== B3F PROVENANCE GUARD ==="

if (-not (Test-Path -LiteralPath $B3FScript -PathType Leaf)) {
    throw "B3F audit script ontbreekt."
}

$B3FHash = (
    Get-FileHash `
        -LiteralPath $B3FScript `
        -Algorithm SHA256
).Hash

Write-Host "B3F_SCRIPT_SHA256=$B3FHash"

if ($B3FHash -ne $ExpectedB3FHash) {
    throw "B3F audit-script hash mismatch."
}

Write-Host "B3F_PROVENANCE_OK=TRUE"


# ============================================================
# Freeze guards
# ============================================================

Write-Host ""
Write-Host "=== B3B2 FREEZE GUARDS ==="

foreach ($Name in $B3B2Hashes.Keys) {

    $Path = Join-Path $B3B2FreezeDir $Name

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "B3B2 freeze artifact ontbreekt: $Name"
    }

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Hash"

    if ($Hash -ne $B3B2Hashes[$Name]) {
        throw "B3B2 freeze mismatch: $Name"
    }
}

Write-Host "B3B2_FREEZE_GUARDS_OK=TRUE"


Write-Host ""
Write-Host "=== B3E FREEZE GUARDS ==="

foreach ($Name in $B3EHashes.Keys) {

    $Path = Join-Path $B3EFreezeDir $Name

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "B3E freeze artifact ontbreekt: $Name"
    }

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Hash"

    if ($Hash -ne $B3EHashes[$Name]) {
        throw "B3E freeze mismatch: $Name"
    }
}

Write-Host "B3E_FREEZE_GUARDS_OK=TRUE"


# ============================================================
# Executor exact prehash
# ============================================================

Write-Host ""
Write-Host "=== EXECUTOR PREPATCH GUARD ==="

if (-not (Test-Path -LiteralPath $ExecutorPath -PathType Leaf)) {
    throw "executor.py ontbreekt."
}

$ExecutorPreHash = (
    Get-FileHash `
        -LiteralPath $ExecutorPath `
        -Algorithm SHA256
).Hash

Write-Host "EXECUTOR_PREPATCH_SHA256=$ExecutorPreHash"

if ($ExecutorPreHash -ne $ExpectedExecutorPreHash) {
    throw "executor.py prehash mismatch. Geen patch."
}

Write-Host "EXECUTOR_PREPATCH_GUARD_OK=TRUE"


# ============================================================
# New test MUST NOT already exist
# ============================================================

Write-Host ""
Write-Host "=== TEST TARGET COLLISION GUARD ==="

$TestExists = Test-Path -LiteralPath $TestPath

Write-Host "B3G_TEST_ALREADY_EXISTS=$($TestExists.ToString().ToUpper())"

if ($TestExists) {
    throw "B3G testbestand bestaat al. Geen overwrite toegestaan."
}

Write-Host "B3G_TEST_TARGET_ABSENT=TRUE"


# ============================================================
# Protected-source prestate
# ============================================================

$ProtectedBefore = [ordered]@{}

Write-Host ""
Write-Host "=== PROTECTED SOURCE GUARDS ==="

foreach ($RelativePath in $ProtectedHashes.Keys) {

    $Path = Join-Path $AppRoot $RelativePath

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Protected source ontbreekt: $RelativePath"
    }

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    $ProtectedBefore[$RelativePath] = $Hash

    Write-Host "$RelativePath=$Hash"

    if ($Hash -ne $ProtectedHashes[$RelativePath]) {
        throw "Protected source hash mismatch: $RelativePath"
    }
}

Write-Host "PROTECTED_SOURCE_GUARDS_OK=TRUE"


# ============================================================
# Timestamped staging + backup
# ============================================================

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$StageRoot =
    "C:\ai-platform_temp\phase_b\b3g_stage_$Stamp"

$BackupRoot =
    "C:\ai-platform_temp\phase_b\backup_b3g_$Stamp"

if (Test-Path -LiteralPath $StageRoot) {
    throw "B3G stage directory bestaat reeds."
}

if (Test-Path -LiteralPath $BackupRoot) {
    throw "B3G backup directory bestaat reeds."
}

New-Item `
    -ItemType Directory `
    -Path $StageRoot |
    Out-Null

New-Item `
    -ItemType Directory `
    -Path $BackupRoot |
    Out-Null


$StageExecutor =
    Join-Path $StageRoot "executor.py"

$StageTest =
    Join-Path $StageRoot "test_phase_b3g_executor_shadow_local_only.py"

$BackupExecutor =
    Join-Path $BackupRoot "executor.py"


Copy-Item `
    -LiteralPath $ExecutorPath `
    -Destination $BackupExecutor


$BackupHash = (
    Get-FileHash `
        -LiteralPath $BackupExecutor `
        -Algorithm SHA256
).Hash

if ($BackupHash -ne $ExpectedExecutorPreHash) {
    throw "Timestamped executor backup is niet byte-identiek."
}

Write-Host ""
Write-Host "BACKUP_DIR=$BackupRoot"
Write-Host "BACKUP_EXECUTOR_SHA256=$BackupHash"
Write-Host "EXECUTOR_BACKUP_PROVEN=TRUE"


# ============================================================
# Generate staged executor using AST structural positions
# ============================================================

$Generator = @'
import ast
import codecs
import hashlib
import pathlib
import sys
import textwrap


source_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])

expected_accepted_hash = sys.argv[3]
expected_wrapper_hash = sys.argv[4]


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return (
            f"{prefix}.{node.attr}"
            if prefix
            else node.attr
        )

    return None


def sha256_text(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest().upper()


def find_function(tree, name):
    hits = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == name
    ]

    if len(hits) != 1:
        raise RuntimeError(
            f"Expected one {name}; found {len(hits)}"
        )

    return hits[0]


def assigned_names(node):
    result = set()

    if isinstance(node, ast.Assign):
        targets = node.targets

    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]

    else:
        return result

    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                result.add(child.id)

    return result


def assignment_value(node):
    if isinstance(node, ast.Assign):
        return node.value

    if isinstance(node, ast.AnnAssign):
        return node.value

    return None


def static_dict_keys(node):
    if not isinstance(node, ast.Dict):
        return None

    result = []

    for key in node.keys:
        if not (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
        ):
            return None

        result.append(key.value)

    return result


def parent_maps(tree):
    parent = {}
    location = {}

    for owner in ast.walk(tree):
        for field, value in ast.iter_fields(owner):

            if isinstance(value, list):
                for index, child in enumerate(value):
                    if isinstance(child, ast.AST):
                        parent[id(child)] = owner
                        location[id(child)] = (
                            owner,
                            field,
                            index,
                        )

            elif isinstance(value, ast.AST):
                parent[id(value)] = owner

    return parent, location


def nearest_statement(node, parent):
    current = node

    while current is not None:
        if isinstance(current, ast.stmt):
            return current

        current = parent.get(
            id(current)
        )

    return None


def ancestors(node, parent):
    result = []
    current = parent.get(id(node))

    while current is not None:
        result.append(current)
        current = parent.get(id(current))

    return result


def source_segment(source, node):
    value = ast.get_source_segment(
        source,
        node,
    )

    if value is None:
        raise RuntimeError(
            "Source segment unavailable"
        )

    return value


raw = source_path.read_bytes()

has_bom = raw.startswith(
    codecs.BOM_UTF8
)

source = raw.decode(
    "utf-8-sig"
)

newline = (
    "\r\n"
    if b"\r\n" in raw
    else "\n"
)

tree = ast.parse(
    source,
    filename=str(source_path),
)

compile(
    source,
    str(source_path),
    "exec",
)

execute_plan = find_function(
    tree,
    "execute_plan",
)

parent, locations = parent_maps(
    tree
)


# ------------------------------------------------------------
# Exact accepted assignment
# ------------------------------------------------------------

accepted_hits = []

for node in ast.walk(
    execute_plan
):

    if not isinstance(
        node,
        (
            ast.Assign,
            ast.AnnAssign,
        ),
    ):
        continue

    if "accepted" not in assigned_names(node):
        continue

    value = assignment_value(node)

    if (
        isinstance(value, ast.Call)
        and dotted(value.func)
            == "_is_accepted"
    ):
        accepted_hits.append(
            node
        )


if len(accepted_hits) != 1:
    raise RuntimeError(
        "accepted assignment is not unique"
    )

accepted_node = accepted_hits[0]

accepted_source = source_segment(
    source,
    accepted_node,
)

if sha256_text(
    accepted_source
) != expected_accepted_hash:
    raise RuntimeError(
        "accepted snippet hash mismatch"
    )


# ------------------------------------------------------------
# Exact legacy wrapper + append statement
# ------------------------------------------------------------

required_wrapper_keys = {
    "step_id",
    "domain",
    "action",
    "endpoint",
    "accepted",
    "result",
}

wrapper_hits = []

for node in ast.walk(
    execute_plan
):

    if not isinstance(node, ast.Dict):
        continue

    keys = static_dict_keys(node)

    if (
        keys is not None
        and set(keys)
            == required_wrapper_keys
    ):
        wrapper_hits.append(
            node
        )


if len(wrapper_hits) != 1:
    raise RuntimeError(
        "legacy wrapper is not unique"
    )

wrapper_dict = wrapper_hits[0]

wrapper_source = source_segment(
    source,
    wrapper_dict,
)

if sha256_text(
    wrapper_source
) != expected_wrapper_hash:
    raise RuntimeError(
        "legacy wrapper hash mismatch"
    )


wrapper_append = None

for ancestor in ancestors(
    wrapper_dict,
    parent,
):

    if not isinstance(
        ancestor,
        ast.Call,
    ):
        continue

    if not isinstance(
        ancestor.func,
        ast.Attribute,
    ):
        continue

    if ancestor.func.attr != "append":
        continue

    if any(
        arg is wrapper_dict
        for arg in ancestor.args
    ):
        wrapper_append = ancestor
        break


if wrapper_append is None:
    raise RuntimeError(
        "wrapper append call not found"
    )


wrapper_statement = nearest_statement(
    wrapper_append,
    parent,
)

accepted_statement = nearest_statement(
    accepted_node,
    parent,
)

accepted_loc = locations.get(
    id(accepted_statement)
)

wrapper_loc = locations.get(
    id(wrapper_statement)
)

if (
    accepted_loc is None
    or wrapper_loc is None
):
    raise RuntimeError(
        "statement locations unavailable"
    )


accepted_owner, accepted_field, accepted_index = (
    accepted_loc
)

wrapper_owner, wrapper_field, wrapper_index = (
    wrapper_loc
)


if not (
    accepted_owner is wrapper_owner
    and accepted_field == wrapper_field
):
    raise RuntimeError(
        "accepted/wrapper no longer share AST block"
    )


body = getattr(
    accepted_owner,
    accepted_field,
)

between = body[
    accepted_index + 1:
    wrapper_index
]

if len(between) != 2:
    raise RuntimeError(
        "Expected exactly result_count + trace append"
    )

if not ast.unparse(
    between[0]
).startswith(
    "result_count = _infer_result_count"
):
    raise RuntimeError(
        "First intermediate statement changed"
    )

if "trace.attempts.append" not in ast.unparse(
    between[1]
):
    raise RuntimeError(
        "Second intermediate statement changed"
    )


# ------------------------------------------------------------
# Import insertion point
# ------------------------------------------------------------

top_imports = [
    node
    for node in tree.body
    if isinstance(
        node,
        (
            ast.Import,
            ast.ImportFrom,
        ),
    )
]

if not top_imports:
    raise RuntimeError(
        "No executor imports found"
    )


existing_modules = set()

for node in top_imports:

    if isinstance(node, ast.Import):
        for alias in node.names:
            existing_modules.add(
                alias.name
            )

    elif (
        isinstance(node, ast.ImportFrom)
        and node.module
    ):
        existing_modules.add(
            node.module
        )


for forbidden in (
    "app.orchestrator.execution_contracts",
    "app.orchestrator.execution_shadow",
):
    if forbidden in existing_modules:
        raise RuntimeError(
            "B3G imports already present"
        )


last_import = max(
    top_imports,
    key=lambda node:
        getattr(
            node,
            "end_lineno",
            node.lineno,
        ),
)


# ------------------------------------------------------------
# Candidate text
# ------------------------------------------------------------

candidate_import_block = """\
from app.orchestrator.execution_contracts import (
    EXECUTION_CONTRACT_VERSION,
    ExecutionRequest,
    ExecutionTransportState,
    FallbackPolicy,
)
from app.orchestrator.execution_shadow import derive_execution_result
"""

raw_shadow_block = """\
try:
    _shadow_request = ExecutionRequest(
        contract_version=EXECUTION_CONTRACT_VERSION,
        step_id=step.step_id,
        domain=step.domain.value,
        action=step.action,
        endpoint=endpoint,
        params=dict(step.params),
        required=step.required,
        timeout_seconds=30.0,
        retry_count=0,
        fallback_policy=FallbackPolicy.UNRESOLVED,
        legacy_fallback_allowed=step.fallback_allowed,
    )

    _shadow_execution_result = derive_execution_result(
        request=_shadow_request,
        raw_result=result,
        legacy_accepted=accepted,
        transport_state=ExecutionTransportState.COMPLETED,
        duration_ms=duration_ms,
    )
except Exception:
    _shadow_execution_result = None
"""


candidate_import_block = (
    candidate_import_block
    .replace(
        "\n",
        newline,
    )
)

raw_shadow_block = (
    raw_shadow_block
    .replace(
        "\n",
        newline,
    )
)


source_lines = source.splitlines(
    keepends=True
)


wrapper_line_text = source_lines[
    wrapper_statement.lineno - 1
]

indent_length = (
    len(wrapper_line_text)
    - len(
        wrapper_line_text.lstrip(" ")
    )
)

indent = " " * indent_length


shadow_block = textwrap.indent(
    raw_shadow_block,
    indent,
)


# Lower insertion first.
candidate_lines = list(
    source_lines
)

candidate_lines.insert(
    wrapper_statement.lineno - 1,
    shadow_block,
)


import_insert_index = getattr(
    last_import,
    "end_lineno",
    last_import.lineno,
)

candidate_lines.insert(
    import_insert_index,
    candidate_import_block,
)


candidate_source = "".join(
    candidate_lines
)


candidate_tree = ast.parse(
    candidate_source,
    filename="<b3g-staged-executor>",
)

compile(
    candidate_source,
    "<b3g-staged-executor>",
    "exec",
)


# ------------------------------------------------------------
# Postcandidate structural checks
# ------------------------------------------------------------

candidate_execute = find_function(
    candidate_tree,
    "execute_plan",
)


candidate_accepted_hits = []

for node in ast.walk(
    candidate_execute
):

    if not isinstance(
        node,
        (
            ast.Assign,
            ast.AnnAssign,
        ),
    ):
        continue

    if "accepted" not in assigned_names(node):
        continue

    value = assignment_value(node)

    if (
        isinstance(value, ast.Call)
        and dotted(value.func)
            == "_is_accepted"
    ):
        candidate_accepted_hits.append(
            node
        )


if len(candidate_accepted_hits) != 1:
    raise RuntimeError(
        "candidate accepted assignment count changed"
    )


candidate_accepted_source = source_segment(
    candidate_source,
    candidate_accepted_hits[0],
)

if sha256_text(
    candidate_accepted_source
) != expected_accepted_hash:
    raise RuntimeError(
        "candidate altered accepted assignment"
    )


candidate_wrapper_hits = []

for node in ast.walk(
    candidate_execute
):

    if not isinstance(node, ast.Dict):
        continue

    keys = static_dict_keys(node)

    if (
        keys is not None
        and set(keys)
            == required_wrapper_keys
    ):
        candidate_wrapper_hits.append(
            node
        )


if len(candidate_wrapper_hits) != 1:
    raise RuntimeError(
        "candidate legacy wrapper count changed"
    )


candidate_wrapper_source = source_segment(
    candidate_source,
    candidate_wrapper_hits[0],
)

if sha256_text(
    candidate_wrapper_source
) != expected_wrapper_hash:
    raise RuntimeError(
        "candidate altered legacy wrapper"
    )


request_calls = [
    node
    for node in ast.walk(
        candidate_execute
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "ExecutionRequest"
]

derive_calls = [
    node
    for node in ast.walk(
        candidate_execute
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "derive_execution_result"
]

if len(request_calls) != 1:
    raise RuntimeError(
        "Expected exactly one ExecutionRequest call"
    )

if len(derive_calls) != 1:
    raise RuntimeError(
        "Expected exactly one derive_execution_result call"
    )


derive_kwargs = {
    keyword.arg:
        ast.unparse(keyword.value)
    for keyword in derive_calls[0].keywords
    if keyword.arg is not None
}


if derive_kwargs.get(
    "transport_state"
) != "ExecutionTransportState.COMPLETED":
    raise RuntimeError(
        "transport_state is not explicitly COMPLETED"
    )

if derive_kwargs.get(
    "duration_ms"
) != "duration_ms":
    raise RuntimeError(
        "duration_ms is not passed explicitly"
    )


common_try = None

for node in ast.walk(
    candidate_execute
):

    if not isinstance(node, ast.Try):
        continue

    has_request = any(
        child is request_calls[0]
        for child in ast.walk(node)
    )

    has_derive = any(
        child is derive_calls[0]
        for child in ast.walk(node)
    )

    if has_request and has_derive:
        common_try = node
        break


if common_try is None:
    raise RuntimeError(
        "ExecutionRequest + derive call not in common try"
    )

if len(common_try.handlers) != 1:
    raise RuntimeError(
        "Shadow try handler count mismatch"
    )


handler = common_try.handlers[0]

if ast.unparse(
    handler.type
) != "Exception":
    raise RuntimeError(
        "Shadow handler is not Exception"
    )

if any(
    isinstance(node, ast.Raise)
    for node in ast.walk(handler)
):
    raise RuntimeError(
        "Shadow handler re-raises"
    )


# ------------------------------------------------------------
# Write staged bytes only
# ------------------------------------------------------------

encoded = candidate_source.encode(
    "utf-8"
)

if has_bom:
    encoded = (
        codecs.BOM_UTF8
        + encoded
    )


output_path.write_bytes(
    encoded
)


print(
    "STAGED_EXECUTOR_AST_COMPILE_OK=TRUE"
)

print(
    "STAGED_ACCEPTED_ASSIGNMENT_PRESERVED=TRUE"
)

print(
    "STAGED_LEGACY_WRAPPER_PRESERVED=TRUE"
)

print(
    "STAGED_SHADOW_CALL_COUNT=1"
)

print(
    "STAGED_TRANSPORT_STATE_EXPLICIT_COMPLETED=TRUE"
)

print(
    "STAGED_DURATION_MS_EXPLICIT=TRUE"
)

print(
    "STAGED_FAIL_OPEN_BOUNDARY_PROVEN=TRUE"
)

print(
    "STAGED_EXECUTOR_WRITTEN="
    + str(output_path)
)
'@


$GeneratorOutput = @(
    $Generator |
        & python -B - `
            $ExecutorPath `
            $StageExecutor `
            $ExpectedAcceptedSnippetHash `
            $ExpectedLegacyWrapperHash
)

$GeneratorExit = $LASTEXITCODE

$GeneratorOutput |
    ForEach-Object {
        Write-Host $_
    }

if ($GeneratorExit -ne 0) {
    throw "B3G staged executor generation mislukt."
}


# ============================================================
# Generate self-contained no-network B3G unit test
# ============================================================

$TestSource = @'
import ast
import pathlib
import time
import unittest
from types import SimpleNamespace


API_ROOT = pathlib.Path(__file__).resolve().parents[1]

EXECUTOR_PATH = (
    API_ROOT
    / "app"
    / "orchestrator"
    / "executor.py"
)


def _load_executor_core(
    *,
    derive_raises=False,
    request_raises=False,
):
    source = EXECUTOR_PATH.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source,
        filename=str(EXECUTOR_PATH),
    )

    wanted = {
        "_infer_result_count",
        "_is_accepted",
        "execute_plan",
    }

    body = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name in wanted
    ]

    names = {
        node.name
        for node in body
    }

    if names != wanted:
        raise AssertionError(
            f"executor core functions mismatch: {names}"
        )

    module = ast.Module(
        body=body,
        type_ignores=[],
    )

    module = ast.fix_missing_locations(
        module
    )

    derive_calls = []
    request_calls = []


    class DummyTrace:
        def __init__(self, *args, **kwargs):
            self.attempts = []

            for key, value in kwargs.items():
                setattr(
                    self,
                    key,
                    value,
                )

        def __getattr__(self, name):
            return None


    class DummyTraceAttempt:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(
                    self,
                    key,
                    value,
                )


    class DummyExecutionRequest:
        def __init__(self, **kwargs):
            request_calls.append(
                dict(kwargs)
            )

            if request_raises:
                raise RuntimeError(
                    "intentional request shadow failure"
                )

            for key, value in kwargs.items():
                setattr(
                    self,
                    key,
                    value,
                )


    class DummyExecutionTransportState:
        COMPLETED = "COMPLETED"


    class DummyFallbackPolicy:
        UNRESOLVED = "UNRESOLVED"


    def derive_execution_result(**kwargs):
        derive_calls.append(
            dict(kwargs)
        )

        if derive_raises:
            raise RuntimeError(
                "intentional derivation shadow failure"
            )

        return SimpleNamespace(
            semantic_outcome="shadow-only"
        )


    namespace = {
        "Any": object,
        "Callable": object,
        "QueryPlan": object,
        "OrchestratorTrace": DummyTrace,
        "TraceAttempt": DummyTraceAttempt,
        "ACTION_ENDPOINTS": {
            "analysis_assistant":
                "/analysis/assistant/ask",
        },
        "ExecutionRequest":
            DummyExecutionRequest,
        "EXECUTION_CONTRACT_VERSION":
            "promati.phase_b2e.execution_contract.v1",
        "ExecutionTransportState":
            DummyExecutionTransportState,
        "FallbackPolicy":
            DummyFallbackPolicy,
        "derive_execution_result":
            derive_execution_result,
        "time":
            time,
    }

    code = compile(
        module,
        str(EXECUTOR_PATH),
        "exec",
    )

    exec(
        code,
        namespace,
    )

    return (
        namespace["execute_plan"],
        request_calls,
        derive_calls,
    )


def _step():
    return SimpleNamespace(
        step_id="step_shadow_test",
        domain=SimpleNamespace(value="inspection"),
        action="analysis_assistant",
        params={
            "vraag": "testvraag",
        },
        required=True,
        fallback_allowed=True,
    )


def _plan():
    return SimpleNamespace(
        clarification_required=False,
        execution_steps=[
            _step()
        ],
    )


def _run(
    result,
    *,
    derive_raises=False,
    request_raises=False,
):
    (
        execute_plan,
        request_calls,
        derive_calls,
    ) = _load_executor_core(
        derive_raises=derive_raises,
        request_raises=request_raises,
    )

    sender_calls = []


    def sender(path, payload):
        sender_calls.append(
            (
                path,
                dict(payload),
            )
        )

        return dict(result)


    results, trace = execute_plan(
        _plan(),
        sender=sender,
    )

    return {
        "results": results,
        "trace": trace,
        "sender_calls": sender_calls,
        "request_calls": request_calls,
        "derive_calls": derive_calls,
    }


class ExecutorLocalOnlyShadowV1Tests(
    unittest.TestCase
):
    def test_shadow_deriver_called_once_with_custom_sender(self):
        run = _run(
            {
                "status": "ok",
                "value": 123,
            }
        )

        self.assertEqual(
            len(run["sender_calls"]),
            1,
        )

        self.assertEqual(
            len(run["request_calls"]),
            1,
        )

        self.assertEqual(
            len(run["derive_calls"]),
            1,
        )

        wrapper = run["results"][0]

        self.assertEqual(
            set(wrapper),
            {
                "step_id",
                "domain",
                "action",
                "endpoint",
                "accepted",
                "result",
            },
        )

        self.assertTrue(
            wrapper["accepted"]
        )

        derive = run["derive_calls"][0]

        self.assertEqual(
            derive["raw_result"],
            {
                "status": "ok",
                "value": 123,
            },
        )

        self.assertTrue(
            derive["legacy_accepted"]
        )

        self.assertEqual(
            derive["transport_state"],
            "COMPLETED",
        )

        self.assertIsInstance(
            derive["duration_ms"],
            int,
        )

        request = run["request_calls"][0]

        self.assertEqual(
            request["step_id"],
            "step_shadow_test",
        )

        self.assertEqual(
            request["action"],
            "analysis_assistant",
        )

        self.assertEqual(
            request["domain"],
            "inspection",
        )

        self.assertEqual(
            request["timeout_seconds"],
            30.0,
        )

        self.assertEqual(
            request["retry_count"],
            0,
        )

        self.assertEqual(
            request["fallback_policy"],
            "UNRESOLVED",
        )

        self.assertTrue(
            request["legacy_fallback_allowed"]
        )


    def test_deriver_exception_is_fail_open(self):
        run = _run(
            {
                "status": "ok",
                "value": 1,
            },
            derive_raises=True,
        )

        self.assertEqual(
            len(run["derive_calls"]),
            1,
        )

        self.assertEqual(
            len(run["results"]),
            1,
        )

        self.assertTrue(
            run["results"][0]["accepted"]
        )

        self.assertEqual(
            set(run["results"][0]),
            {
                "step_id",
                "domain",
                "action",
                "endpoint",
                "accepted",
                "result",
            },
        )


    def test_request_constructor_exception_is_fail_open(self):
        run = _run(
            {
                "status": "ok",
            },
            request_raises=True,
        )

        self.assertEqual(
            len(run["request_calls"]),
            1,
        )

        self.assertEqual(
            len(run["derive_calls"]),
            0,
        )

        self.assertEqual(
            len(run["results"]),
            1,
        )

        self.assertTrue(
            run["results"][0]["accepted"]
        )


    def test_semantic_non_success_keeps_legacy_acceptance(self):
        run = _run(
            {
                "status":
                    "clarification_required",
            }
        )

        wrapper = run["results"][0]

        # Existing legacy rule rejects only
        # error / failed / failure.
        self.assertTrue(
            wrapper["accepted"]
        )

        self.assertEqual(
            run["derive_calls"][0][
                "raw_result"
            ][
                "status"
            ],
            "clarification_required",
        )

        self.assertTrue(
            run["derive_calls"][0][
                "legacy_accepted"
            ]
        )


    def test_transport_error_dict_is_completed_but_legacy_rejected(self):
        run = _run(
            {
                "status": "error",
                "context_type":
                    "orchestrator_transport",
                "error":
                    "simulated transport failure",
            }
        )

        wrapper = run["results"][0]

        self.assertFalse(
            wrapper["accepted"]
        )

        derive = run["derive_calls"][0]

        self.assertFalse(
            derive["legacy_accepted"]
        )

        self.assertEqual(
            derive["transport_state"],
            "COMPLETED",
        )


    def test_custom_sender_path_requires_no_default_sender_or_network(self):
        run = _run(
            {
                "status": "ok",
            }
        )

        self.assertEqual(
            run["sender_calls"],
            [
                (
                    "/analysis/assistant/ask",
                    {
                        "vraag":
                            "testvraag",
                    },
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
'@


$Utf8NoBom =
    New-Object System.Text.UTF8Encoding($false)

[System.IO.File]::WriteAllText(
    $StageTest,
    $TestSource,
    $Utf8NoBom
)


# ============================================================
# Staged Python validation
# ============================================================

$StageValidator = @'
import ast
import pathlib
import sys


for value in sys.argv[1:]:
    path = pathlib.Path(value)

    source = path.read_text(
        encoding="utf-8-sig"
    )

    ast.parse(
        source,
        filename=str(path),
    )

    compile(
        source,
        str(path),
        "exec",
    )

    print(
        "STAGED_AST_COMPILE_OK="
        + path.name
    )
'@


$StageValidation = @(
    $StageValidator |
        & python -B - `
            $StageExecutor `
            $StageTest
)

$StageValidationExit =
    $LASTEXITCODE

$StageValidation |
    ForEach-Object {
        Write-Host $_
    }

if ($StageValidationExit -ne 0) {
    throw "B3G staged syntax validation mislukt."
}

Write-Host "B3G_STAGED_FILES_VALID=TRUE"


$StagedExecutorHash = (
    Get-FileHash `
        -LiteralPath $StageExecutor `
        -Algorithm SHA256
).Hash

$StagedTestHash = (
    Get-FileHash `
        -LiteralPath $StageTest `
        -Algorithm SHA256
).Hash


Write-Host ""
Write-Host "STAGED_EXECUTOR_SHA256=$StagedExecutorHash"
Write-Host "STAGED_TEST_SHA256=$StagedTestHash"


if ($StagedExecutorHash -eq $ExpectedExecutorPreHash) {
    throw "Staged executor is onverwacht identiek aan prepatch executor."
}


# ============================================================
# Last pre-promotion guards
# ============================================================

$CurrentExecutorHash = (
    Get-FileHash `
        -LiteralPath $ExecutorPath `
        -Algorithm SHA256
).Hash

if ($CurrentExecutorHash -ne $ExpectedExecutorPreHash) {
    throw "executor.py veranderde tijdens staging."
}

if (Test-Path -LiteralPath $TestPath) {
    throw "B3G test target verscheen tijdens staging."
}


foreach ($RelativePath in $ProtectedHashes.Keys) {

    $Path = Join-Path $AppRoot $RelativePath

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    if ($Hash -ne $ProtectedBefore[$RelativePath]) {
        throw "Protected source veranderde vóór promotion: $RelativePath"
    }
}

Write-Host "PRE_PROMOTION_GUARDS_OK=TRUE"


# ============================================================
# Promote with rollback capability
# ============================================================

$ExecutorPromoted = $false
$TestPromoted = $false

try {

    Write-Host ""
    Write-Host "=== B3G PROMOTION ==="


    # Same-directory temporary file enables File.Replace().
    $ExecutorSwapPath =
        Join-Path `
            $OrchRoot `
            "executor.py.b3g_$Stamp.swap"


    if (Test-Path -LiteralPath $ExecutorSwapPath) {
        throw "Executor swap file bestaat reeds."
    }


    Copy-Item `
        -LiteralPath $StageExecutor `
        -Destination $ExecutorSwapPath


    $ReplaceBackupPath =
        Join-Path `
            $OrchRoot `
            "executor.py.b3g_replace_backup_$Stamp.bak"

    if (Test-Path -LiteralPath $ReplaceBackupPath) {
        throw "B3G replace backup path bestaat reeds."
    }

    [System.IO.File]::Replace(
        $ExecutorSwapPath,
        $ExecutorPath,
        $ReplaceBackupPath
    )

    $ReplaceBackupHash = (
        Get-FileHash `
            -LiteralPath $ReplaceBackupPath `
            -Algorithm SHA256
    ).Hash

    if ($ReplaceBackupHash -ne $ExpectedExecutorPreHash) {
        throw "File.Replace backup is niet de originele executor."
    }

    Write-Host "FILE_REPLACE_BACKUP_SHA256=$ReplaceBackupHash"
    Write-Host "FILE_REPLACE_BACKUP_PROVEN=TRUE"

    $ExecutorPromoted = $true

    Write-Host "EXECUTOR_ATOMIC_REPLACE_COMPLETE=TRUE"


    [System.IO.File]::Move(
        $StageTest,
        $TestPath
    )

    $TestPromoted = $true

    Write-Host "B3G_TEST_PROMOTION_COMPLETE=TRUE"


    # ========================================================
    # Promoted hashes must equal staged hashes
    # ========================================================

    $ExecutorPostHash = (
        Get-FileHash `
            -LiteralPath $ExecutorPath `
            -Algorithm SHA256
    ).Hash

    $TestPostHash = (
        Get-FileHash `
            -LiteralPath $TestPath `
            -Algorithm SHA256
    ).Hash


    if ($ExecutorPostHash -ne $StagedExecutorHash) {
        throw "Promoted executor hash differs from staged candidate."
    }

    if ($TestPostHash -ne $StagedTestHash) {
        throw "Promoted test hash differs from staged test."
    }


    Write-Host "PROMOTED_EXECUTOR_MATCHES_STAGE=TRUE"
    Write-Host "PROMOTED_TEST_MATCHES_STAGE=TRUE"


    # ========================================================
    # Postpromotion static structural audit
    # ========================================================

    $PostAudit = @'
import ast
import hashlib
import pathlib
import sys


executor_path = pathlib.Path(sys.argv[1])

expected_accepted = sys.argv[2]
expected_wrapper = sys.argv[3]


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return (
            f"{prefix}.{node.attr}"
            if prefix
            else node.attr
        )

    return None


def sha256_text(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest().upper()


source = executor_path.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(
    source,
    filename=str(executor_path),
)

compile(
    source,
    str(executor_path),
    "exec",
)


execute_hits = [
    node
    for node in ast.walk(tree)
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
    and node.name == "execute_plan"
]

if len(execute_hits) != 1:
    raise RuntimeError(
        "execute_plan count mismatch"
    )

execute_plan = execute_hits[0]


accepted = []

for node in ast.walk(
    execute_plan
):

    if not isinstance(
        node,
        (
            ast.Assign,
            ast.AnnAssign,
        ),
    ):
        continue

    targets = (
        node.targets
        if isinstance(node, ast.Assign)
        else [node.target]
    )

    if not any(
        isinstance(target, ast.Name)
        and target.id == "accepted"
        for target in targets
    ):
        continue

    value = node.value

    if (
        isinstance(value, ast.Call)
        and dotted(value.func)
            == "_is_accepted"
    ):
        accepted.append(
            node
        )


if len(accepted) != 1:
    raise RuntimeError(
        "accepted assignment count mismatch"
    )


accepted_source = ast.get_source_segment(
    source,
    accepted[0],
)

if sha256_text(
    accepted_source
) != expected_accepted:
    raise RuntimeError(
        "accepted assignment changed"
    )


required_keys = {
    "step_id",
    "domain",
    "action",
    "endpoint",
    "accepted",
    "result",
}

wrappers = []

for node in ast.walk(
    execute_plan
):

    if not isinstance(node, ast.Dict):
        continue

    keys = []

    valid = True

    for key in node.keys:

        if not (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
        ):
            valid = False
            break

        keys.append(
            key.value
        )

    if (
        valid
        and set(keys) == required_keys
    ):
        wrappers.append(
            node
        )


if len(wrappers) != 1:
    raise RuntimeError(
        "legacy wrapper count mismatch"
    )


wrapper_source = ast.get_source_segment(
    source,
    wrappers[0],
)

if sha256_text(
    wrapper_source
) != expected_wrapper:
    raise RuntimeError(
        "legacy wrapper changed"
    )


derive_calls = [
    node
    for node in ast.walk(
        execute_plan
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "derive_execution_result"
]

request_calls = [
    node
    for node in ast.walk(
        execute_plan
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "ExecutionRequest"
]


if len(derive_calls) != 1:
    raise RuntimeError(
        "derive call count mismatch"
    )

if len(request_calls) != 1:
    raise RuntimeError(
        "ExecutionRequest call count mismatch"
    )


derive_kwargs = {
    keyword.arg:
        ast.unparse(keyword.value)
    for keyword in derive_calls[0].keywords
    if keyword.arg is not None
}


if derive_kwargs.get(
    "transport_state"
) != "ExecutionTransportState.COMPLETED":
    raise RuntimeError(
        "explicit COMPLETED state missing"
    )

if derive_kwargs.get(
    "duration_ms"
) != "duration_ms":
    raise RuntimeError(
        "duration_ms mapping missing"
    )


imports = {
    node.module
    for node in tree.body
    if isinstance(node, ast.ImportFrom)
    and node.module
}


if (
    "app.orchestrator.execution_contracts"
    not in imports
):
    raise RuntimeError(
        "execution_contracts import missing"
    )

if (
    "app.orchestrator.execution_shadow"
    not in imports
):
    raise RuntimeError(
        "execution_shadow import missing"
    )


print(
    "POSTPATCH_EXECUTOR_AST_COMPILE_OK=TRUE"
)

print(
    "POSTPATCH_ACCEPTED_ASSIGNMENT_PRESERVED=TRUE"
)

print(
    "POSTPATCH_LEGACY_WRAPPER_PRESERVED=TRUE"
)

print(
    "POSTPATCH_SHADOW_CALL_COUNT=1"
)

print(
    "POSTPATCH_EXPLICIT_COMPLETED_STATE=TRUE"
)

print(
    "POSTPATCH_EXPLICIT_DURATION_MS=TRUE"
)
'@


    $PostAuditOutput = @(
        $PostAudit |
            & python -B - `
                $ExecutorPath `
                $ExpectedAcceptedSnippetHash `
                $ExpectedLegacyWrapperHash
    )

    $PostAuditExit =
        $LASTEXITCODE

    $PostAuditOutput |
        ForEach-Object {
            Write-Host $_
        }

    if ($PostAuditExit -ne 0) {
        throw "Postpatch executor structure audit mislukt."
    }


    # ========================================================
    # Targeted tests only
    # ========================================================

    Write-Host ""
    Write-Host "=== B3G TARGETED TESTS ==="


    $OldPythonPath =
        $env:PYTHONPATH

    $OldNoByteCode =
        $env:PYTHONDONTWRITEBYTECODE


    try {

        $env:PYTHONPATH =
            $ApiRoot

        $env:PYTHONDONTWRITEBYTECODE =
            "1"


        Write-Host ""
        Write-Host "--- B3B1 regression tests ---"

        & python -B -m unittest discover `
            -s $TestsRoot `
            -p "test_phase_b3b1_*.py" `
            -v

        $B3B1Exit =
            $LASTEXITCODE

        if ($B3B1Exit -ne 0) {
            throw "B3B1 regression tests failed."
        }


        Write-Host ""
        Write-Host "--- B3G executor-shadow tests ---"

        & python -B -m unittest discover `
            -s $TestsRoot `
            -p "test_phase_b3g_executor_shadow_local_only.py" `
            -v

        $B3GTestExit =
            $LASTEXITCODE

        if ($B3GTestExit -ne 0) {
            throw "B3G executor-shadow tests failed."
        }
    }
    finally {

        $env:PYTHONPATH =
            $OldPythonPath

        $env:PYTHONDONTWRITEBYTECODE =
            $OldNoByteCode
    }


    Write-Host "B3B1_REGRESSION_TESTS_GREEN=TRUE"
    Write-Host "B3G_TARGETED_TESTS_GREEN=TRUE"


    # ========================================================
    # Final protected immutability
    # ========================================================

    Write-Host ""
    Write-Host "=== PROTECTED SOURCE IMMUTABILITY ==="

    foreach ($RelativePath in $ProtectedHashes.Keys) {

        $Path = Join-Path $AppRoot $RelativePath

        $After = (
            Get-FileHash `
                -LiteralPath $Path `
                -Algorithm SHA256
        ).Hash

        if ($After -ne $ProtectedBefore[$RelativePath]) {
            throw "Protected source changed during B3G: $RelativePath"
        }
    }

    Write-Host "PROTECTED_SOURCE_CHANGED=FALSE"


    # ========================================================
    # Freeze immutability
    # ========================================================

    foreach ($Name in $B3B2Hashes.Keys) {

        $Path = Join-Path $B3B2FreezeDir $Name

        $Hash = (
            Get-FileHash `
                -LiteralPath $Path `
                -Algorithm SHA256
        ).Hash

        if ($Hash -ne $B3B2Hashes[$Name]) {
            throw "B3B2 freeze changed during B3G: $Name"
        }
    }


    foreach ($Name in $B3EHashes.Keys) {

        $Path = Join-Path $B3EFreezeDir $Name

        $Hash = (
            Get-FileHash `
                -LiteralPath $Path `
                -Algorithm SHA256
        ).Hash

        if ($Hash -ne $B3EHashes[$Name]) {
            throw "B3E freeze changed during B3G: $Name"
        }
    }


    $FinalB3FHash = (
        Get-FileHash `
            -LiteralPath $B3FScript `
            -Algorithm SHA256
    ).Hash

    if ($FinalB3FHash -ne $ExpectedB3FHash) {
        throw "B3F script changed during B3G."
    }


    Write-Host "B3B2_FREEZE_ARTIFACTS_CHANGED=FALSE"
    Write-Host "B3E_FREEZE_ARTIFACTS_CHANGED=FALSE"
}
catch {

    Write-Host ""
    Write-Host "=== B3G ROLLBACK ===" -ForegroundColor Yellow
    Write-Host "ROLLBACK_REASON=$($_.Exception.Message)"


    if ($ExecutorPromoted) {

        $RestoreSwap =
            Join-Path `
                $OrchRoot `
                "executor.py.b3g_restore_$Stamp.swap"


        if (Test-Path -LiteralPath $RestoreSwap) {
            Remove-Item `
                -LiteralPath $RestoreSwap `
                -Force
        }


        Copy-Item `
            -LiteralPath $BackupExecutor `
            -Destination $RestoreSwap


        $RollbackDisplacedPath =
            Join-Path `
                $OrchRoot `
                "executor.py.b3g_failed_candidate_$Stamp.bak"

        if (Test-Path -LiteralPath $RollbackDisplacedPath) {
            Remove-Item `
                -LiteralPath $RollbackDisplacedPath `
                -Force
        }

        [System.IO.File]::Replace(
            $RestoreSwap,
            $ExecutorPath,
            $RollbackDisplacedPath
        )

        if (Test-Path -LiteralPath $RollbackDisplacedPath -PathType Leaf) {

            $RollbackDisplacedHash = (
                Get-FileHash `
                    -LiteralPath $RollbackDisplacedPath `
                    -Algorithm SHA256
            ).Hash

            Write-Host "ROLLBACK_DISPLACED_SHA256=$RollbackDisplacedHash"

            if ($RollbackDisplacedHash -eq $StagedExecutorHash) {

                Remove-Item `
                    -LiteralPath $RollbackDisplacedPath `
                    -Force

                Write-Host "ROLLBACK_DISPLACED_CANDIDATE_REMOVED=TRUE"
            }
            else {

                Write-Host "ROLLBACK_DISPLACED_CANDIDATE_RETAINED=TRUE" -ForegroundColor Yellow
            }
        }

        Write-Host "EXECUTOR_ROLLED_BACK=TRUE"
    }


    if (
        $TestPromoted `
        -and
        (Test-Path -LiteralPath $TestPath -PathType Leaf)
    ) {

        Remove-Item `
            -LiteralPath $TestPath `
            -Force

        Write-Host "B3G_TEST_ROLLED_BACK=TRUE"
    }


    $RollbackExecutorHash = (
        Get-FileHash `
            -LiteralPath $ExecutorPath `
            -Algorithm SHA256
    ).Hash


    if ($RollbackExecutorHash -ne $ExpectedExecutorPreHash) {
        throw "CRITICAL: executor rollback hash mismatch."
    }


    if (Test-Path -LiteralPath $TestPath) {
        throw "CRITICAL: B3G test remained after rollback."
    }


    Write-Host "ROLLBACK_EXECUTOR_SHA256=$RollbackExecutorHash"
    Write-Host "B3G_ROLLBACK_COMPLETE=TRUE"

    throw
}


# ============================================================
# Clean staging only after success
# ============================================================

if (Test-Path -LiteralPath $StageRoot) {

    Remove-Item `
        -LiteralPath $StageRoot `
        -Recurse `
        -Force
}

Write-Host "STAGING_DIRECTORY_REMOVED=TRUE"


# ============================================================
# Final hashes
# ============================================================

$ExecutorPostHash = (
    Get-FileHash `
        -LiteralPath $ExecutorPath `
        -Algorithm SHA256
).Hash

$TestPostHash = (
    Get-FileHash `
        -LiteralPath $TestPath `
        -Algorithm SHA256
).Hash


Write-Host ""
Write-Host "=== B3G POSTPATCH HASHES ==="

Write-Host "EXECUTOR_PREPATCH_SHA256=$ExpectedExecutorPreHash"
Write-Host "EXECUTOR_POSTPATCH_SHA256=$ExecutorPostHash"
Write-Host "B3G_TEST_SHA256=$TestPostHash"
Write-Host "BACKUP_EXECUTOR_SHA256=$BackupHash"


if ($ExecutorPostHash -eq $ExpectedExecutorPreHash) {
    throw "executor.py postpatch hash is unexpectedly unchanged."
}

if ($ExecutorPostHash -ne $StagedExecutorHash) {
    throw "Final executor differs from staged candidate."
}

if ($TestPostHash -ne $StagedTestHash) {
    throw "Final B3G test differs from staged test."
}


# ============================================================
# Final decision
# ============================================================

Write-Host ""
Write-Host "=== B3G DECISION ==="

Write-Host "EXECUTOR_LOCAL_ONLY_SHADOW_INTEGRATION_ADDED=TRUE"
Write-Host "EXECUTOR_SHADOW_RESULT_EXPOSED_OUTWARD=FALSE"

Write-Host "SHADOW_EXECUTIONREQUEST_CREATED=TRUE"
Write-Host "SHADOW_DERIVATION_CALLED=TRUE"
Write-Host "SHADOW_TRANSPORT_STATE_EXPLICIT_COMPLETED=TRUE"
Write-Host "SHADOW_DURATION_MS_EXPLICIT=TRUE"

Write-Host "SHADOW_FAIL_OPEN=TRUE"
Write-Host "SHADOW_FAILURE_CHANGES_LEGACY_EXECUTION=FALSE"

Write-Host "LEGACY_ACCEPTED_ASSIGNMENT_CHANGED=FALSE"
Write-Host "LEGACY_WRAPPER_SCHEMA_CHANGED=FALSE"
Write-Host "EXECUTE_PLAN_RETURN_SHAPE_CHANGED=FALSE"

Write-Host "PHASE_A_ROUTER_CHANGED=FALSE"
Write-Host "QUERYPLAN_BEHAVIOR_CHANGED=FALSE"
Write-Host "PLANNER_CHANGED=FALSE"
Write-Host "SERVICE_CHANGED=FALSE"
Write-Host "SPECIALIST_ENDPOINTS_CHANGED=FALSE"

Write-Host "FALLBACK_BEHAVIOR_CHANGED=FALSE"
Write-Host "RETRY_BEHAVIOR_CHANGED=FALSE"
Write-Host "EVIDENCE_BEHAVIOR_CHANGED=FALSE"
Write-Host "NETWORK_BEHAVIOR_CHANGED=FALSE"

Write-Host "B3B1_REGRESSION_TESTS_GREEN=TRUE"
Write-Host "B3G_TARGETED_TESTS_GREEN=TRUE"

Write-Host "B3G_LOCAL_ONLY_EXECUTOR_SHADOW_READY_FOR_FREEZE=TRUE"

Write-Host "NEXT_STEP_CANDIDATE=B3H_AUDIT_AND_FREEZE_LOCAL_ONLY_EXECUTOR_SHADOW"

Write-Host ""
Write-Host "BACKUP_DIR=$BackupRoot"
Write-Host "EXECUTOR_POSTPATCH_SHA256=$ExecutorPostHash"
Write-Host "B3G_TEST_SHA256=$TestPostHash"

Write-Host ""
Write-Host "PROMATI_EXISTING_SOURCE_CHANGED_COUNT=1"
Write-Host "PROMATI_EXISTING_SOURCE_CHANGED_FILE=orchestrator\executor.py"
Write-Host "PROMATI_NEW_TEST_FILE_COUNT=1"

Write-Host "PHASE_A_FROZEN_FILES_CHANGED=FALSE"
Write-Host "B3B2_FREEZE_ARTIFACTS_CHANGED=FALSE"
Write-Host "B3E_FREEZE_ARTIFACTS_CHANGED=FALSE"

Write-Host "ARTIFACT_FILES_WRITTEN=FALSE"
Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"

Write-Host "PHASE_B3G_COMPLETE=TRUE" -ForegroundColor Green