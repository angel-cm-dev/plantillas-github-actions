import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_workflows import validate_repo  # noqa: E402

REUSABLE = """
name: Reusable
on:
  workflow_call:
    inputs:
      version:
        description: Versión
        type: string
        default: "1"
      token-name:
        description: Requerido
        type: string
        required: true
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo ${{ inputs.version }} ${{ inputs.token-name }}
"""

CALLER = """
name: Caller
on: push
permissions:
  contents: read
jobs:
  call:
    uses: ./.github/workflows/reusable-x.yml
    with:
      token-name: abc
"""


class RepoFixture:
    """Crea un repositorio temporal con archivos de workflow."""

    def __init__(self, files: dict[str, str]):
        self.files = files

    def __enter__(self) -> Path:
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / ".github" / "workflows").mkdir(parents=True)
        (self.tmp / ".github" / "pull_request_template.md").write_text("## PR\n", encoding="utf-8")
        for rel, content in self.files.items():
            path = self.tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content), encoding="utf-8")
        return self.tmp

    def __exit__(self, *exc):
        shutil.rmtree(self.tmp, ignore_errors=True)


def errors_for(files: dict[str, str]) -> list[str]:
    with RepoFixture(files) as root:
        return validate_repo(root)[0]


class RepositorioRealTests(unittest.TestCase):
    def test_el_repositorio_es_valido(self):
        errors, checked = validate_repo(ROOT)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(checked, 10)

    def test_existen_los_cuatro_reutilizables(self):
        names = {p.name for p in (ROOT / ".github" / "workflows").glob("reusable-*.yml")}
        self.assertEqual(
            names,
            {"reusable-dotnet.yml", "reusable-node.yml", "reusable-python.yml", "reusable-docker-ghcr.yml"},
        )


class ValidadorTests(unittest.TestCase):
    def base(self, **overrides):
        files = {
            ".github/workflows/reusable-x.yml": REUSABLE,
            ".github/workflows/caller.yml": CALLER,
        }
        files.update(overrides)
        return files

    def test_fixture_valido(self):
        self.assertEqual(errors_for(self.base()), [])

    def test_input_requerido_faltante_e_input_desconocido(self):
        caller = CALLER.replace("token-name: abc", "otro: 1")
        errors = errors_for(self.base(**{".github/workflows/caller.yml": caller}))
        self.assertTrue(any("falta el input requerido 'token-name'" in e for e in errors))
        self.assertTrue(any("input 'otro' no existe" in e for e in errors))

    def test_workflow_reutilizable_inexistente(self):
        caller = CALLER.replace("reusable-x.yml", "no-existe.yml")
        errors = errors_for(self.base(**{".github/workflows/caller.yml": caller}))
        self.assertTrue(any("no existe el workflow reutilizable" in e for e in errors))

    def test_input_no_declarado_en_reutilizable(self):
        reusable = REUSABLE.replace("${{ inputs.version }}", "${{ inputs.fantasma }}")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("inputs.fantasma" in e for e in errors))

    def test_secret_no_declarado(self):
        reusable = REUSABLE.replace("echo ${{ inputs.version }}", "echo ${{ secrets.NPM_TOKEN }}")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("secrets.NPM_TOKEN" in e for e in errors))

    def test_tipo_y_default_de_input(self):
        reusable = REUSABLE.replace('type: string\n        default: "1"', "type: boolean\n        default: \"si\"")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("no es de tipo boolean" in e for e in errors))

    def test_reusable_sin_workflow_call(self):
        reusable = REUSABLE.replace("workflow_call:", "workflow_dispatch:")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("deben declarar on.workflow_call" in e for e in errors))

    def test_accion_sin_version_o_flotante(self):
        reusable = REUSABLE.replace("actions/checkout@v4", "actions/checkout@main")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("referencia flotante" in e for e in errors))
        reusable = REUSABLE.replace("actions/checkout@v4", "actions/checkout")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("no está fijada" in e for e in errors))

    def test_step_con_uses_y_run(self):
        reusable = REUSABLE.replace("- uses: actions/checkout@v4", "- uses: actions/checkout@v4\n        run: echo")
        errors = errors_for(self.base(**{".github/workflows/reusable-x.yml": reusable}))
        self.assertTrue(any("exactamente uno de 'uses' o 'run'" in e for e in errors))

    def test_permissions_obligatorio(self):
        caller = CALLER.replace("permissions:\n  contents: read\n", "")
        errors = errors_for(self.base(**{".github/workflows/caller.yml": caller}))
        self.assertTrue(any("define 'permissions'" in e for e in errors))

    def test_needs_inexistente(self):
        caller = CALLER.replace("  call:\n", "  call:\n    needs: [fantasma]\n")
        errors = errors_for(self.base(**{".github/workflows/caller.yml": caller}))
        self.assertTrue(any("needs 'fantasma' no existe" in e for e in errors))

    def test_yaml_invalido(self):
        errors = errors_for(self.base(**{".github/workflows/roto.yml": "name: x\nname: y\n"}))
        self.assertTrue(any("YAML inválido" in e for e in errors))

    def test_dependabot(self):
        bad = """
        version: 2
        updates:
          - package-ecosystem: npmx
            directory: "/no-existe"
            schedule:
              interval: hourly
        """
        errors = errors_for(self.base(**{".github/dependabot.yml": bad}))
        self.assertTrue(any("package-ecosystem inválido" in e for e in errors))
        self.assertTrue(any("no existe" in e and "/no-existe" in e for e in errors))
        self.assertTrue(any("schedule.interval" in e for e in errors))

    def test_issue_template(self):
        bad = """
        name: Bug
        description: x
        body:
          - type: radio
          - type: dropdown
            attributes:
              label: Opción
        """
        errors = errors_for(self.base(**{".github/ISSUE_TEMPLATE/bug.yml": bad}))
        self.assertTrue(any("type inválido 'radio'" in e for e in errors))
        self.assertTrue(any("dropdown necesita options" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
