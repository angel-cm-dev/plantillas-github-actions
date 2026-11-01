#!/usr/bin/env python3
"""Validador estructural de workflows de GitHub Actions, plantillas de issues y dependabot.

Sin dependencias externas: usa ``yamlmini`` (subconjunto de YAML) para leer los archivos.

Reglas principales
------------------
* Todo workflow tiene ``name``, ``on``, ``jobs`` y ``permissions`` explícitos (global o por job).
* Cada job define ``runs-on`` + ``steps`` o bien ``uses`` (llamada a workflow reutilizable).
* Cada step tiene ``uses`` o ``run``; las acciones externas se fijan a una versión (no ``@main``).
* Los workflows ``reusable-*`` exponen ``on.workflow_call`` con inputs tipados y documentados,
  y solo referencian ``inputs.*`` / ``secrets.*`` declarados.
* Las llamadas locales (``uses: ./.github/workflows/x.yml``) apuntan a archivos existentes,
  envían solo inputs declarados y todos los requeridos.
* ``dependabot.yml`` e ``ISSUE_TEMPLATE/*.yml`` cumplen su esquema básico.

Uso: python scripts/validate_workflows.py [raíz-del-repo]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yamlmini import YamlError, load_file  # noqa: E402

INPUT_TYPES = {"string": str, "boolean": bool, "number": (int, float)}
INPUT_REF = re.compile(r"\binputs\.([A-Za-z_][A-Za-z0-9_-]*)")
SECRET_REF = re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)")
FLOATING_REFS = {"main", "master", "latest", "head", "develop"}
ISSUE_FIELD_TYPES = {"markdown", "textarea", "input", "dropdown", "checkboxes"}
DEPENDABOT_ECOSYSTEMS = {
    "bundler", "cargo", "composer", "devcontainers", "docker", "docker-compose", "dotnet-sdk",
    "elm", "github-actions", "gitsubmodule", "gomod", "gradle", "helm", "maven", "mix", "npm",
    "nuget", "pip", "pub", "swift", "terraform", "uv", "bun",
}
DEPENDABOT_INTERVALS = {"daily", "weekly", "monthly", "quarterly", "semiannually", "yearly", "cron"}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def reusable_interface(wf: dict) -> dict | None:
    on = wf.get("on")
    if isinstance(on, dict) and "workflow_call" in on:
        return on["workflow_call"] or {}
    return None


def check_action_ref(uses: str, where: str, errors: list[str]) -> None:
    if uses.startswith("./") or uses.startswith("docker://"):
        return
    if "@" not in uses:
        errors.append(f"{where}: la acción '{uses}' no está fijada a una versión")
        return
    ref = uses.rsplit("@", 1)[1]
    if ref.lower() in FLOATING_REFS:
        errors.append(f"{where}: la acción '{uses}' usa una referencia flotante '@{ref}'")


def validate_reusable(name: str, wf: dict, interface: dict, errors: list[str]) -> None:
    inputs = interface.get("inputs") or {}
    secrets = interface.get("secrets") or {}
    if not isinstance(inputs, dict) or not isinstance(secrets, dict):
        errors.append(f"{name}: workflow_call.inputs/secrets deben ser mapas")
        return

    for key, spec in inputs.items():
        where = f"{name}: input '{key}'"
        if not isinstance(spec, dict):
            errors.append(f"{where} debe ser un mapa")
            continue
        if not spec.get("description"):
            errors.append(f"{where} no tiene description")
        typ = spec.get("type")
        if typ not in INPUT_TYPES:
            errors.append(f"{where} tiene type inválido: {typ!r}")
            continue
        if "default" in spec and spec["default"] is not None:
            default = spec["default"]
            is_expr = isinstance(default, str) and "${{" in default
            if not is_expr and (not isinstance(default, INPUT_TYPES[typ]) or (typ == "number" and isinstance(default, bool))):
                errors.append(f"{where}: default {default!r} no es de tipo {typ}")
        if spec.get("required") is True and "default" in spec:
            errors.append(f"{where}: un input requerido no debería tener default")

    for key, spec in secrets.items():
        if not isinstance(spec, dict) or not spec.get("description"):
            errors.append(f"{name}: secret '{key}' necesita description")

    outputs = interface.get("outputs") or {}
    for key, spec in outputs.items():
        if not isinstance(spec, dict) or "value" not in spec:
            errors.append(f"{name}: output '{key}' necesita value")
        elif not re.search(r"jobs\.[\w-]+\.outputs\.", str(spec["value"])):
            errors.append(f"{name}: output '{key}' debe tomar su valor de jobs.<id>.outputs")

    body = {k: v for k, v in wf.items() if k != "on"}
    for text in _strings(body):
        for ref in INPUT_REF.findall(text):
            if ref not in inputs:
                errors.append(f"{name}: usa inputs.{ref} que no está declarado")
        for ref in SECRET_REF.findall(text):
            if ref != "GITHUB_TOKEN" and ref not in secrets:
                errors.append(f"{name}: usa secrets.{ref} que no está declarado")


def validate_call(name: str, job_id: str, job: dict, root: Path, interfaces: dict, errors: list[str]) -> None:
    uses = job["uses"]
    where = f"{name}: job '{job_id}'"
    if not uses.startswith("./"):
        if "@" not in uses:
            errors.append(f"{where}: el workflow remoto '{uses}' debe fijarse con @versión")
        return
    target = (root / uses).resolve()
    if not target.is_file():
        errors.append(f"{where}: no existe el workflow reutilizable '{uses}'")
        return
    interface = interfaces.get(target)
    if interface is None:
        errors.append(f"{where}: '{uses}' no declara on.workflow_call")
        return
    declared = interface.get("inputs") or {}
    given = job.get("with") or {}
    for key in given:
        if key not in declared:
            errors.append(f"{where}: input '{key}' no existe en {target.name}")
    for key, spec in declared.items():
        if isinstance(spec, dict) and spec.get("required") is True and key not in given:
            errors.append(f"{where}: falta el input requerido '{key}'")
    secrets = job.get("secrets")
    if isinstance(secrets, dict):
        declared_secrets = interface.get("secrets") or {}
        for key in secrets:
            if key not in declared_secrets:
                errors.append(f"{where}: secret '{key}' no existe en {target.name}")
    elif secrets not in (None, "inherit"):
        errors.append(f"{where}: secrets debe ser un mapa o 'inherit'")
    for forbidden in ("steps", "runs-on"):
        if forbidden in job:
            errors.append(f"{where}: un job con 'uses' no puede tener '{forbidden}'")


def validate_workflow(name: str, wf, root: Path, interfaces: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(wf, dict):
        return [f"{name}: el workflow debe ser un mapa"]
    for key in ("name", "on", "jobs"):
        if key not in wf:
            errors.append(f"{name}: falta la clave '{key}'")
    jobs = wf.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        errors.append(f"{name}: 'jobs' debe ser un mapa no vacío")
        return errors

    global_perms = "permissions" in wf
    for job_id, job in jobs.items():
        where = f"{name}: job '{job_id}'"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", job_id):
            errors.append(f"{where}: id de job inválido")
        if not isinstance(job, dict):
            errors.append(f"{where} debe ser un mapa")
            continue
        if not global_perms and "permissions" not in job:
            errors.append(f"{where}: define 'permissions' (global o por job) con mínimo privilegio")
        needs = job.get("needs")
        for need in [needs] if isinstance(needs, str) else (needs or []):
            if need not in jobs:
                errors.append(f"{where}: needs '{need}' no existe")
        if "uses" in job:
            validate_call(name, job_id, job, root, interfaces, errors)
            continue
        if "runs-on" not in job:
            errors.append(f"{where}: falta 'runs-on'")
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{where}: 'steps' debe ser una lista no vacía")
            continue
        ids = set()
        for i, step in enumerate(steps):
            swhere = f"{where} step {i + 1}"
            if not isinstance(step, dict):
                errors.append(f"{swhere}: debe ser un mapa")
                continue
            has_uses, has_run = "uses" in step, "run" in step
            if has_uses == has_run:
                errors.append(f"{swhere}: debe tener exactamente uno de 'uses' o 'run'")
            if has_uses:
                check_action_ref(str(step["uses"]), swhere, errors)
            if "id" in step:
                if step["id"] in ids:
                    errors.append(f"{swhere}: id duplicado '{step['id']}'")
                ids.add(step["id"])

    interface = reusable_interface(wf)
    if Path(name).name.startswith("reusable-"):
        if interface is None:
            errors.append(f"{name}: los workflows reusable-* deben declarar on.workflow_call")
        else:
            validate_reusable(name, wf, interface, errors)
    return errors


def validate_dependabot(path: Path) -> list[str]:
    errors: list[str] = []
    data = load_file(path)
    if not isinstance(data, dict) or data.get("version") != 2:
        return [f"{path.name}: debe declarar version: 2"]
    updates = data.get("updates")
    if not isinstance(updates, list) or not updates:
        return [f"{path.name}: 'updates' debe ser una lista no vacía"]
    seen = set()
    for i, upd in enumerate(updates):
        where = f"{path.name}: updates[{i}]"
        eco = upd.get("package-ecosystem")
        if eco not in DEPENDABOT_ECOSYSTEMS:
            errors.append(f"{where}: package-ecosystem inválido {eco!r}")
        directory = upd.get("directory")
        if not isinstance(directory, str) or not directory.startswith("/"):
            errors.append(f"{where}: directory debe empezar con '/'")
        elif directory != "/" and not (path.parent.parent / directory.lstrip("/")).is_dir():
            errors.append(f"{where}: el directorio {directory} no existe")
        interval = (upd.get("schedule") or {}).get("interval")
        if interval not in DEPENDABOT_INTERVALS:
            errors.append(f"{where}: schedule.interval inválido {interval!r}")
        if (eco, directory) in seen:
            errors.append(f"{where}: entrada duplicada para {eco} {directory}")
        seen.add((eco, directory))
    return errors


def validate_issue_template(path: Path) -> list[str]:
    data = load_file(path)
    if path.name == "config.yml":
        if not isinstance(data, dict) or not isinstance(data.get("blank_issues_enabled"), bool):
            return [f"{path.name}: blank_issues_enabled debe ser booleano"]
        return [f"{path.name}: contact_links[{i}] incompleto" for i, link in enumerate(data.get("contact_links") or [])
                if not all(link.get(k) for k in ("name", "url", "about"))]
    errors = []
    for key in ("name", "description", "body"):
        if not data.get(key):
            errors.append(f"{path.name}: falta '{key}'")
    ids = set()
    for i, field in enumerate(data.get("body") or []):
        where = f"{path.name}: body[{i}]"
        if field.get("type") not in ISSUE_FIELD_TYPES:
            errors.append(f"{where}: type inválido {field.get('type')!r}")
            continue
        attrs = field.get("attributes") or {}
        if field["type"] == "markdown":
            if not attrs.get("value"):
                errors.append(f"{where}: markdown necesita attributes.value")
            continue
        if not attrs.get("label"):
            errors.append(f"{where}: falta attributes.label")
        if field["type"] in ("dropdown", "checkboxes") and not attrs.get("options"):
            errors.append(f"{where}: {field['type']} necesita options")
        fid = field.get("id")
        if fid in ids:
            errors.append(f"{where}: id duplicado {fid!r}")
        ids.add(fid)
    return errors


def validate_repo(root: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    workflows_dir = root / ".github" / "workflows"
    files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
    parsed: dict[Path, object] = {}
    for path in files:
        try:
            parsed[path.resolve()] = load_file(path)
        except YamlError as exc:
            errors.append(f"{path.name}: YAML inválido ({exc})")
    interfaces = {p: reusable_interface(wf) for p, wf in parsed.items() if isinstance(wf, dict)}
    for path, wf in parsed.items():
        errors.extend(validate_workflow(path.name, wf, root, interfaces))

    checked = len(files)
    dependabot = root / ".github" / "dependabot.yml"
    if dependabot.exists():
        checked += 1
        try:
            errors.extend(validate_dependabot(dependabot))
        except YamlError as exc:
            errors.append(f"dependabot.yml: YAML inválido ({exc})")
    for path in sorted((root / ".github" / "ISSUE_TEMPLATE").glob("*.yml")):
        checked += 1
        try:
            errors.extend(validate_issue_template(path))
        except YamlError as exc:
            errors.append(f"{path.name}: YAML inválido ({exc})")
    if not (root / ".github" / "pull_request_template.md").exists():
        errors.append("falta .github/pull_request_template.md")
    return errors, checked


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    errors, checked = validate_repo(root)
    for err in errors:
        print(f"ERROR  {err}")
    print(f"\n{checked} archivos revisados, {len(errors)} error(es).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
