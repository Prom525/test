$ErrorActionPreference = "Stop"

Set-Location C:\ai-platform

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-A A2d LOCAL STRUCTURAL AUDIT V1" -ForegroundColor Cyan
Write-Host " READ ONLY - EXACT AST DELTA AGAINST BACKUP" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan


$Root = "C:\ai-platform\api\app\orchestrator"

$BackupDir = `
    "C:\ai-platform\artifacts\phase_a_a2d_execution_grounding_backup_20260826_121027"


$Current = [ordered]@{
    "models.py" = Join-Path $Root "models.py"
    "understanding.py" = Join-Path $Root "understanding.py"
    "planner.py" = Join-Path $Root "planner.py"
    "band_candidate_shadow.py" = Join-Path $Root "band_candidate_shadow.py"
    "service.py" = Join-Path $Root "service.py"
    "executor.py" = Join-Path $Root "executor.py"
}


$Backup = [ordered]@{
    "models.py" = Join-Path $BackupDir "models.py"
    "understanding.py" = Join-Path $BackupDir "understanding.py"
    "planner.py" = Join-Path $BackupDir "planner.py"
}


$ExpectedPreHashes = [ordered]@{
    "models.py" = `
        "A12C7FF33F065F545CA698687788329B926922C41C3246243060344E3A843DA2"

    "understanding.py" = `
        "45A59DF819ADD0ABD54BD19CBB230C842BB2E406129E8B94F0D2395A376B5D65"

    "planner.py" = `
        "760B0CE4915E4998FD9F95FAD7FF0123606FDAF7E0C83107DA1E621A2EAAFBC2"
}


$ExpectedPostHashes = [ordered]@{
    "models.py" = `
        "CFAA831CCF5CFA39FBBA98800376F1099E587C8047EE552BCA0D6D815E852374"

    "understanding.py" = `
        "2F3F4588E7DBBE7D60DC561165795895597ED035C5FB8678094361F224F22581"

    "planner.py" = `
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"
}


$ExpectedUntouchedHashes = [ordered]@{
    "band_candidate_shadow.py" = `
        "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484"

    "service.py" = `
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"

    "executor.py" = `
        "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"
}


# ============================================================
# Presence checks
# ============================================================

foreach ($Path in $Current.Values) {
    if (-not (Test-Path $Path)) {
        throw "Current bestand ontbreekt: $Path"
    }
}

foreach ($Path in $Backup.Values) {
    if (-not (Test-Path $Path)) {
        throw "Backupbestand ontbreekt: $Path"
    }
}


# ============================================================
# Hard hash guards
# ============================================================

Write-Host ""
Write-Host "=== BACKUP PRE-A2d HASH GUARDS ==="


foreach ($Name in $ExpectedPreHashes.Keys) {

    $Actual = (
        Get-FileHash `
            $Backup[$Name] `
            -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Actual"

    if ($Actual -ne $ExpectedPreHashes[$Name]) {
        throw "Backup prehash mismatch: $Name"
    }
}


Write-Host "A2D_BACKUP_PREHASHES_OK" `
    -ForegroundColor Green


Write-Host ""
Write-Host "=== CURRENT POST-A2d HASH GUARDS ==="


foreach ($Name in $ExpectedPostHashes.Keys) {

    $Actual = (
        Get-FileHash `
            $Current[$Name] `
            -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Actual"

    if ($Actual -ne $ExpectedPostHashes[$Name]) {
        throw "Current posthash mismatch: $Name"
    }
}


Write-Host "A2D_CURRENT_POSTHASHES_OK" `
    -ForegroundColor Green


Write-Host ""
Write-Host "=== UNTOUCHED FILE HASH GUARDS ==="


foreach ($Name in $ExpectedUntouchedHashes.Keys) {

    $Actual = (
        Get-FileHash `
            $Current[$Name] `
            -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Actual"

    if ($Actual -ne $ExpectedUntouchedHashes[$Name]) {
        throw "Untouched frozen file changed: $Name"
    }
}


Write-Host "A2D_UNTOUCHED_FILES_FROZEN=TRUE" `
    -ForegroundColor Green


# ============================================================
# Exact AST normalization audit
# ============================================================

$PythonCode = @'
import ast
import copy
import pathlib
import sys


backup_models = pathlib.Path(sys.argv[1])
current_models = pathlib.Path(sys.argv[2])

backup_understanding = pathlib.Path(sys.argv[3])
current_understanding = pathlib.Path(sys.argv[4])

backup_planner = pathlib.Path(sys.argv[5])
current_planner = pathlib.Path(sys.argv[6])


def read(path):
    return path.read_text(
        encoding="utf-8-sig"
    )


def parse(path, label):
    try:
        return ast.parse(
            read(path)
        )
    except SyntaxError as exc:
        raise RuntimeError(
            f"{label}: syntax error line "
            f"{exc.lineno}: {exc.msg}"
        ) from exc


def dump(node):
    return ast.dump(
        node,
        include_attributes=False,
    )


def top_class(tree, name):

    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == name
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{name} class count={len(matches)}, expected 1"
        )

    return matches[0]


def top_function(tree, name):

    matches = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == name
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{name} function count={len(matches)}, expected 1"
        )

    return matches[0]


def assignment_name(node):

    if isinstance(node, ast.Assign):
        if len(node.targets) == 1:
            target = node.targets[0]

            if isinstance(target, ast.Name):
                return target.id

    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            return node.target.id

    return None


def call_name(node):

    if not isinstance(node, ast.Call):
        return None

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def source_segment(source, node):
    return (
        ast.get_source_segment(
            source,
            node,
        )
        or ""
    )


def contains_call(node, name):

    return any(
        isinstance(item, ast.Call)
        and call_name(item) == name
        for item in ast.walk(node)
    )


def assignment_targets(node):

    result = []

    for item in ast.walk(node):

        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    result.append(target.id)

        elif isinstance(item, ast.AnnAssign):
            if isinstance(item.target, ast.Name):
                result.append(
                    item.target.id
                )

    return result


def queryplan_returns(function_node):

    result = []

    for node in ast.walk(function_node):

        if not isinstance(node, ast.Return):
            continue

        value = node.value

        if (
            isinstance(value, ast.Call)
            and call_name(value) == "QueryPlan"
        ):
            result.append(node)

    result.sort(
        key=lambda node: node.lineno
    )

    return result


# ============================================================
# Load all six ASTs
# ============================================================

bm_source = read(backup_models)
cm_source = read(current_models)

bu_source = read(backup_understanding)
cu_source = read(current_understanding)

bp_source = read(backup_planner)
cp_source = read(current_planner)


bm = parse(
    backup_models,
    "backup models.py",
)

cm = parse(
    current_models,
    "current models.py",
)

bu = parse(
    backup_understanding,
    "backup understanding.py",
)

cu = parse(
    current_understanding,
    "current understanding.py",
)

bp = parse(
    backup_planner,
    "backup planner.py",
)

cp = parse(
    current_planner,
    "current planner.py",
)


# ============================================================
# MODELS â€” positive structural contract
# ============================================================

print("")
print("=== MODELS A2d STRUCTURE ===")


blocker_type = top_class(
    cm,
    "ExecutionBlockerType",
)

blocker_model = top_class(
    cm,
    "ExecutionBlocker",
)

current_query_plan = top_class(
    cm,
    "QueryPlan",
)


# Exact enum member.
enum_members = []

for node in blocker_type.body:

    if not isinstance(node, ast.Assign):
        continue

    if len(node.targets) != 1:
        continue

    target = node.targets[0]

    if isinstance(target, ast.Name):
        enum_members.append(
            (
                target.id,
                getattr(node.value, "value", None),
            )
        )


if enum_members != [
    (
        "UNRESOLVED_REQUIRED_ENTITY",
        "unresolved_required_entity",
    )
]:
    raise RuntimeError(
        f"Unexpected ExecutionBlockerType members: {enum_members}"
    )


# Exact blocker fields.
blocker_fields = [
    node.target.id
    for node in blocker_model.body
    if isinstance(node, ast.AnnAssign)
    and isinstance(node.target, ast.Name)
]


if blocker_fields != [
    "blocker_type",
    "entity_name",
    "candidate_value",
    "reason",
]:
    raise RuntimeError(
        f"Unexpected ExecutionBlocker fields: {blocker_fields}"
    )


queryplan_blocker_fields = [
    node
    for node in current_query_plan.body
    if isinstance(node, ast.AnnAssign)
    and isinstance(node.target, ast.Name)
    and node.target.id == "execution_blockers"
]


if len(queryplan_blocker_fields) != 1:
    raise RuntimeError(
        "QueryPlan.execution_blockers count != 1"
    )


print("A2D_EXECUTION_BLOCKER_TYPE_EXACT=TRUE")
print("A2D_EXECUTION_BLOCKER_MODEL_FIELDS_EXACT=TRUE")
print("A2D_QUERYPLAN_BLOCKER_FIELD_COUNT=1")


# ============================================================
# MODELS â€” normalize A2d away and require exact A2c AST
# ============================================================

cm_norm = copy.deepcopy(
    cm
)


removed_classes = 0

new_body = []

for node in cm_norm.body:

    if (
        isinstance(node, ast.ClassDef)
        and node.name in {
            "ExecutionBlockerType",
            "ExecutionBlocker",
        }
    ):
        removed_classes += 1
        continue

    new_body.append(node)


cm_norm.body = new_body


norm_query_plan = top_class(
    cm_norm,
    "QueryPlan",
)


old_len = len(
    norm_query_plan.body
)

norm_query_plan.body = [
    node
    for node in norm_query_plan.body
    if not (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "execution_blockers"
    )
]


removed_fields = (
    old_len
    - len(norm_query_plan.body)
)


if removed_classes != 2:
    raise RuntimeError(
        f"Models removed class count={removed_classes}, expected 2"
    )

if removed_fields != 1:
    raise RuntimeError(
        f"Models removed field count={removed_fields}, expected 1"
    )


if dump(cm_norm) != dump(bm):
    raise RuntimeError(
        "models.py contains semantic deltas beyond "
        "ExecutionBlockerType + ExecutionBlocker + "
        "QueryPlan.execution_blockers"
    )


print("A2D_MODELS_AFTER_NORMALIZATION_AST_IDENTICAL_TO_BACKUP=TRUE")


# ============================================================
# UNDERSTANDING â€” frozen A2c activation exact
# ============================================================

backup_understand = top_function(
    bu,
    "understand_query",
)

current_understand = top_function(
    cu,
    "understand_query",
)


def find_a2c_activation(
    function_node,
    source,
):

    matches = []

    for node in function_node.body:

        if not isinstance(node, ast.If):
            continue

        text = source_segment(
            source,
            node,
        )

        if (
            "_band_candidate_shadow" in text
            and "mention_only" in text
            and "comparison_member" in text
        ):
            matches.append(node)

    return matches


backup_a2c = find_a2c_activation(
    backup_understand,
    bu_source,
)

current_a2c = find_a2c_activation(
    current_understand,
    cu_source,
)


if len(backup_a2c) != 1:
    raise RuntimeError(
        "Backup A2c activation count != 1"
    )

if len(current_a2c) != 1:
    raise RuntimeError(
        "Current A2c activation count != 1"
    )


if dump(
    backup_a2c[0]
) != dump(
    current_a2c[0]
):
    raise RuntimeError(
        "Frozen A2c activation AST changed"
    )


current_a2c_text = source_segment(
    cu_source,
    current_a2c[0],
)


if "unresolved" in current_a2c_text:
    raise RuntimeError(
        "UNRESOLVED leaked into frozen A2c suppression IF"
    )


print("")
print("=== FROZEN A2c CONTRACT ===")

print("A2C_ACTIVATION_AST_IDENTICAL_TO_BACKUP=TRUE")
print("A2C_UNRESOLVED_IN_SUPPRESSION_IF=FALSE")
print("A2C_MENTION_ONLY_PRESERVED=TRUE")
print("A2C_COMPARISON_MEMBER_PRESERVED=TRUE")


# ============================================================
# UNDERSTANDING â€” positive A2d structure
# ============================================================

# Exact added model import.
a2d_imports = [
    node
    for node in cu.body
    if isinstance(node, ast.ImportFrom)
    and node.module
        == "app.orchestrator.models"
    and {
        alias.name
        for alias in node.names
    } == {
        "ExecutionBlocker",
        "ExecutionBlockerType",
    }
]


if len(a2d_imports) != 1:
    raise RuntimeError(
        "A2d models import count != 1"
    )


band_unresolved_assignments = [
    node
    for node in current_understand.body
    if assignment_name(node)
        == "_band_unresolved"
]


if len(band_unresolved_assignments) != 1:
    raise RuntimeError(
        "_band_unresolved assignment count != 1"
    )


band_unresolved_text = source_segment(
    cu_source,
    band_unresolved_assignments[0],
)


required_unresolved_tokens = (
    "band is not None",
    "_band_candidate_shadow is not None",
    '"unresolved"',
)


for token in required_unresolved_tokens:

    if token not in band_unresolved_text:
        raise RuntimeError(
            "_band_unresolved contract missing token: "
            + token
        )


blocker_initializers = [
    node
    for node in current_understand.body
    if assignment_name(node)
        == "execution_blockers"
]


if len(blocker_initializers) != 1:
    raise RuntimeError(
        "execution_blockers initializer count != 1"
    )


blocker_constructor_ifs = [
    node
    for node in current_understand.body
    if isinstance(node, ast.If)
    and contains_call(
        node,
        "ExecutionBlocker",
    )
]


if len(blocker_constructor_ifs) != 1:
    raise RuntimeError(
        "ExecutionBlocker construction IF count != 1"
    )


blocker_text = source_segment(
    cu_source,
    blocker_constructor_ifs[0],
)


for token in (
    "_band_unresolved",
    'entity_name="band_code"',
    "candidate_value=band.value",
    "ExecutionBlockerType.UNRESOLVED_REQUIRED_ENTITY",
    'reason="band_candidate_unresolved"',
):

    if token not in blocker_text:
        raise RuntimeError(
            "Blocker construction contract missing: "
            + token
        )


# band_code emission must be guarded by NOT unresolved.
band_entity_ifs = []

for node in current_understand.body:

    if not isinstance(node, ast.If):
        continue

    text = source_segment(
        cu_source,
        node,
    )

    if 'entities["band_code"] = band' in text:
        band_entity_ifs.append(node)


if len(band_entity_ifs) != 1:
    raise RuntimeError(
        "band entity emission IF count != 1"
    )


band_entity_test = source_segment(
    cu_source,
    band_entity_ifs[0].test,
)


if (
    "band" not in band_entity_test
    or "_band_unresolved"
        not in band_entity_test
):
    raise RuntimeError(
        "band entity unresolved guard missing"
    )


# Two derived UX uses:
# clarification_required and clarification_question.
execution_blocker_test_ifs = []

for node in current_understand.body:

    if not isinstance(node, ast.If):
        continue

    test_text = source_segment(
        cu_source,
        node.test,
    ).strip()

    if test_text == "execution_blockers":
        execution_blocker_test_ifs.append(node)


if len(execution_blocker_test_ifs) != 2:
    raise RuntimeError(
        "execution_blockers clarification IF count != 2"
    )


derived_targets = sorted(
    target
    for node in execution_blocker_test_ifs
    for target in assignment_targets(node)
)


if derived_targets != [
    "clarification_question",
    "clarification_required",
]:
    raise RuntimeError(
        f"Unexpected blocker-derived targets: {derived_targets}"
    )


# Exactly one final QueryPlan execution_blockers keyword.
current_returns = queryplan_returns(
    current_understand
)


if len(current_returns) != 4:
    raise RuntimeError(
        "Current QueryPlan return count != 4"
    )


blocker_keywords = []

for return_node in current_returns:

    for keyword in return_node.value.keywords:

        if keyword.arg == "execution_blockers":
            blocker_keywords.append(
                (
                    return_node,
                    keyword,
                )
            )


if len(blocker_keywords) != 1:
    raise RuntimeError(
        "QueryPlan execution_blockers keyword count != 1"
    )


if blocker_keywords[0][0] is not current_returns[-1]:
    raise RuntimeError(
        "execution_blockers emitted outside main QueryPlan return"
    )


# Ordering: establish unresolved before scoring.
score_nodes = [
    node
    for node in current_understand.body
    if isinstance(node, ast.Assign)
    and isinstance(node.value, ast.Call)
    and call_name(node.value)
        == "_score_domain"
]


if len(score_nodes) != 1:
    raise RuntimeError(
        "_score_domain assignment count != 1"
    )


if not (
    band_unresolved_assignments[0].lineno
    < score_nodes[0].lineno
):
    raise RuntimeError(
        "_band_unresolved not established before scoring"
    )


print("")
print("=== A2d UNDERSTANDING CONTRACT ===")

print("A2D_UNRESOLVED_STATUS_PROBE_COUNT=1")
print("A2D_UNRESOLVED_ESTABLISHED_BEFORE_SCORING=TRUE")
print("A2D_BLOCKER_INITIALIZER_COUNT=1")
print("A2D_BLOCKER_CONSTRUCTOR_COUNT=1")
print("A2D_BLOCKER_TYPE_UNRESOLVED_REQUIRED_ENTITY=TRUE")
print("A2D_BLOCKER_ENTITY_NAME_BAND_CODE=TRUE")
print("A2D_BLOCKER_CANDIDATE_FROM_BAND_VALUE=TRUE")
print("A2D_UNRESOLVED_VALIDATED_BAND_EMISSION_BLOCKED=TRUE")
print("A2D_CLARIFICATION_DERIVED_FROM_BLOCKER=TRUE")
print("A2D_MAIN_QUERYPLAN_BLOCKER_EMISSION_COUNT=1")


# ============================================================
# UNDERSTANDING â€” exact normalization back to frozen A2c
# ============================================================

cu_norm = copy.deepcopy(
    cu
)


# Remove exact new A2d import.
removed_imports = 0
new_top_body = []

for node in cu_norm.body:

    if (
        isinstance(node, ast.ImportFrom)
        and node.module
            == "app.orchestrator.models"
        and {
            alias.name
            for alias in node.names
        } == {
            "ExecutionBlocker",
            "ExecutionBlockerType",
        }
    ):
        removed_imports += 1
        continue

    new_top_body.append(node)


cu_norm.body = new_top_body


norm_understand = top_function(
    cu_norm,
    "understand_query",
)


removed_band_unresolved = 0
removed_blocker_init = 0
removed_blocker_constructor = 0
removed_blocker_ux_ifs = 0
reverted_band_emit = 0


normalized_body = []


for node in norm_understand.body:

    name = assignment_name(node)

    if name == "_band_unresolved":
        removed_band_unresolved += 1
        continue

    if name == "execution_blockers":
        removed_blocker_init += 1
        continue


    if isinstance(node, ast.If):

        if contains_call(
            node,
            "ExecutionBlocker",
        ):
            removed_blocker_constructor += 1
            continue


        test_text = (
            ast.unparse(node.test)
            if hasattr(ast, "unparse")
            else ""
        ).strip()

        if test_text == "execution_blockers":
            removed_blocker_ux_ifs += 1
            continue


        # Revert exactly the A2d band-emission guard.
        #
        # Detect this AST-semantically instead of using ast.unparse()
        # string formatting. ast.unparse() may normalize quote style
        # and therefore is not a safe structural identity test.
        is_band_entity_emission = False

        if (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Assign)
            and len(node.body[0].targets) == 1
        ):
            stmt = node.body[0]
            target = stmt.targets[0]

            is_band_entity_emission = (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "entities"
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "band_code"
                and isinstance(stmt.value, ast.Name)
                and stmt.value.id == "band"
            )

        if is_band_entity_emission:

            node.test = ast.Name(
                id="band",
                ctx=ast.Load(),
            )

            reverted_band_emit += 1


    normalized_body.append(node)


norm_understand.body = normalized_body


# Remove execution_blockers keyword from main QueryPlan.
removed_keywords = 0

for return_node in ast.walk(
    norm_understand
):

    if not isinstance(
        return_node,
        ast.Return,
    ):
        continue

    call = return_node.value

    if not (
        isinstance(call, ast.Call)
        and call_name(call) == "QueryPlan"
    ):
        continue

    new_keywords = []

    for keyword in call.keywords:

        if keyword.arg == "execution_blockers":
            removed_keywords += 1
            continue

        new_keywords.append(keyword)

    call.keywords = new_keywords


if removed_imports != 1:
    raise RuntimeError(
        f"Normalized A2d import removals="
        f"{removed_imports}, expected 1"
    )

if removed_band_unresolved != 1:
    raise RuntimeError(
        f"_band_unresolved removals="
        f"{removed_band_unresolved}, expected 1"
    )

if removed_blocker_init != 1:
    raise RuntimeError(
        f"blocker initializer removals="
        f"{removed_blocker_init}, expected 1"
    )

if removed_blocker_constructor != 1:
    raise RuntimeError(
        f"blocker constructor removals="
        f"{removed_blocker_constructor}, expected 1"
    )

if removed_blocker_ux_ifs != 2:
    raise RuntimeError(
        f"blocker UX IF removals="
        f"{removed_blocker_ux_ifs}, expected 2"
    )

if reverted_band_emit != 1:
    raise RuntimeError(
        f"band emission reversions="
        f"{reverted_band_emit}, expected 1"
    )

if removed_keywords != 1:
    raise RuntimeError(
        f"QueryPlan blocker keyword removals="
        f"{removed_keywords}, expected 1"
    )


ast.fix_missing_locations(
    cu_norm
)


if dump(cu_norm) != dump(bu):
    raise RuntimeError(
        "understanding.py contains semantic deltas "
        "outside the intended A2d grounding patch"
    )


print("")
print("=== UNDERSTANDING EXACT DELTA PROOF ===")

print("A2D_UNDERSTANDING_NORMALIZATION_REMOVED_IMPORTS=1")
print("A2D_UNDERSTANDING_NORMALIZATION_REMOVED_STATUS_PROBE=1")
print("A2D_UNDERSTANDING_NORMALIZATION_REMOVED_BLOCKER_INIT=1")
print("A2D_UNDERSTANDING_NORMALIZATION_REMOVED_BLOCKER_CONSTRUCTOR=1")
print("A2D_UNDERSTANDING_NORMALIZATION_REMOVED_BLOCKER_UX_IFS=2")
print("A2D_UNDERSTANDING_NORMALIZATION_REVERTED_BAND_EMISSION=1")
print("A2D_UNDERSTANDING_NORMALIZATION_REMOVED_QP_KEYWORD=1")
print("A2D_UNDERSTANDING_AFTER_NORMALIZATION_AST_IDENTICAL_TO_BACKUP=TRUE")


# ============================================================
# Diagnostics functions must themselves be untouched
# ============================================================

def top_functions_by_name(tree):

    return {
        node.name: node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }


backup_functions = top_functions_by_name(
    bu
)

current_functions = top_functions_by_name(
    cu
)


diagnostic_names = sorted(
    name
    for name in backup_functions
    if "diagnostic" in name.casefold()
)


if not diagnostic_names:
    raise RuntimeError(
        "No diagnostics functions found for freeze audit"
    )


diagnostic_failures = []

for name in diagnostic_names:

    if name not in current_functions:
        diagnostic_failures.append(
            name + ":missing"
        )
        continue

    if dump(
        backup_functions[name]
    ) != dump(
        current_functions[name]
    ):
        diagnostic_failures.append(
            name + ":changed"
        )


if diagnostic_failures:
    raise RuntimeError(
        "Diagnostics functions changed: "
        + ",".join(
            diagnostic_failures
        )
    )


print("")
print("=== DIAGNOSTICS FREEZE ===")

print(
    "DIAGNOSTICS_FUNCTION_COUNT="
    + str(
        len(diagnostic_names)
    )
)

print(
    "DIAGNOSTICS_FUNCTIONS_AST_UNCHANGED=TRUE"
)

print(
    "DIAGNOSTICS_DOMAIN_LOGIC_CHANGED=FALSE"
)


# ============================================================
# PLANNER â€” exact blocker gate
# ============================================================

backup_build = top_function(
    bp,
    "build_execution_plan",
)

current_build = top_function(
    cp,
    "build_execution_plan",
)


reset_nodes = []
blocker_gates = []
clarification_gates = []
domains_nodes = []


for node in current_build.body:

    text = source_segment(
        cp_source,
        node,
    )

    if (
        isinstance(node, ast.Assign)
        and "plan.execution_steps = []"
            in text
    ):
        reset_nodes.append(node)


    if isinstance(node, ast.If):

        test_text = source_segment(
            cp_source,
            node.test,
        ).strip()

        if test_text == "plan.execution_blockers":
            blocker_gates.append(node)

        if test_text == "plan.clarification_required":
            clarification_gates.append(node)


    if assignment_name(node) == "domains":
        domains_nodes.append(node)


if len(reset_nodes) != 1:
    raise RuntimeError(
        "planner reset count != 1"
    )

if len(blocker_gates) != 1:
    raise RuntimeError(
        "planner blocker gate count != 1"
    )

if len(clarification_gates) != 1:
    raise RuntimeError(
        "planner clarification gate count != 1"
    )

if len(domains_nodes) != 1:
    raise RuntimeError(
        "planner domains assignment count != 1"
    )


gate = blocker_gates[0]


if len(gate.body) != 1:
    raise RuntimeError(
        "planner blocker gate body count != 1"
    )


if not (
    isinstance(gate.body[0], ast.Return)
    and isinstance(gate.body[0].value, ast.Name)
    and gate.body[0].value.id == "plan"
):
    raise RuntimeError(
        "planner blocker gate is not exact return plan"
    )


# AST-body adjacency, ignoring blank lines/comments.
body_positions = {
    id(node): index
    for index, node in enumerate(
        current_build.body
    )
}


reset_pos = body_positions[
    id(reset_nodes[0])
]

blocker_pos = body_positions[
    id(blocker_gates[0])
]

clarification_pos = body_positions[
    id(clarification_gates[0])
]

domains_pos = body_positions[
    id(domains_nodes[0])
]


if blocker_pos != reset_pos + 1:
    raise RuntimeError(
        "planner blocker gate is not immediately "
        "after execution_steps reset"
    )


if not (
    reset_pos
    < blocker_pos
    < clarification_pos
    < domains_pos
):
    raise RuntimeError(
        "planner safety-gate ordering contract failed"
    )


print("")
print("=== PLANNER A2d GATE ===")

print("A2D_PLANNER_EXECUTION_RESET_COUNT=1")
print("A2D_PLANNER_BLOCKER_GATE_COUNT=1")
print("A2D_PLANNER_BLOCKER_GATE_EXACT_RETURN_PLAN=TRUE")
print("A2D_PLANNER_BLOCKER_IMMEDIATELY_AFTER_RESET=TRUE")
print("A2D_PLANNER_BLOCKER_BEFORE_CLARIFICATION=TRUE")
print("A2D_PLANNER_BLOCKER_BEFORE_DOMAIN_BUILD=TRUE")


# Normalize planner by removing only blocker gate.
cp_norm = copy.deepcopy(
    cp
)

norm_build = top_function(
    cp_norm,
    "build_execution_plan",
)


removed_planner_gates = 0
new_body = []


for node in norm_build.body:

    if isinstance(node, ast.If):

        test_text = (
            ast.unparse(node.test)
            if hasattr(ast, "unparse")
            else ""
        ).strip()

        if test_text == "plan.execution_blockers":
            removed_planner_gates += 1
            continue

    new_body.append(node)


norm_build.body = new_body


if removed_planner_gates != 1:
    raise RuntimeError(
        f"planner normalized gate removals="
        f"{removed_planner_gates}, expected 1"
    )


if dump(cp_norm) != dump(bp):
    raise RuntimeError(
        "planner.py contains semantic deltas "
        "outside the A2d blocker gate"
    )


print("A2D_PLANNER_AFTER_NORMALIZATION_AST_IDENTICAL_TO_BACKUP=TRUE")


# ============================================================
# Whole audit success
# ============================================================

print("")
print("A2D_MODELS_ONLY_INTENDED_AST_DELTA=TRUE")
print("A2D_UNDERSTANDING_ONLY_INTENDED_AST_DELTA=TRUE")
print("A2D_PLANNER_ONLY_INTENDED_AST_DELTA=TRUE")

print("A2C_FROZEN_SEMANTICS_PRESERVED=TRUE")
print("A2D_UNRESOLVED_ONLY_AT_GROUNDING_BOUNDARY=TRUE")
print("A2D_SERVICE_PATCH_REQUIRED=FALSE")
print("A2D_EXECUTOR_PATCH_REQUIRED=FALSE")

print("")
print("PHASE_A_A2D_LOCAL_STRUCTURAL_AUDIT_OK")
'@


$Raw = (
    $PythonCode |
        python - `
            $Backup["models.py"] `
            $Current["models.py"] `
            $Backup["understanding.py"] `
            $Current["understanding.py"] `
            $Backup["planner.py"] `
            $Current["planner.py"]
)

if ($LASTEXITCODE -ne 0) {
    throw "A2d exact structural audit mislukt."
}


$Raw |
    ForEach-Object {
        Write-Host $_
    }


# ============================================================
# Independent syntax checks
# ============================================================

Write-Host ""
Write-Host "=== INDEPENDENT SYNTAX CHECKS ==="


foreach ($Path in @(
    $Current["models.py"],
    $Current["understanding.py"],
    $Current["planner.py"],
    $Current["band_candidate_shadow.py"],
    $Current["service.py"],
    $Current["executor.py"]
)) {

    python -c `
        "import ast,pathlib,sys; p=pathlib.Path(sys.argv[1]); ast.parse(p.read_bytes().decode('utf-8-sig')); print('SYNTAX_OK',p.name)" `
        $Path

    if ($LASTEXITCODE -ne 0) {
        throw "Syntaxcheck mislukt: $Path"
    }
}


Write-Host ""
Write-Host "NO_FILES_WRITTEN=TRUE"
Write-Host "NO_APP_CODE_CHANGED_BY_AUDIT=TRUE"
Write-Host "NO_CONTAINER_CALLS=TRUE"
Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_RESEARCH_PROVIDER_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"

Write-Host "PHASE_A_A2D_LOCAL_STRUCTURAL_AUDIT_COMPLETE" `
    -ForegroundColor Green
