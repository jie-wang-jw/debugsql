from app.semantic_sql.operators import contains_semantic_operators
from app.semantic_sql.resolver import KeywordMediaResolver
from app.semantic_sql.rewriter import rewrite_semantic_sql
from app.semantic_sql.schemas import RewriteResult, SemanticSQLError

UNSUPPORTED_MESSAGE = (
    "This benchmark does not support AI semantic predicates (NL_FILTER / NL_JOIN). "
    "Select a benchmark with the ai_fuzzy_match capability, such as the Multimodal Demo."
)

__all__ = [
    "contains_semantic_operators",
    "KeywordMediaResolver",
    "rewrite_semantic_sql",
    "RewriteResult",
    "SemanticSQLError",
    "UNSUPPORTED_MESSAGE",
]
