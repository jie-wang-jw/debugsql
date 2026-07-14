from __future__ import annotations

from typing import Any

from app.benchmark_registry import benchmark_questions, get_schema_context
from app.tools.executor import list_tools_for_context
from app.tools.registry import get_connector, normalize_context
from app.tools.schemas import CapabilityExample, CapabilitiesResponse, DatasetContext


def build_capabilities(raw_context: dict | DatasetContext | None) -> CapabilitiesResponse:
    from app.benchmarks.registry import descriptor_for_context

    context = normalize_context(raw_context)
    connector = get_connector(context)
    caps = connector.capabilities()
    schema_preview = connector.introspect_schema(context)
    examples = _build_examples(context, schema_preview)
    policies = {
        "readOnly": caps.readOnly,
        "maxRows": caps.maxRows,
        "maxSampleRows": caps.maxSampleRows,
        "supportedTools": [tool.name for tool in list_tools_for_context(context)],
    }
    descriptor = descriptor_for_context(context.dbType, context.benchmark)
    return CapabilitiesResponse(
        context=context,
        connector=caps,
        tools=list_tools_for_context(context),
        schemaPreview=schema_preview,
        policies=policies,
        examples=examples,
        benchmark=descriptor.model_dump() if descriptor else None,
        capabilityLabels=descriptor.capability_labels() if descriptor else [],
    )


def _build_examples(context: DatasetContext, schema_preview: dict[str, Any]) -> list[CapabilityExample]:
    examples: list[CapabilityExample] = []
    if context.dbType == "sqlite_benchmark" and context.benchmark and context.dbId:
        for index, item in enumerate(benchmark_questions(context.benchmark, context.dbId, limit=5)):
            question = item.get("question") or ""
            query = item.get("query") or ""
            if question:
                examples.append(
                    CapabilityExample(
                        id=f"prompt-{index}",
                        kind="prompt",
                        label=f"Example {index + 1}",
                        content=question,
                    )
                )
            if query:
                examples.append(
                    CapabilityExample(
                        id=f"sql-{index}",
                        kind="sql",
                        label=f"SQL {index + 1}",
                        content=query,
                    )
                )
        tables = schema_preview.get("tables") or []
        if tables:
            first_table = tables[0]["name"]
            examples.append(
                CapabilityExample(
                    id="schema-prompt",
                    kind="prompt",
                    label="Schema overview",
                    content=f"What tables and columns are available in {context.dbId}?",
                )
            )
            examples.append(
                CapabilityExample(
                    id="sample-sql",
                    kind="sql",
                    label="Row count",
                    content=f'SELECT COUNT(*) AS row_count FROM "{first_table}";',
                )
            )
    elif context.dbType == "postgres":
        examples.extend(
            [
                CapabilityExample(
                    id="pg-prompt-1",
                    kind="prompt",
                    label="List tables",
                    content="What tables exist in this PostgreSQL database?",
                ),
                CapabilityExample(
                    id="pg-prompt-2",
                    kind="prompt",
                    label="Describe schema",
                    content="Show me the schema and relationships I can query.",
                ),
            ]
        )
    elif context.dbType == "multimodal_demo":
        for index, item in enumerate(schema_preview.get("exampleQuestions") or []):
            question = item.get("question") if isinstance(item, dict) else None
            if question:
                examples.append(
                    CapabilityExample(
                        id=f"multimodal-prompt-{index}",
                        kind="prompt",
                        label=f"Media example {index + 1}",
                        content=question,
                    )
                )
        examples.append(
            CapabilityExample(
                id="multimodal-sql-1",
                kind="sql",
                label="All prepared media",
                content=(
                    "SELECT e.name, a.media_type, a.caption FROM entities e "
                    "JOIN media_assets a ON a.entity_id = e.id LIMIT 10;"
                ),
            )
        )
        from app.tools.connectors.multimodal_demo import NL_FILTER_EXAMPLE_SQL

        examples.append(
            CapabilityExample(
                id="multimodal-sql-nl-filter",
                kind="sql",
                label="Semantic filter (NL_FILTER)",
                content=NL_FILTER_EXAMPLE_SQL,
            )
        )
    elif context.dbType == "craigslist":
        for index, item in enumerate(schema_preview.get("exampleQuestions") or []):
            question = item.get("question") if isinstance(item, dict) else None
            if question:
                examples.append(
                    CapabilityExample(
                        id=f"craigslist-prompt-{index}",
                        kind="prompt",
                        label=f"Craigslist example {index + 1}",
                        content=question,
                    )
                )
        from app.tools.connectors.craigslist import NL_FILTER_EXAMPLE_SQL

        examples.append(
            CapabilityExample(
                id="craigslist-nl-filter",
                kind="sql",
                label="Semantic image filter",
                content=NL_FILTER_EXAMPLE_SQL,
            )
        )
    return examples
