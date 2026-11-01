# plantillas-github-actions

Workflows reutilizables de GitHub Actions (`workflow_call`) para .NET, Node.js, Python y publicación de imágenes Docker en GHCR.

![CI](https://img.shields.io/github/actions/workflow/status/angel-cm-dev/plantillas-github-actions/ci.yml?branch=main&label=CI)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-reutilizables-2088FF?logo=githubactions&logoColor=white)
![Python](https://img.shields.io/badge/validador-Python%20stdlib-3776AB?logo=python&logoColor=white)
![Dependabot](https://img.shields.io/badge/Dependabot-activo-025E8C?logo=dependabot&logoColor=white)
![License](https://img.shields.io/badge/licencia-MIT-green)

## Características

| Workflow | Qué hace | Inputs principales |
|---|---|---|
| `reusable-dotnet.yml` | restore (con caché NuGet), `dotnet format` opcional, build, test con resultados TRX | `dotnet-version`, `working-directory`, `configuration`, `run-format-check` |
| `reusable-node.yml` | matriz de versiones, `npm ci` con caché, lint, test y build opcionales | `node-versions` (JSON), `working-directory`, `run-lint`, `run-build` |
| `reusable-python.yml` | pip con caché, `ruff check`, `pytest` con reporte JUnit | `python-version`, `working-directory`, `requirements-file`, `run-lint` |
| `reusable-docker-ghcr.yml` | Buildx multi-plataforma, tags automáticos (rama, PR, semver, SHA), caché GHA, provenance, push a `ghcr.io` | `image-name`, `context`, `dockerfile`, `platforms`, `push` → outputs `digest`, `tags` |

Además:

- `ejemplo-consumidor.yml`: consume los cuatro workflows sobre apps de ejemplo reales en `examples/` (Node, Python, .NET y Docker).
- Plantillas de **issues** (formularios YAML) y de **pull request**, y `dependabot.yml` para Actions, npm, pip, NuGet y Docker.
- **Validador estructural sin dependencias** (`scripts/validate_workflows.py` + parser YAML mínimo): inputs tipados y documentados, referencias `inputs.*`/`secrets.*` declaradas, llamadas a reutilizables con inputs válidos y requeridos, acciones fijadas a versión, `permissions` explícitos, esquema de dependabot y de formularios de issues.
- Mínimo privilegio: todos los workflows declaran `permissions`.

## Requisitos

- Un repositorio en GitHub con Actions habilitado.
- Para publicar en GHCR: el job que llama debe otorgar `packages: write`.
- Python 3.10+ para ejecutar el validador localmente (sin `pip install`).

## Instalación y uso

Referencia los workflows desde tu repositorio fijando una versión (tag o SHA):

```yaml
# .github/workflows/ci.yml en tu proyecto
name: CI
on: [push, pull_request]
permissions:
  contents: read

jobs:
  test:
    uses: angel-cm-dev/plantillas-github-actions/.github/workflows/reusable-node.yml@v1
    with:
      node-versions: '["20", "22"]'

  image:
    needs: test
    if: github.ref == 'refs/heads/main'
    uses: angel-cm-dev/plantillas-github-actions/.github/workflows/reusable-docker-ghcr.yml@v1
    permissions:
      contents: read
      packages: write
    with:
      platforms: linux/amd64,linux/arm64
```

Validar el repositorio localmente:

```bash
git clone https://github.com/angel-cm-dev/plantillas-github-actions.git
cd plantillas-github-actions
python scripts/validate_workflows.py
python -m unittest discover -s tests -v
```

## Ejemplo

API .NET con verificación de formato:

```yaml
jobs:
  dotnet:
    uses: angel-cm-dev/plantillas-github-actions/.github/workflows/reusable-dotnet.yml@v1
    with:
      dotnet-version: "8.0.x"
      working-directory: backend
      run-format-check: true
```

Salida del validador:

```text
$ python scripts/validate_workflows.py

10 archivos revisados, 0 error(es).
```

Si un consumidor envía un input inexistente u olvida uno requerido:

```text
ERROR  caller.yml: job 'call': input 'otro' no existe en reusable-x.yml
ERROR  caller.yml: job 'call': falta el input requerido 'token-name'
```

## Estructura del proyecto

```text
plantillas-github-actions/
├── .github/
│   ├── workflows/
│   │   ├── reusable-dotnet.yml
│   │   ├── reusable-node.yml
│   │   ├── reusable-python.yml
│   │   ├── reusable-docker-ghcr.yml
│   │   ├── ejemplo-consumidor.yml   # usa los 4 reutilizables
│   │   └── ci.yml                   # validador + actionlint + yamllint
│   ├── ISSUE_TEMPLATE/              # bug, mejora, config
│   ├── pull_request_template.md
│   └── dependabot.yml
├── examples/
│   ├── node-app/      # API HTTP + node:test + Dockerfile
│   ├── python-app/    # cálculo de IGV + pytest + ruff
│   └── dotnet-app/    # validador de RUC + xUnit
├── scripts/
│   ├── yamlmini.py              # parser YAML (subconjunto) en stdlib
│   └── validate_workflows.py    # reglas estructurales
└── tests/                       # unittest del parser y del validador
```

## Pruebas / validación

```bash
python scripts/validate_workflows.py         # reglas estructurales
python -m unittest discover -s tests -v      # 28 pruebas
```

En CI también se ejecutan **actionlint** (análisis semántico de expresiones y sintaxis de Actions) y **yamllint**. El workflow `ejemplo-consumidor.yml` ejecuta de verdad los cuatro reutilizables contra las apps de `examples/`.

> El parser `yamlmini` cubre el subconjunto de YAML usado por GitHub Actions (sin anclas ni multi-documento); para validación semántica completa se apoya en actionlint en CI.

## Roadmap

- [ ] Workflow reutilizable de release con changelog automático (release-please).
- [ ] Escaneo de seguridad (CodeQL / Trivy) como workflow reutilizable.
- [ ] Publicar tags `v1` semánticos y fijar acciones por SHA.

## Licencia y autor

Distribuido bajo licencia [MIT](LICENSE).

Hecho por **Angel Castañeda Meza** — Ingeniero de Sistemas, Lima, Perú · [github.com/angel-cm-dev](https://github.com/angel-cm-dev)
