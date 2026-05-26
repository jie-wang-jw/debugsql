// ================================================
// DebugSQL – Mock Execution Service  (Phase 5)
//
// Simulates an async SQL execution pipeline:
//   intent detection → SQL generation → fake results + metrics
//
// TODO: Replace runMockExecution with a real backend call:
//   POST /api/execute  { sql, sessionId }
//   → { columns, rows, metrics, planId }
// TODO: Support live execution streaming (Server-Sent Events / WebSocket)
// TODO: Validate SQL against backend schema before sending
// TODO: Propagate real database errors to the ExecutionContext
// ================================================

import type {
  ExecutionColumn,
  ExecutionRow,
  ExecutionMetrics,
  ExecutionResult,
} from '../../types/execution.types';

// ---------------------------------------------------------------------------
// Timing helpers
// ---------------------------------------------------------------------------

const PLANNING_MIN =  80;
const PLANNING_MAX = 320;
const EXEC_MIN     = 900;
const EXEC_MAX     = 2600;

function rand(min: number, max: number): number {
  return Math.round(min + Math.random() * (max - min));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Intent detection (mirrors mockChatService for consistency)
// ---------------------------------------------------------------------------

type QueryIntent = 'aggregate' | 'join' | 'filter' | 'sort' | 'default';

function detectIntent(message: string): QueryIntent {
  const m = message.toLowerCase();
  if (['total', 'sum', 'count', 'average', 'avg', 'group', 'per', 'revenue', 'sales'].some((k) => m.includes(k)))
    return 'aggregate';
  if (['join', 'related', 'users and', 'customers and', 'together', 'combined'].some((k) => m.includes(k)))
    return 'join';
  if (['top', 'rank', 'best', 'highest', 'lowest', 'sorted', 'most', 'limit'].some((k) => m.includes(k)))
    return 'sort';
  if (['where', 'filter', 'only', 'between', 'recent', 'last', 'days', 'months'].some((k) => m.includes(k)))
    return 'filter';
  return 'default';
}

// ---------------------------------------------------------------------------
// SQL templates  (one per intent)
// ---------------------------------------------------------------------------

const SQL_AGGREGATE = `SELECT
  t.store_id,
  s.name         AS store_name,
  s.state,
  SUM(t.amount)  AS total_sales,
  COUNT(t.id)    AS transaction_count
FROM transactions t
JOIN stores s ON s.id = t.store_id
WHERE t.state = 'TX'
  AND t.completed_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY t.store_id, s.name, s.state
ORDER BY total_sales DESC;`;

const SQL_JOIN = `SELECT
  u.id,
  u.name,
  u.email,
  COUNT(o.id)   AS order_count,
  SUM(o.total)  AS lifetime_value
FROM users u
INNER JOIN orders o ON o.user_id = u.id
WHERE u.active = TRUE
GROUP BY u.id, u.name, u.email
HAVING COUNT(o.id) > 0
ORDER BY lifetime_value DESC
LIMIT 20;`;

const SQL_FILTER = `SELECT
  p.id,
  p.name,
  p.category,
  p.price,
  p.stock_quantity
FROM products p
WHERE p.category = 'electronics'
  AND p.price BETWEEN 50 AND 500
  AND p.stock_quantity > 0
ORDER BY p.price ASC;`;

const SQL_SORT = `SELECT
  p.name,
  p.category,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM products p
JOIN order_items oi ON oi.product_id = p.id
GROUP BY p.id, p.name, p.category
ORDER BY revenue DESC
LIMIT 10;`;

const SQL_DEFAULT = `SELECT
  t.store_id,
  s.name        AS store_name,
  SUM(t.amount) AS total_sales
FROM transactions t
JOIN stores s ON s.id = t.store_id
WHERE t.completed_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY t.store_id, s.name
ORDER BY total_sales DESC;`;

// ---------------------------------------------------------------------------
// Fake result datasets (columns + rows)
// ---------------------------------------------------------------------------

interface MockDataset {
  columns: ExecutionColumn[];
  rows:    ExecutionRow[];
}

const DATA_AGGREGATE: MockDataset = {
  columns: [
    { key: 'store_id',          label: 'store_id'          },
    { key: 'store_name',        label: 'store_name'        },
    { key: 'state',             label: 'state'             },
    { key: 'total_sales',       label: 'total_sales'       },
    { key: 'transaction_count', label: 'transaction_count' },
  ],
  rows: [
    { store_id: 'STX-01', store_name: 'Austin TX Store',      state: 'TX', total_sales: 142580.00, transaction_count: 2341 },
    { store_id: 'STX-02', store_name: 'Dallas TX Store',      state: 'TX', total_sales: 127340.50, transaction_count: 1982 },
    { store_id: 'STX-03', store_name: 'Houston TX Store',     state: 'TX', total_sales: 113220.75, transaction_count: 1756 },
    { store_id: 'STX-04', store_name: 'San Antonio TX Store', state: 'TX', total_sales:  98450.00, transaction_count: 1543 },
    { store_id: 'STX-05', store_name: 'Plano TX Store',       state: 'TX', total_sales:  84930.25, transaction_count: 1322 },
    { store_id: 'STX-06', store_name: 'El Paso TX Store',     state: 'TX', total_sales:  71280.00, transaction_count: 1108 },
    { store_id: 'STX-07', store_name: 'Arlington TX Store',   state: 'TX', total_sales:  65820.50, transaction_count:  980 },
    { store_id: 'STX-08', store_name: 'Fort Worth TX Store',  state: 'TX', total_sales:  59140.00, transaction_count:  876 },
  ],
};

const DATA_JOIN: MockDataset = {
  columns: [
    { key: 'id',             label: 'id'             },
    { key: 'name',           label: 'name'           },
    { key: 'email',          label: 'email'          },
    { key: 'order_count',    label: 'order_count'    },
    { key: 'lifetime_value', label: 'lifetime_value' },
  ],
  rows: [
    { id: 1,  name: 'Sarah Chen',      email: 'sarah.chen@example.com',      order_count: 31, lifetime_value: 7240.50 },
    { id: 2,  name: 'James Rivera',    email: 'james.r@example.com',         order_count: 28, lifetime_value: 6820.00 },
    { id: 3,  name: 'Priya Nair',      email: 'priya.nair@example.com',      order_count: 24, lifetime_value: 5530.75 },
    { id: 4,  name: 'Marcus Webb',     email: 'mwebb@example.com',           order_count: 22, lifetime_value: 4980.25 },
    { id: 5,  name: 'Lena Hoffmann',   email: 'lena.h@example.com',          order_count: 19, lifetime_value: 4120.00 },
    { id: 6,  name: 'Daniel Park',     email: 'dpark@example.com',           order_count: 17, lifetime_value: 3760.50 },
    { id: 7,  name: 'Amara Okonkwo',   email: 'amara.ok@example.com',        order_count: 14, lifetime_value: 3210.00 },
    { id: 8,  name: 'Ethan Moore',     email: 'ethan.moore@example.com',     order_count: 12, lifetime_value: 2840.75 },
    { id: 9,  name: 'Sofia Petrov',    email: 'sofia.petrov@example.com',    order_count: 10, lifetime_value: 2340.00 },
    { id: 10, name: 'Lucas Andrade',   email: 'l.andrade@example.com',       order_count:  8, lifetime_value: 1820.50 },
  ],
};

const DATA_FILTER: MockDataset = {
  columns: [
    { key: 'id',             label: 'id'             },
    { key: 'name',           label: 'name'           },
    { key: 'category',       label: 'category'       },
    { key: 'price',          label: 'price'          },
    { key: 'stock_quantity', label: 'stock_quantity' },
  ],
  rows: [
    { id: 1,  name: 'USB-C Hub Pro',         category: 'electronics', price:  59.99, stock_quantity: 214 },
    { id: 2,  name: 'Mechanical Keyboard',   category: 'electronics', price:  79.99, stock_quantity:  87 },
    { id: 3,  name: 'Wireless Mouse X3',     category: 'electronics', price:  49.99, stock_quantity: 153 },
    { id: 4,  name: 'LED Desk Lamp',         category: 'electronics', price:  64.99, stock_quantity:  62 },
    { id: 5,  name: 'HDMI 2.1 Cable 3m',    category: 'electronics', price:  18.99, stock_quantity: 340 },
    { id: 6,  name: 'Webcam HD 1080p',       category: 'electronics', price: 129.99, stock_quantity:  45 },
    { id: 7,  name: 'Noise-Cancel Headset',  category: 'electronics', price: 199.99, stock_quantity:  38 },
    { id: 8,  name: 'SSD 1TB NVMe',          category: 'electronics', price: 179.99, stock_quantity:  71 },
    { id: 9,  name: 'Portable Charger 20K',  category: 'electronics', price:  89.99, stock_quantity:  96 },
    { id: 10, name: 'Smart Plug (4-pack)',    category: 'electronics', price:  34.99, stock_quantity: 188 },
    { id: 11, name: 'Ring Light 18"',        category: 'electronics', price:  74.99, stock_quantity:  55 },
    { id: 12, name: 'USB Microphone',        category: 'electronics', price: 119.99, stock_quantity:  42 },
  ],
};

const DATA_SORT: MockDataset = {
  columns: [
    { key: 'name',     label: 'name'     },
    { key: 'category', label: 'category' },
    { key: 'revenue',  label: 'revenue'  },
  ],
  rows: [
    { name: 'MacBook Pro 16"',        category: 'laptops',    revenue: 284920.00 },
    { name: 'iPhone 15 Pro Max',      category: 'phones',     revenue: 231480.50 },
    { name: 'AirPods Pro 2nd Gen',    category: 'audio',      revenue: 187360.00 },
    { name: 'iPad Pro 12.9"',         category: 'tablets',    revenue: 162840.75 },
    { name: 'Apple Watch Ultra 2',    category: 'wearables',  revenue: 143290.00 },
    { name: 'Dell XPS 15',            category: 'laptops',    revenue: 128450.25 },
    { name: 'Samsung Galaxy S24+',    category: 'phones',     revenue: 114820.00 },
    { name: 'Sony WH-1000XM5',        category: 'audio',      revenue:  98340.50 },
    { name: 'LG UltraWide 34"',       category: 'monitors',   revenue:  87920.00 },
    { name: 'Logitech MX Master 3S',  category: 'peripherals', revenue:  74150.75 },
  ],
};

const DATA_DEFAULT: MockDataset = {
  columns: [
    { key: 'store_id',    label: 'store_id'    },
    { key: 'store_name',  label: 'store_name'  },
    { key: 'total_sales', label: 'total_sales' },
  ],
  rows: [
    { store_id: 'S001', store_name: 'Manhattan Flagship', total_sales: 284920.00 },
    { store_id: 'S002', store_name: 'Brooklyn Heights',   total_sales: 231480.50 },
    { store_id: 'S003', store_name: 'Midtown West',       total_sales: 187360.00 },
    { store_id: 'S004', store_name: 'Upper East Side',    total_sales: 162840.75 },
    { store_id: 'S005', store_name: 'Hoboken NJ',         total_sales: 143290.00 },
    { store_id: 'S006', store_name: 'Astoria Queens',     total_sales: 128450.25 },
    { store_id: 'S007', store_name: 'Jersey City',        total_sales: 114820.00 },
    { store_id: 'S008', store_name: 'Bronx Hub',          total_sales:  98340.50 },
  ],
};

// ---------------------------------------------------------------------------
// Intent → SQL + data mapping
// ---------------------------------------------------------------------------

interface IntentPayload {
  sql:     string;
  dataset: MockDataset;
  estimatedRows: number;
}

function resolveIntent(intent: QueryIntent): IntentPayload {
  switch (intent) {
    case 'aggregate': return { sql: SQL_AGGREGATE, dataset: DATA_AGGREGATE, estimatedRows: 1200 };
    case 'join':      return { sql: SQL_JOIN,       dataset: DATA_JOIN,      estimatedRows:  420 };
    case 'filter':    return { sql: SQL_FILTER,     dataset: DATA_FILTER,    estimatedRows:  320 };
    case 'sort':      return { sql: SQL_SORT,       dataset: DATA_SORT,      estimatedRows: 2800 };
    default:          return { sql: SQL_DEFAULT,    dataset: DATA_DEFAULT,   estimatedRows:  890 };
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Simulates an async query execution run.
 *
 * Resolves with an ExecutionResult after a realistic planning + execution delay.
 *
 * TODO: Replace with a real backend call:
 *   POST /api/execute  body: { sql, sessionId }
 *   GET  /api/execute/:runId/stream  (for live progress)
 * TODO: Add query cancellation support (AbortController)
 * TODO: Connect database connection pooling configuration
 */
export async function runMockExecution(query: string): Promise<ExecutionResult> {
  const intent  = detectIntent(query);
  const payload = resolveIntent(intent);

  const planningTimeMs  = rand(PLANNING_MIN, PLANNING_MAX);
  const executionTimeMs = rand(EXEC_MIN, EXEC_MAX);

  // Simulate network + DB round-trip
  await sleep(planningTimeMs + executionTimeMs);

  const metrics: ExecutionMetrics = {
    planningTimeMs,
    executionTimeMs,
    rowCount:      payload.dataset.rows.length,
    estimatedRows: payload.estimatedRows,
  };

  return {
    sql:     payload.sql,
    columns: payload.dataset.columns,
    rows:    payload.dataset.rows,
    metrics,
  };
}
