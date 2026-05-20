import { useState } from 'react';
import { motion } from 'framer-motion';
import { FiCpu, FiRefreshCw, FiMaximize2 } from 'react-icons/fi';
import type { QueryNode } from '../../types';
import { FadeIn } from '../animations/FadeIn';
import { StatusBadge } from '../ui/StatusBadge';
import { PlanNode } from './PlanNode';
import './QueryPlanArea.css';

// TODO: Replace with real query plan data from backend (GET /api/query-plan/:id)
const MOCK_NODES: QueryNode[] = [
  {
    id: 'n1',
    type: 'Aggregate',
    estimatedRows: 142,
    totalCost: 98.50,
    startupCost: 87.30,
  },
  {
    id: 'n2',
    type: 'Sort',
    estimatedRows: 1183,
    totalCost: 87.10,
    startupCost: 62.40,
    filter: 'order_count > 5',
  },
  {
    id: 'n3',
    type: 'HashJoin',
    joinType: 'Inner',
    estimatedRows: 1183,
    totalCost: 45.23,
    startupCost: 12.50,
    hashCond: '(o.user_id = u.id)',
  },
  {
    id: 'n4',
    type: 'SeqScan',
    relation: 'users u',
    estimatedRows: 3200,
    totalCost: 12.80,
    startupCost: 0.00,
    filter: 'active = true',
  },
  {
    id: 'n5',
    type: 'IndexScan',
    relation: 'orders o',
    indexName: 'orders_user_id_idx',
    estimatedRows: 28400,
    totalCost: 18.90,
    startupCost: 0.43,
    filter: "created_at >= NOW() - INTERVAL '30 days'",
  },
];

export function QueryPlanArea() {
  // TODO: Lift selectedNodeId to shared state so InspectorPanel can react
  const [selectedId, setSelectedId] = useState<string>('n3');

  return (
    <div className="qplan">
      <QueryPlanHeader />

      <div className="qplan__canvas">
        {/* TODO: Integrate React Flow for interactive graph visualization */}
        <FadeIn direction="up" delay={0.1}>
          <PlanTree
            nodes={MOCK_NODES}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </FadeIn>
      </div>
    </div>
  );
}

/* ---- Header ---- */
function QueryPlanHeader() {
  return (
    <div className="qplan__header">
      <div className="qplan__header-left">
        <div className="qplan__header-icon">
          <FiCpu size={13} />
        </div>
        <div>
          <span className="qplan__title">Query Plan</span>
          <span className="qplan__query-preview">
            SELECT users JOIN orders WHERE …
          </span>
        </div>
      </div>
      <div className="qplan__header-right">
        <StatusBadge label="5 nodes" variant="gray" />
        <StatusBadge label="cost 98.5" variant="orange" />
        <button className="qplan__icon-btn" aria-label="Refresh plan" title="Refresh plan">
          <FiRefreshCw size={12} />
        </button>
        <button className="qplan__icon-btn" aria-label="Expand view" title="Expand view">
          <FiMaximize2 size={12} />
        </button>
      </div>
    </div>
  );
}

/* ---- Tree layout ---- */
interface PlanTreeProps {
  nodes: QueryNode[];
  selectedId: string;
  onSelect: (id: string) => void;
}

function PlanTreeRow({ children }: { children: React.ReactNode }) {
  return <div className="ptree__row">{children}</div>;
}

function Connector({ branches = 1 }: { branches?: number }) {
  return (
    <div className={`ptree__connector ptree__connector--${branches > 1 ? 'fork' : 'straight'}`}>
      {branches > 1 ? (
        <>
          <div className="ptree__connector-left" />
          <div className="ptree__connector-right" />
        </>
      ) : (
        <div className="ptree__connector-line" />
      )}
    </div>
  );
}

function PlanTree({ nodes, selectedId, onSelect }: PlanTreeProps) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

  return (
    <div className="ptree">
      {/* Aggregate */}
      <PlanTreeRow>
        <PlanNode
          node={byId['n1']}
          isSelected={selectedId === 'n1'}
          onClick={onSelect}
        />
      </PlanTreeRow>

      <Connector />

      {/* Sort */}
      <PlanTreeRow>
        <PlanNode
          node={byId['n2']}
          isSelected={selectedId === 'n2'}
          onClick={onSelect}
        />
      </PlanTreeRow>

      <Connector />

      {/* Hash Join */}
      <PlanTreeRow>
        <PlanNode
          node={byId['n3']}
          isSelected={selectedId === 'n3'}
          onClick={onSelect}
        />
      </PlanTreeRow>

      {/* Fork connector */}
      <Connector branches={2} />

      {/* Leaf scans */}
      <PlanTreeRow>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.3 }}
        >
          <PlanNode
            node={byId['n4']}
            isSelected={selectedId === 'n4'}
            onClick={onSelect}
          />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.32, duration: 0.3 }}
        >
          <PlanNode
            node={byId['n5']}
            isSelected={selectedId === 'n5'}
            onClick={onSelect}
          />
        </motion.div>
      </PlanTreeRow>

      <p className="ptree__hint">Click a node to inspect and edit its properties</p>
    </div>
  );
}
