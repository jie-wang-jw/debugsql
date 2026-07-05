from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from app.semantic_sql.schemas import NLFilterOp, SemanticSQLError


SEMANTIC_FUNCTION_NAMES = ("NL_FILTER", "NL_JOIN")

_SEMANTIC_TOKEN = re.compile(r"\b(NL_FILTER|NL_JOIN)\s*\(", re.IGNORECASE)


def contains_semantic_operators(sql: str) -> bool:
    """Cheap detection used for routing and capability gating."""
    return bool(_SEMANTIC_TOKEN.search(sql or ""))


def parse_select(sql: str) -> exp.Select:
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise SemanticSQLError(f"Could not parse semantic SQL: {exc}") from exc
    if not isinstance(tree, exp.Select):
        raise SemanticSQLError("Semantic SQL must be a single SELECT statement.")
    return tree


def extract_nl_filters(
    tree: exp.Select,
    table_columns: dict[str, list[str]],
) -> list[tuple[NLFilterOp, exp.Anonymous]]:
    """Extract NL_FILTER operators from the top-level WHERE clause.

    Returns pairs of (operator model, AST node) so the rewriter can replace
    the nodes in place. Rejects NL_JOIN and misplaced/misformed operators
    with clear messages.
    """
    alias_to_table = _alias_map(tree)
    pairs: list[tuple[NLFilterOp, exp.Anonymous]] = []
    index = 0

    for node in tree.find_all(exp.Anonymous):
        name = (node.name or "").upper()
        if name == "NL_JOIN":
            raise SemanticSQLError(
                "NL_JOIN is planned but not supported yet. Only NL_FILTER is available in this version."
            )
        if name != "NL_FILTER":
            continue

        if node.find_ancestor(exp.Select) is not tree or node.find_ancestor(exp.Where) is None:
            raise SemanticSQLError(
                "NL_FILTER is only supported in the WHERE clause of the top-level SELECT."
            )

        args = node.expressions
        if len(args) != 2 or not isinstance(args[0], exp.Column):
            raise SemanticSQLError(
                "NL_FILTER expects two arguments: NL_FILTER(column, 'natural language condition')."
            )
        predicate_arg = args[1]
        if not (isinstance(predicate_arg, exp.Literal) and predicate_arg.is_string):
            raise SemanticSQLError("The NL_FILTER condition must be a quoted string literal.")

        column_node = args[0]
        table_alias = column_node.table or ""
        table = _resolve_table(column_node.name, table_alias, alias_to_table, table_columns)

        pairs.append(
            (
                NLFilterOp(
                    op_id=f"nlf_{index}",
                    table=table,
                    table_alias=table_alias or table,
                    column=column_node.name,
                    predicate=predicate_arg.this,
                ),
                node,
            )
        )
        index += 1

    return pairs


def _alias_map(tree: exp.Select) -> dict[str, str]:
    return {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}


def _resolve_table(
    column: str,
    table_alias: str,
    alias_to_table: dict[str, str],
    table_columns: dict[str, list[str]],
) -> str:
    if table_alias:
        table = alias_to_table.get(table_alias)
        if not table:
            raise SemanticSQLError(f"Unknown table alias '{table_alias}' in NL_FILTER column.")
        return table
    owners = [name for name, columns in table_columns.items() if column in columns]
    if len(owners) == 1:
        return owners[0]
    raise SemanticSQLError(
        f"Could not resolve which table the NL_FILTER column '{column}' belongs to; "
        "qualify it with a table alias."
    )
