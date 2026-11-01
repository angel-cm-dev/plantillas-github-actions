import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from yamlmini import YamlError, loads  # noqa: E402


class YamlMiniTests(unittest.TestCase):
    def test_mapas_anidados_y_escalares(self):
        data = loads(
            """
name: CI   # comentario
on:
  push:
    branches: [main, "release/*"]
count: 3
ratio: 0.5
enabled: true
nothing: ~
"""
        )
        self.assertEqual(data["name"], "CI")
        self.assertEqual(data["on"], {"push": {"branches": ["main", "release/*"]}})
        self.assertEqual((data["count"], data["ratio"], data["enabled"], data["nothing"]), (3, 0.5, True, None))

    def test_on_es_texto_como_en_github(self):
        self.assertIn("on", loads("on: push\n"))
        self.assertEqual(loads("x: on\n"), {"x": "on"})

    def test_lista_de_mapas(self):
        data = loads(
            """
steps:
  - name: Checkout
    uses: actions/checkout@v4
  - run: echo hola
  -
    name: anidado
"""
        )
        self.assertEqual(
            data["steps"],
            [{"name": "Checkout", "uses": "actions/checkout@v4"}, {"run": "echo hola"}, {"name": "anidado"}],
        )

    def test_lista_al_mismo_nivel_que_la_clave(self):
        self.assertEqual(loads("items:\n- a\n- b\nfin: 1\n"), {"items": ["a", "b"], "fin": 1})

    def test_bloque_literal_conserva_lineas_y_almohadillas(self):
        data = loads('run: |\n  echo "### Título"\n\n  echo fin\nnext: 1\n')
        self.assertEqual(data["run"], 'echo "### Título"\n\necho fin\n')
        self.assertEqual(data["next"], 1)

    def test_bloque_plegado_y_strip(self):
        self.assertEqual(loads("a: >-\n  uno\n  dos\n")["a"], "uno dos")

    def test_comillas(self):
        data = loads("""a: 'it''s'\nb: "x: y # no es comentario"\nc: '["20", "22"]'\n""")
        self.assertEqual(data, {"a": "it's", "b": "x: y # no es comentario", "c": '["20", "22"]'})

    def test_expresiones_de_actions(self):
        data = loads("key: nuget-${{ hashFiles('**/*.csproj', 'x') }}\nif: ${{ a == 'b' }}\n")
        self.assertEqual(data["key"], "nuget-${{ hashFiles('**/*.csproj', 'x') }}")
        self.assertEqual(data["if"], "${{ a == 'b' }}")

    def test_mapa_en_linea(self):
        self.assertEqual(loads("p: { contents: read, packages: write }\n"), {"p": {"contents": "read", "packages": "write"}})

    def test_url_no_se_confunde_con_clave(self):
        self.assertEqual(loads("- https://example.com/a\n"), ["https://example.com/a"])

    def test_errores(self):
        with self.assertRaises(YamlError):
            loads("a: 1\na: 2\n")
        with self.assertRaises(YamlError):
            loads("a:\n\tb: 1\n")
        with self.assertRaises(YamlError):
            loads("a: 'sin cerrar\n")
        with self.assertRaises(YamlError):
            loads("a: 1\n  b: 2\n")
        with self.assertRaises(YamlError):
            loads("a: &ancla 1\n")

    def test_documento_vacio(self):
        self.assertIsNone(loads("# solo comentarios\n"))


if __name__ == "__main__":
    unittest.main()
