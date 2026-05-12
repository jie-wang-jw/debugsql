// ================================================
// DebugSQL – Mock Query Plan Generator
//
// Produces a fully-formed React Flow graph for the
// demo query: "Show total sales in Texas grouped by store"
//
// TODO: Replace mock graph generation with backend query plan API
//       Target: GET /api/query-plan/:planId
//       The response shape should match QueryPlanGraph so this
//       file can be swapped out without touching rendering code.
// ================================================

import { MarkerType } from 'reactflow';
import type {
  QueryPlanGraph,
  FlowNode,
  FlowEdge,
  IntentNodeData,
  OperationNodeData,
  DataNodeData,
} from '../components/query-plan/queryPlan.types';

/** Shared edge style for the execution pipeline. */
const pipelineEdge = {
  type: 'smoothstep',
  animated: true,
  markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(99,102,241,0.75)', width: 16, height: 16 },
  style: { stroke: 'rgba(99,102,241,0.45)', strokeWidth: 1.8 },
};

/** Side-branch edge (data source → JOIN node). */
const branchEdge = {
  type: 'smoothstep',
  animated: true,
  markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(16,185,129,0.75)', width: 14, height: 14 },
  style: { stroke: 'rgba(16,185,129,0.4)', strokeWidth: 1.5 },
};

/**
 * Generates the demo query plan graph.
 *
 * Graph layout (top-down pipeline with side-branches at JOIN):
 *
 *    [IntentNode]
 *         ↓
 *    [FILTER: state='TX']
 *         ↓
 * [sales] → [HASH JOIN] ← [stores]
 *         ↓
 *    [GROUP BY: store_id]
 *         ↓
 *    [AGGREGATE: SUM(amount)]
 *         ↓
 *    [SORT: total_sales DESC]
 *         ↓
 *    [DataNode: Result]
 *
 * TODO: Sync graph with assistant-generated query plans
 * TODO: Enable real query execution pipeline visualization
 */
export function generateDemoQueryPlan(): QueryPlanGraph {
  // ----- Nodes -----

  const intentData: IntentNodeData = {
    kind: 'intent',
    intentLabel: 'Aggregation Query',
    aggregation: 'SUM(amount)',
    filters: ["state = 'TX'"],
    groupBy: ['store_id'],
    targetColumns: ['amount', 'store_id', 'store_name'],
  };

  const filterData: OperationNodeData = {
    kind: 'operation',
    operationType: 'FILTER',
    label: 'Filter',
    detail: "state = 'TX'",
    estimatedRows: 18_400,
    cost: 12.40,
    executionState: 'done',
  };

  const joinData: OperationNodeData = {
    kind: 'operation',
    operationType: 'JOIN',
    label: 'Hash Join',
    detail: 'sales.store_id = stores.id',
    estimatedRows: 18_400,
    cost: 45.20,
    executionState: 'done',
  };

  const salesData: DataNodeData = {
    kind: 'data',
    tableName: 'sales_transactions',
    nodeRole: 'source',
    rowCount: 284_000,
    estimatedCost: 18.90,
    columns: ['id', 'store_id', 'amount', 'state', 'created_at'],
  };

  const storesData: DataNodeData = {
    kind: 'data',
    tableName: 'stores',
    nodeRole: 'source',
    rowCount: 420,
    estimatedCost: 2.80,
    columns: ['id', 'name', 'region', 'state'],
  };

  const groupByData: OperationNodeData = {
    kind: 'operation',
    operationType: 'GROUP_BY',
    label: 'Group By',
    detail: 'store_id, store_name',
    estimatedRows: 28,
    cost: 52.10,
    executionState: 'done',
  };

  const aggregateData: OperationNodeData = {
    kind: 'operation',
    operationType: 'AGGREGATE',
    label: 'Aggregate',
    detail: 'SUM(amount) AS total_sales',
    estimatedRows: 28,
    cost: 62.80,
    executionState: 'running',
  };

  const sortData: OperationNodeData = {
    kind: 'operation',
    operationType: 'SORT',
    label: 'Sort',
    detail: 'total_sales DESC',
    estimatedRows: 28,
    cost: 63.10,
    executionState: 'pending',
  };

  const resultData: DataNodeData = {
    kind: 'data',
    tableName: 'Result',
    nodeRole: 'result',
    rowCount: 28,
    columns: ['store_id', 'store_name', 'total_sales'],
  };

  const nodes: FlowNode[] = [
    { id: 'intent',       type: 'intent',    position: { x: 185, y: 0   }, data: intentData    },
    { id: 'filter',       type: 'operation', position: { x: 190, y: 130 }, data: filterData    },
    { id: 'data-sales',   type: 'data',      position: { x: -45, y: 280 }, data: salesData     },
    { id: 'join',         type: 'operation', position: { x: 190, y: 280 }, data: joinData      },
    { id: 'data-stores',  type: 'data',      position: { x: 450, y: 280 }, data: storesData    },
    { id: 'groupby',      type: 'operation', position: { x: 190, y: 430 }, data: groupByData   },
    { id: 'aggregate',    type: 'operation', position: { x: 190, y: 560 }, data: aggregateData },
    { id: 'sort',         type: 'operation', position: { x: 190, y: 685 }, data: sortData      },
    { id: 'result',       type: 'data',      position: { x: 190, y: 810 }, data: resultData    },
  ];

  // ----- Edges -----

  const edges: FlowEdge[] = [
    // Main pipeline (top-down)
    { id: 'e-intent-filter',    source: 'intent',    target: 'filter',    ...pipelineEdge },
    { id: 'e-filter-join',      source: 'filter',    target: 'join',      targetHandle: 'top', ...pipelineEdge },
    { id: 'e-join-groupby',     source: 'join',      target: 'groupby',   ...pipelineEdge },
    { id: 'e-groupby-aggregate',source: 'groupby',   target: 'aggregate', ...pipelineEdge },
    { id: 'e-aggregate-sort',   source: 'aggregate', target: 'sort',      ...pipelineEdge },
    { id: 'e-sort-result',      source: 'sort',      target: 'result',    ...pipelineEdge },

    // Data source branches → JOIN (side connections)
    {
      id: 'e-sales-join',
      source: 'data-sales', sourceHandle: 'right',
      target: 'join',       targetHandle: 'left',
      ...branchEdge,
    },
    {
      id: 'e-stores-join',
      source: 'data-stores', sourceHandle: 'left',
      target: 'join',        targetHandle: 'right',
      ...branchEdge,
    },
  ];

  return {
    nodes,
    edges,
    queryLabel: 'Show total sales in Texas grouped by store',
    totalCost: 63.10,
  };
}
