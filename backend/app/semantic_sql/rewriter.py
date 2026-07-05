from __future__ import annotations

from app.semantic_sql.operators import extract_nl_filters, parse_select
from app.semantic_sql.resolver import SemanticResolver
from app.semantic_sql.schemas import (
    NLFilterOp,
    ResolvedMatch,
    ResolvedOperator,
    RewriteResult,
    SemanticSQLError,
)

from sqlglot import exp


def rewrite_semantic_sql(
    sql: str,
    *,
    resolver: SemanticResolver,
    table_columns: dict[str, list[str]],
    semantic_tables: dict[str, str],
) -> RewriteResult:
    """Rewrite SQL containing NL_FILTER into plain executable SQLite SQL.

    Each NL_FILTER becomes an inner join against a VALUES CTE of
    (match_key, score) rows keyed by the semantic table's primary key.
    The result exposes ``asset_id``, ``score``, and ``<op_id>_score`` columns
    so media previews and ranking keep working.
    """
    from app.tools.policy import is_safe_read_query

    tree = parse_select(sql)
    pairs = extract_nl_filters(tree, table_columns)
    if not pairs:
        return RewriteResult(sql=sql, original_sql=sql, explanation="No semantic operators found.")

    resolved: list[ResolvedOperator] = []
    assumptions = [
        "Semantic predicates are resolved with prepared caption/transcript/tag keyword overlap; "
        "an embedding or vision model can replace this resolver later.",
    ]

    for op, node in pairs:
        pk = semantic_tables.get(op.table)
        if pk is None:
            supported = ", ".join(sorted(semantic_tables))
            raise SemanticSQLError(
                f"NL_FILTER on table '{op.table}' is not supported; "
                f"semantic predicates are available for: {supported}."
            )

        matches = resolver.resolve_filter(op)
        if not matches:
            assumptions.append(
                f"No prepared media asset matched the predicate '{op.predicate}' ({op.op_id})."
            )
        resolved.append(
            ResolvedOperator(
                op_id=op.op_id,
                table=op.table,
                column=op.column,
                predicate=op.predicate,
                matches=matches,
            )
        )

        node.replace(exp.true())
        tree = tree.with_(op.op_id, as_=_matches_cte_sql(matches))
        tree = tree.join(
            op.op_id,
            on=f"{op.op_id}.match_key = {op.table_alias}.{pk}",
            join_type="inner",
        )

    tree = _append_score_columns(tree, [op for op, _ in pairs])

    out_sql = tree.sql(dialect="sqlite")
    if not is_safe_read_query(out_sql):
        raise SemanticSQLError("Rewritten SQL failed the read-only safety policy.")

    predicates = "; ".join(f"{op.op_id}: '{op.predicate}' on {op.table}.{op.column}" for op, _ in pairs)
    return RewriteResult(
        sql=out_sql,
        original_sql=sql,
        operators=resolved,
        explanation=(
            f"Rewrote {len(pairs)} NL_FILTER operator(s) ({predicates}) into VALUES CTE joins "
            "keyed by the media table primary key."
        ),
        assumptions=assumptions,
    )


def _matches_cte_sql(matches: list[ResolvedMatch]) -> str:
    if matches:
        values = ", ".join(f"('{_escape(m.key)}', {m.score:.4f})" for m in matches)
    else:
        # Sentinel row that can never join against a real primary key.
        values = "('__no_match__', 0.0)"
    return f"SELECT column1 AS match_key, column2 AS score FROM (VALUES {values})"


def _append_score_columns(tree: exp.Select, ops: list[NLFilterOp]) -> exp.Select:
    existing = {e.alias_or_name for e in tree.expressions}
    additions: list[str] = []
    first = ops[0]
    if "asset_id" not in existing:
        additions.append(f"{first.op_id}.match_key AS asset_id")
    if "score" not in existing:
        additions.append(f"{first.op_id}.score AS score")
    for op in ops:
        alias = f"{op.op_id}_score"
        if alias not in existing:
            additions.append(f"{op.op_id}.score AS {alias}")
    if additions:
        tree = tree.select(*additions, append=True)
    return tree


def _escape(value: str) -> str:
    return value.replace("'", "''")
