"""Conservative SQL guard for explorer candidates; not a substitute for read-only DB roles."""
import re

_START = re.compile(r"^\s*SELECT\s", re.I)
_BLOCK = re.compile(r";|--|/\*|\*/|\x00")
_DANGEROUS = re.compile(
    r"\b(?:INTO|FOR\s+(?:UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)|"
    r"PG_SLEEP\s*\(|SLEEP\s*\(|PG_ADVISORY_[A-Z_]+\s*\(|"
    r"DBLINK\s*\(|LO_EXPORT\s*\(|LOAD_FILE\s*\()",
    re.I,
)

def validate_select(sql: str) -> str:
    """Fail closed for a small SELECT-only subset.

    SQL parsing and PostgreSQL privilege enforcement remain necessary.
    This deliberately rejects INTO even if it appears in an innocuous literal.
    """
    if (not isinstance(sql, str) or not 1 <= len(sql) <= 4000
            or not _START.match(sql) or _BLOCK.search(sql)
            or _DANGEROUS.search(sql)):
        raise ValueError("only_single_readonly_select_allowed")
    return sql.strip()
