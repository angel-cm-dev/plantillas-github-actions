"""Parser YAML mínimo (solo librería estándar) para el subconjunto usado en GitHub Actions.

Soporta: mapas y listas por indentación, listas de mapas (``- key: value``),
escalares planos y entre comillas, secuencias y mapas en línea (``[a, b]``, ``{a: 1}``),
bloques literales/plegados (``|``, ``>``), comentarios y documentos sin anclas.

No pretende cubrir YAML completo (anclas, etiquetas, multi-documento, claves complejas);
ante construcciones no soportadas lanza ``YamlError`` con el número de línea.
Igual que GitHub Actions, ``on``/``yes``/``no`` se interpretan como texto, no como booleanos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["YamlError", "loads", "load_file"]


class YamlError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(f"línea {line}: {message}" if line else message)
        self.line = line


@dataclass
class _Line:
    indent: int
    text: str
    number: int


_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(\d+\.\d*|\.\d+)([eE][-+]?\d+)?$")


def _strip_comment(raw: str) -> str:
    """Quita comentarios ``#`` que no estén dentro de comillas."""
    quote = None
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"') and (i == 0 or raw[i - 1] in " \t[{,:-"):
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i].rstrip()
    return raw.rstrip()


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    parts, depth, quote, current = [], 0, None, []
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _find_mapping_colon(text: str) -> int:
    """Posición del ``:`` que separa clave y valor (fuera de comillas y corchetes), o -1."""
    quote, depth = None, 0
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"') and i == 0:
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(text) or text[i + 1] in " \t"):
            # "${{ x }}" nunca contiene ": " al inicio de un escalar, así que es seguro.
            return i
    return -1


def _parse_scalar(text: str, line: int):
    text = text.strip()
    if text == "":
        return None
    if text[0] == '"':
        if not text.endswith('"') or len(text) < 2:
            raise YamlError("cadena con comillas dobles sin cerrar", line)
        body = text[1:-1]
        return (body.replace("\\\\", "\0").replace('\\"', '"').replace("\\n", "\n")
                .replace("\\t", "\t").replace("\0", "\\"))
    if text[0] == "'":
        if not text.endswith("'") or len(text) < 2:
            raise YamlError("cadena con comillas simples sin cerrar", line)
        return text[1:-1].replace("''", "'")
    if text[0] == "[":
        if not text.endswith("]"):
            raise YamlError("secuencia en línea sin cerrar", line)
        return [_parse_scalar(p, line) for p in _split_top_level(text[1:-1])]
    if text[0] == "{":
        if not text.endswith("}"):
            raise YamlError("mapa en línea sin cerrar", line)
        result = {}
        for part in _split_top_level(text[1:-1]):
            idx = _find_mapping_colon(part)
            if idx < 0:
                raise YamlError(f"entrada inválida en mapa en línea: {part!r}", line)
            result[_parse_key(part[:idx], line)] = _parse_scalar(part[idx + 1:], line)
        return result
    if text[0] in "&*!":
        raise YamlError("anclas, alias y etiquetas no están soportados", line)
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    return text


def _parse_key(text: str, line: int) -> str:
    key = _parse_scalar(text, line)
    if isinstance(key, (list, dict)) or key is None:
        raise YamlError(f"clave inválida: {text!r}", line)
    return str(key) if not isinstance(key, bool) else text.strip()


class _Parser:
    def __init__(self, text: str):
        self.lines: list[_Line] = []
        self.raw = text.replace("\r\n", "\n").split("\n")
        for number, raw in enumerate(self.raw, start=1):
            if "\t" in raw[: len(raw) - len(raw.lstrip())]:
                raise YamlError("tabulación en la indentación", number)
            stripped = _strip_comment(raw)
            if stripped.strip() in ("", "---"):
                continue
            if stripped.strip() == "...":
                break
            indent = len(stripped) - len(stripped.lstrip(" "))
            self.lines.append(_Line(indent, stripped.strip(), number))
        self.pos = 0

    # -- utilidades -----------------------------------------------------
    def _peek(self) -> _Line | None:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def parse(self):
        if not self.lines:
            return None
        value = self._parse_block(self.lines[0].indent)
        if self._peek() is not None:
            ln = self._peek()
            raise YamlError(f"indentación inesperada: {ln.text!r}", ln.number)
        return value

    def _parse_block(self, indent: int):
        line = self._peek()
        if line.text == "-" or line.text.startswith("- "):
            return self._parse_sequence(indent)
        return self._parse_mapping(indent)

    def _parse_sequence(self, indent: int) -> list:
        items = []
        while (line := self._peek()) is not None and line.indent == indent:
            if not (line.text == "-" or line.text.startswith("- ")):
                break
            rest = line.text[1:].lstrip(" ")
            if rest == "":
                self.pos += 1
                nxt = self._peek()
                items.append(self._parse_block(nxt.indent) if nxt and nxt.indent > indent else None)
            elif rest[0] not in "[{" and _find_mapping_colon(rest) >= 0:
                # "- key: value": el mapa empieza en la columna del texto tras el guion
                offset = len(line.text) - len(rest)
                self.lines[self.pos] = _Line(indent + offset, rest, line.number)
                items.append(self._parse_mapping(indent + offset))
            else:
                self.pos += 1
                items.append(self._scalar_or_block(rest, indent, line.number))
        return items

    def _parse_mapping(self, indent: int) -> dict:
        result: dict = {}
        while (line := self._peek()) is not None and line.indent == indent:
            if line.text.startswith("- "):
                raise YamlError("elemento de lista donde se esperaba una clave", line.number)
            idx = _find_mapping_colon(line.text)
            if idx < 0:
                raise YamlError(f"se esperaba 'clave: valor' en {line.text!r}", line.number)
            key = _parse_key(line.text[:idx], line.number)
            if key in result:
                raise YamlError(f"clave duplicada: {key!r}", line.number)
            rest = line.text[idx + 1:].strip()
            self.pos += 1
            if rest == "":
                nxt = self._peek()
                if nxt and nxt.indent > indent:
                    result[key] = self._parse_block(nxt.indent)
                elif nxt and nxt.indent == indent and (nxt.text == "-" or nxt.text.startswith("- ")):
                    result[key] = self._parse_sequence(indent)
                else:
                    result[key] = None
            else:
                result[key] = self._scalar_or_block(rest, indent, line.number)
        if (line := self._peek()) is not None and line.indent > indent:
            raise YamlError(f"indentación inesperada: {line.text!r}", line.number)
        return result

    def _scalar_or_block(self, rest: str, indent: int, number: int):
        if re.fullmatch(r"[|>][-+]?", rest):
            return self._parse_block_scalar(rest, indent, number)
        return _parse_scalar(rest, number)

    def _parse_block_scalar(self, header: str, indent: int, number: int) -> str:
        # Se trabaja sobre las líneas crudas para conservar comentarios y espacios.
        body: list[str] = []
        raw_index = number  # índice 0-based de la línea siguiente
        block_indent = None
        while raw_index < len(self.raw):
            raw = self.raw[raw_index]
            if raw.strip() == "":
                body.append("")
                raw_index += 1
                continue
            current = len(raw) - len(raw.lstrip(" "))
            if current <= indent:
                break
            if block_indent is None:
                block_indent = current
            body.append(raw[block_indent:] if current >= block_indent else raw.strip())
            raw_index += 1
        while self.pos < len(self.lines) and self.lines[self.pos].number <= raw_index:
            self.pos += 1
        while body and body[-1] == "":
            body.pop()
        if header[0] == ">":
            text = " ".join(part for part in body if part)
        else:
            text = "\n".join(body)
        return text if header.endswith("-") else text + "\n"


def loads(text: str):
    """Convierte texto YAML (subconjunto) en estructuras de Python."""
    return _Parser(text).parse()


def load_file(path) -> object:
    with open(path, encoding="utf-8") as fh:
        return loads(fh.read())
