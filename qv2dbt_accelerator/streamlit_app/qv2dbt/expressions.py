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
        result = self._cleanup_null_patterns(result)
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

    @staticmethod
    def _cleanup_null_patterns(s: str) -> str:
        """Collapse QlikView IsNull(x)=True() artifacts into valid Snowflake SQL."""
        s = re.sub(r'\bIS\s+NULL\s*=\s*TRUE\b', 'IS NULL', s, flags=re.IGNORECASE)
        s = re.sub(r'\bIS\s+NULL\s*=\s*FALSE\b', 'IS NOT NULL', s, flags=re.IGNORECASE)
        return s

    def _resolve(self, s: str, warnings: list[str]) -> str:
        out: list[str] = []
        i = 0
        while i < len(s):
            # Skip over quoted identifiers ("...") and string literals ('...')
            # so their contents are never mistaken for function calls.
            if s[i] == '"':
                end = s.find('"', i + 1)
                if end == -1:
                    out.append(s[i:])
                    break
                out.append(s[i:end + 1])
                i = end + 1
                continue
            if s[i] == "'":
                end = s.find("'", i + 1)
                if end == -1:
                    out.append(s[i:])
                    break
                out.append(s[i:end + 1])
                i = end + 1
                continue
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

        # Previous(expr) -> LAG(expr) OVER (ORDER BY <inferred>)
        if key == "previous" and args:
            expr = args[0]
            warnings.append(
                "Previous() converted to LAG() - VALIDATE the ORDER BY clause. "
                "QlikView uses load order which may not match any explicit column."
            )
            return f"LAG({expr}) OVER (ORDER BY 1 /* TODO: specify order key */)"

        # Peek(field [, offset [, table]]) -> LAG/LEAD
        if key == "peek" and args:
            field_ref = args[0].strip().strip("'\"")
            offset = args[1].strip() if len(args) > 1 else "1"
            table_ref = args[2].strip().strip("'\"") if len(args) > 2 else ""
            # Negative offset = future rows (LEAD), positive = past rows (LAG)
            try:
                n = int(offset)
                if n < 0:
                    fn = f"LEAD({field_ref}, {abs(n)})"
                else:
                    fn = f"LAG({field_ref}, {n})"
            except ValueError:
                fn = f"LAG({field_ref}, {offset})"
            warnings.append(
                f"Peek() converted to {fn.split('(')[0]}() - VALIDATE ORDER BY. "
                f"QlikView Peek references row position in load order."
            )
            return f"{fn} OVER (ORDER BY 1 /* TODO: specify order key */)"

        # Aggr(aggregate_expr, dim1, dim2, ...) -> window function
        if key == "aggr" and len(args) >= 2:
            agg_expr = args[0]
            dims = args[1:]
            # Check for set analysis (curly braces) which can't be translated
            if "{" in agg_expr or "<" in agg_expr:
                warnings.append(
                    "Aggr() with set analysis detected - cannot auto-translate. "
                    "Manual conversion to a filtered subquery/CTE required."
                )
                return f"/* TODO: Aggr with set analysis */ {name}({', '.join(args)})"
            partition = ", ".join(dims)
            warnings.append(
                "Aggr() converted to window function - verify PARTITION BY columns."
            )
            return f"{agg_expr} OVER (PARTITION BY {partition})"

        # Pick(n, val1, val2, ...) -> CASE n WHEN 1 THEN val1 WHEN 2 THEN val2...
        if key == "pick" and len(args) >= 2:
            index_expr = args[0]
            values = args[1:]
            cases = " ".join(
                f"WHEN {i+1} THEN {v}" for i, v in enumerate(values)
            )
            return f"CASE {index_expr} {cases} END"

        # Match(expr, val1, val2, ...) -> CASE WHEN expr=val1 THEN 1 WHEN...
        if key in ("match", "mixmatch") and len(args) >= 2:
            expr = args[0]
            values = args[1:]
            cases = " ".join(
                f"WHEN {expr} = {v} THEN {i+1}" for i, v in enumerate(values)
            )
            ci = " /* case-insensitive */" if key == "mixmatch" else ""
            return f"CASE{ci} {cases} ELSE 0 END"

        # WildMatch(expr, pattern1, pattern2, ...) -> CASE WHEN LIKE
        if key == "wildmatch" and len(args) >= 2:
            expr = args[0]
            patterns = args[1:]
            cases = " ".join(
                f"WHEN {expr} LIKE {p} THEN {i+1}" for i, p in enumerate(patterns)
            )
            warnings.append(
                "WildMatch() converted to CASE/LIKE - QlikView uses * wildcard "
                "(converted to %) and is case-insensitive; verify patterns."
            )
            return f"CASE {cases} ELSE 0 END"

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

        # Heuristic: if extra args exist and the function expects 2 args
        # (string + length), try merging leading bare-identifier args into a
        # compound field name.  This handles translated scripts where a field
        # like "year/month" became "year , month" during localisation.
        if len(padded) > max_idx + 1 and max_idx >= 1:
            last = padded[-1].strip()
            if re.fullmatch(r"\d+", last):
                field_parts = padded[:-1]
                if all(re.fullmatch(r"[\w\s]+", p.strip()) for p in field_parts):
                    merged_field = ", ".join(p.strip() for p in field_parts)
                    padded = [merged_field, last]
                    warnings.append(
                        f"Function '{name}()' received {len(args)} args but "
                        f"mapping uses {max_idx + 1} - merged leading args as "
                        f"compound field name '{merged_field}'; review."
                    )

        while len(padded) <= max_idx:
            padded.append("NULL")
            warnings.append(
                f"Function '{name}()' missing argument #{len(padded)} - "
                f"defaulted to NULL."
            )
        if len(padded) > max_idx + 1:
            warnings.append(
                f"Function '{name}()' received {len(args)} args but mapping "
                f"uses {max_idx + 1} - extra arguments dropped; review."
            )
        result = template
        for idx in sorted(set(needed), reverse=True):
            result = result.replace("{" + str(idx) + "}", padded[idx])
        return result
