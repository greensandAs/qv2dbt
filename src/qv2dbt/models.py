"""In-memory representation of a parsed QlikView load script.

These dataclasses form the intermediate representation (IR) that the parser
produces and the generators consume. Keeping the IR decoupled from both the
QlikView syntax and the Snowflake/dbt output makes the accelerator extensible:
new source dialects only need a new parser, new targets only need a new
generator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LoadKind(str, Enum):
    """Where a table's rows originate."""

    QVD = "qvd"          # LOAD ... FROM x.qvd (QVD)
    FILE = "file"        # LOAD ... FROM x.csv / .txt / .xlsx
    SQL = "sql"          # SQL SELECT ... (pass-through to a source DB)
    RESIDENT = "resident"  # LOAD ... RESIDENT AnotherTable
    INLINE = "inline"    # LOAD ... INLINE [ ... ]
    MAPPING = "mapping"  # MAPPING LOAD used by ApplyMap
    AUTOGEN = "autogen"  # AUTOGENERATE / unknown source


class JoinKind(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    INNER = "inner"
    OUTER = "outer"
    CONCATENATE = "concatenate"
    KEEP = "keep"


@dataclass
class QvField:
    """A single output field of a LOAD statement."""

    # Raw right-hand-side expression exactly as written in QlikView.
    source_expr: str
    # Output/alias name (the `as X` target, or the bare field name).
    alias: str
    # Snowflake SQL for source_expr, filled in by the expression translator.
    sf_expr: Optional[str] = None
    # Constructs the translator could not confidently convert.
    warnings: list[str] = field(default_factory=list)
    # True when the field is a straight column passthrough (no transformation).
    is_passthrough: bool = False


@dataclass
class QvJoin:
    """A JOIN / KEEP / CONCATENATE applied to the *preceding* table."""

    kind: JoinKind
    # The table the join pulls data from (the LOAD that follows the JOIN kw).
    right_table: str
    # Explicit key fields when QlikView specifies them; otherwise implicit
    # (QlikView auto-joins on identically named fields).
    on_fields: list[str] = field(default_factory=list)
    implicit_keys: bool = True


@dataclass
class QvTable:
    """A logical table built by one or more LOAD statements."""

    name: str
    kind: LoadKind
    fields: list[QvField] = field(default_factory=list)
    # Source locator: qvd/file path, resident table name, or sql text.
    source: Optional[str] = None
    # WHERE clause (raw QlikView), later translated.
    where_raw: Optional[str] = None
    where_sf: Optional[str] = None
    group_by: list[str] = field(default_factory=list)
    distinct: bool = False
    joins: list[QvJoin] = field(default_factory=list)
    # Order in which the table appeared in the script (drives dbt ref order).
    order: int = 0
    # Constructs attached to the whole table the translator flagged.
    warnings: list[str] = field(default_factory=list)
    # dbt layer this table maps to: staging / intermediate / mart.
    layer: str = "intermediate"
    # Original raw statement text, retained for the audit report.
    raw: str = ""


@dataclass
class QvMap:
    """A MAPPING LOAD table used by ApplyMap()."""

    name: str
    source: Optional[str] = None
    key_expr: str = ""
    value_expr: str = ""
    raw: str = ""


@dataclass
class QvVariable:
    name: str
    value: str
    is_let: bool = False  # LET evaluates the RHS, SET stores it literally.


@dataclass
class QvSource:
    """An external source referenced by the script (QVD, file or DB table)."""

    identifier: str      # logical name used for dbt sources.yml
    kind: LoadKind
    locator: str         # path or table name
    fields: list[str] = field(default_factory=list)


@dataclass
class QvControlBlock:
    """A script control-flow construct (SUB/FOR/IF/DO/SWITCH/CALL)."""

    kind: str            # sub | for | if | do | switch | call | exit
    header: str          # opening line
    body: str            # full raw text of the block
    start_line: int
    end_line: int
    guidance: str = ""   # suggested conversion approach


@dataclass
class QvScript:
    """Root IR object for a whole parsed .qvs script."""

    name: str
    tables: list[QvTable] = field(default_factory=list)
    maps: list[QvMap] = field(default_factory=list)
    variables: list[QvVariable] = field(default_factory=list)
    sources: list[QvSource] = field(default_factory=list)
    control_blocks: list[QvControlBlock] = field(default_factory=list)
    # Statements the parser recognised but does not translate (STORE, DROP,
    # RENAME, control flow). Retained for the migration report.
    unsupported: list[dict] = field(default_factory=list)
    dropped_tables: list[str] = field(default_factory=list)

    def table_by_name(self, name: str) -> Optional[QvTable]:
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None
