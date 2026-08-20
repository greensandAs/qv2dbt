"""Stage 3: translate QlikView expressions to Snowflake SQL.

The translator is a small recursive-descent pass over function calls. It is
intentionally conservative: anything it cannot map with confidence is emitted
verbatim, wrapped so a reviewer can find it, and reported as a warning. This
"fail loud, never silently wrong" behaviour is what makes the generated dbt
models safe to hand to an engineer for sign-off.
"""
from __future__ import annotations

import re

from .parser import split_top_level


_IDENT_PAREN = re.compile(r"([A-Za-z_][\w#$]*)\s*\(")
_BRACKET = re.compile(r"\[([^\]]+)\]")


class ExpressionTranslator:
    def __init__(self, config: dict):
        self.functions = {k.lower(): v for k, v in
                          (config.get("functions") or {}).items()}
        self.operators = config.get("operators") or {}
        self.manual = {f.lower() for f in
                       (config.get("manual_review_functions") or [])}

    # -- public ---------------------------------------------------------------

    def translate(self, expr: str) -> tuple[str, list[str]]:
        """Return (snowflake_sql, warnings)."""
        if expr is None or expr.strip() == "":
            return "", []
        warnings: list[str] = []
        s = self._bracket_to_quoted(expr)
        s = self._normalize_operators(s)
        result = self._resolve(s, warnings)
        return result.strip(), warnings

    # -- helpers --------------------------------------------------------------

    def _bracket_to_quoted(self, s: str) -> str:
        # [Order Date] -> "Order Date"  (Snowflake quoted identifier)
        def repl(m: re.Match) -> str:
            name = m.group(1).strip()
            if re.fullmatch(r"\w+", name):
                return name
            return '"' + name + '"'
        return _BRACKET.sub(repl, s)

    def _normalize_operators(self, s: str) -> str:
        # Replace '&' string-concat with '||', skipping quoted regions.
        out: list[str] = []
        quote: str | None = None
        for ch in s:
            if quote:
                out.append(ch)
                if ch == quote:
                    quote = None
                continue
            if ch in ("'", '"'):
                quote = ch
                out.append(ch)
            elif ch == "&":
                out.append(" || ")
            else:
                out.append(ch)
        text = "".join(out)
        # literal token replacements (true(), false(), null(), ...)
        for src, dst in self.operators.items():
            if src == "&":
                continue
            text = re.sub(re.escape(src), dst, text, flags=re.IGNORECASE)
        return text

    def _resolve(self, s: str, warnings: list[str]) -> str:
        out: list[str] = []
        i = 0
        while i < len(s):
            m = _IDENT_PAREN.match(s, i)
            if m:
                name = m.group(1)
                close = self._match_paren(s, m.end() - 1)
                if close == -1:
                    out.append(s[i])
                    i += 1
                    continue
                inner = s[m.end():close]
                args = [self._resolve(a, warnings)
                        for a in split_top_level(inner)]
                out.append(self._apply_function(name, args, warnings))
                i = close + 1
            else:
                out.append(s[i])
                i += 1
        return "".join(out)

    @staticmethod
    def _match_paren(s: str, open_idx: int) -> int:
        depth = 0
        quote: str | None = None
        for j in range(open_idx, len(s)):
            ch = s[j]
            if quote:
                if ch == quote:
                    quote = None
                continue
            if ch in ("'", '"'):
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return j
        return -1

    def _apply_function(self, name: str, args: list[str],
                        warnings: list[str]) -> str:
        key = name.lower()

        # ApplyMap('MapName', keyExpr [, default]) becomes a dbt macro call so
        # the mapping table is resolved as a real LEFT JOIN at compile time.
        if key == "applymap" and args:
            map_name = args[0].strip().strip("'\"")
            key_expr = args[1] if len(args) > 1 else "NULL"
            default = args[2] if len(args) > 2 else "NULL"
            warnings.append(
                f"ApplyMap('{map_name}', ...) converted to apply_map() macro "
                f"- confirm mapping table was generated."
            )
            return (f"{{{{ apply_map('{map_name}', \"{key_expr}\", "
                    f"\"{default}\") }}}}")

        entry = self.functions.get(key)
        # Arity-aware templates: a function may map to a dict keyed by the
        # argument count (with 'default' as a fallback) so e.g. Date(x) and
        # Date(x, fmt) can translate differently instead of dropping args.
        if isinstance(entry, dict):
            template = (entry.get(len(args)) or entry.get(str(len(args)))
                        or entry.get("default") or entry.get("*"))
        else:
            template = entry
        if template is None and entry is not None:
            template = str(entry)
        if template is None:
            # Unknown function: keep verbatim, flag for manual review.
            rebuilt = f"{name}({', '.join(args)})"
            if key in self.manual:
                warnings.append(
                    f"Function '{name}()' requires manual review "
                    f"(no deterministic Snowflake equivalent)."
                )
            else:
                warnings.append(
                    f"Function '{name}()' not in mapping - emitted verbatim; "
                    f"verify Snowflake compatibility."
                )
            return f"/* TODO review */ {rebuilt}"

        if key in self.manual:
            warnings.append(
                f"Function '{name}()' mapped approximately - validate results."
            )

        if "{*}" in template:
            return template.replace("{*}", ", ".join(args))

        # Indexed placeholders. Pad missing trailing args with NULL.
        needed = [int(x) for x in re.findall(r"\{(\d+)\}", template)]
        max_idx = max(needed) if needed else -1
        padded = list(args)
        while len(padded) <= max_idx:
            padded.append("NULL")
            warnings.append(
                f"Function '{name}()' missing argument #{len(padded)} - "
                f"defaulted to NULL."
            )
        if len(args) > max_idx + 1:
            warnings.append(
                f"Function '{name}()' received {len(args)} args but mapping "
                f"uses {max_idx + 1} - extra arguments dropped; review."
            )
        result = template
        for idx in sorted(set(needed), reverse=True):
            result = result.replace("{" + str(idx) + "}", padded[idx])
        return result
