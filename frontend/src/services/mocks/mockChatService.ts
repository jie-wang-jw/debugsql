// ================================================
// DebugSQL – Mock Chat / AI Service
//
// TODO: Replace every function here with real backend API calls.
// Target endpoint: POST /api/query
// Expected payload: { message: string, sessionId: string }
// Expected response: { sql: string, planId: string, explanation: string }
// ================================================

/** Minimum and maximum simulated response delay (ms). */
const DELAY_MIN = 1100;
const DELAY_MAX = 2200;

// ---------------------------------------------------------------------------
// Response banks – categorised by detected query intent
// ---------------------------------------------------------------------------

const RESPONSES_AGGREGATE = [
  `I've generated a query plan for your aggregation request.

\`\`\`sql
SELECT
  region,
  SUM(sales_amount) AS total_sales,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM transactions
WHERE status = 'completed'
GROUP BY region
ORDER BY total_sales DESC;
\`\`\`

The plan uses an **Aggregate** node on top of a Sequential Scan on \`transactions\`. Estimated total cost: **62.40** · ~8,200 rows. Select the Aggregate node in the plan to inspect and edit it.`,

  `Your query maps to a GROUP BY aggregation.

\`\`\`sql
SELECT
  store_id,
  DATE_TRUNC('month', created_at) AS month,
  SUM(amount) AS revenue
FROM orders
GROUP BY store_id, month
ORDER BY month DESC, revenue DESC;
\`\`\`

I built a plan with **Sort → Aggregate → SeqScan** chain. The planner estimates 3,400 groups at a total cost of **48.75**. No index is used — full scan is optimal here.`,
];

const RESPONSES_JOIN = [
  `Your query requires joining two tables. I've selected a **Hash Join** strategy.

\`\`\`sql
SELECT
  u.id,
  u.name,
  COUNT(o.id) AS order_count,
  SUM(o.total) AS lifetime_value
FROM users u
INNER JOIN orders o ON o.user_id = u.id
WHERE u.active = true
GROUP BY u.id, u.name
HAVING COUNT(o.id) > 0
ORDER BY lifetime_value DESC;
\`\`\`

Plan: **Aggregate → Hash Join → SeqScan(users) + IndexScan(orders)**. Estimated cost: **45.23** · ~1,183 rows. The Hash Join uses \`o.user_id = u.id\` as the hash condition.`,

  `The query joins \`customers\` and \`purchases\`. The planner chose a **Merge Join** after sorting both sides.

\`\`\`sql
SELECT
  c.country,
  p.category,
  COUNT(*) AS purchase_count
FROM customers c
JOIN purchases p ON p.customer_id = c.id
WHERE p.created_at >= NOW() - INTERVAL '90 days'
GROUP BY c.country, p.category;
\`\`\`

Plan cost: **78.90**. Click the Merge Join node to inspect the sort keys and join condition.`,
];

const RESPONSES_FILTER = [
  `I built a filtered query plan for you.

\`\`\`sql
SELECT *
FROM products
WHERE category = 'electronics'
  AND price BETWEEN 50 AND 500
  AND stock_quantity > 0
ORDER BY price ASC;
\`\`\`

The planner applied a **Filter** on \`category\`, \`price\`, and \`stock_quantity\`. An Index Scan on \`products_category_idx\` was selected — estimated cost: **18.40** · ~320 rows.`,

  `Your filter condition selects a subset of rows before joining.

\`\`\`sql
SELECT id, name, email
FROM users
WHERE created_at >= NOW() - INTERVAL '30 days'
  AND country = 'US'
  AND subscription_tier = 'pro';
\`\`\`

Plan uses a **Bitmap Index Scan** on \`users_created_at_idx\` combined with a Bitmap Heap Scan. Estimated rows after filter: **~420**. Total cost: **12.80**.`,
];

const RESPONSES_SORT = [
  `I've created a plan for your ranked/sorted query.

\`\`\`sql
SELECT
  p.name,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM products p
JOIN order_items oi ON oi.product_id = p.id
GROUP BY p.id, p.name
ORDER BY revenue DESC
LIMIT 10;
\`\`\`

The plan includes a **Sort** node (sort key: revenue DESC) on top of a Hash Aggregate. A \`LIMIT\` node caps the output at 10 rows. Total cost: **55.10**.`,
];

const RESPONSES_DEFAULT = [
  `I've analyzed your request and generated an execution plan.

\`\`\`sql
SELECT
  t.store_id,
  s.name AS store_name,
  SUM(t.amount) AS total_sales
FROM transactions t
JOIN stores s ON s.id = t.store_id
WHERE t.completed_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY t.store_id, s.name
ORDER BY total_sales DESC;
\`\`\`

Plan has **5 nodes**: Aggregate → Sort → Hash Join → SeqScan(transactions) + IndexScan(stores). Estimated cost: **67.30** · ~890 rows. Click any node to inspect or edit it.`,

  `Query intent understood. Here's the generated plan:

\`\`\`sql
SELECT
  department,
  AVG(salary) AS avg_salary,
  MAX(salary) AS max_salary,
  COUNT(*) AS headcount
FROM employees
WHERE status = 'active'
GROUP BY department
ORDER BY avg_salary DESC;
\`\`\`

The planner chose Sequential Scan → Aggregate → Sort. Startup cost: **0.00**, total cost: **38.20**. The Aggregate node groups 2,400 rows into 12 departments.`,

  `I've built an execution plan with **4 nodes** for your query.

The plan pipeline is:\n- **SeqScan** on the primary table\n- **Filter** applied in-place\n- **Aggregate** for grouping\n- **Sort** for final ordering\n\nEstimated cost: **51.80** · ~650 rows. Inspect any node in the Query Plan panel to modify its parameters.`,

  `The query intent involves data retrieval with filtering. The planner generated a lightweight plan — no joins required.

\`\`\`sql
SELECT id, name, value, created_at
FROM records
WHERE category IN ('A', 'B', 'C')
  AND created_at >= '2024-01-01'
ORDER BY created_at DESC
LIMIT 100;
\`\`\`

Index Scan on \`records_category_created_at_idx\` was selected. Very efficient — estimated cost: **8.40** · ~100 rows.`,
];

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------

function randomDelay(): Promise<void> {
  const ms = DELAY_MIN + Math.random() * (DELAY_MAX - DELAY_MIN);
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/** Detects the rough intent of the user's message for response routing. */
function detectIntent(message: string): 'aggregate' | 'join' | 'filter' | 'sort' | 'default' {
  const m = message.toLowerCase();

  const aggregateKw = ['total', 'sum', 'count', 'average', 'avg', 'group', 'grouped', 'per', 'by region', 'by store', 'by country', 'by month', 'by year', 'revenue', 'sales'];
  const joinKw      = ['join', 'related', 'combined', 'users and', 'and orders', 'customers and', 'together', 'with their', 'along with'];
  const filterKw    = ['where', 'filter', 'only', 'greater than', 'less than', 'between', 'more than', 'under', 'above', 'recent', 'last', 'days', 'months'];
  const sortKw      = ['top', 'rank', 'ranked', 'best', 'highest', 'lowest', 'ordered', 'sorted', 'most', 'least', 'limit'];

  if (aggregateKw.some((kw) => m.includes(kw))) return 'aggregate';
  if (joinKw.some((kw) => m.includes(kw)))      return 'join';
  if (sortKw.some((kw) => m.includes(kw)))      return 'sort';
  if (filterKw.some((kw) => m.includes(kw)))    return 'filter';
  return 'default';
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Simulates an AI response for the given user message.
 *
 * TODO: Replace with real API call:
 *   const res = await fetch('/api/query', {
 *     method: 'POST',
 *     body: JSON.stringify({ message, sessionId }),
 *   });
 *   return res.json();
 */
export async function getMockResponse(userMessage: string): Promise<string> {
  await randomDelay();

  const intent = detectIntent(userMessage);

  const bank: Record<typeof intent, string[]> = {
    aggregate: RESPONSES_AGGREGATE,
    join:      RESPONSES_JOIN,
    filter:    RESPONSES_FILTER,
    sort:      RESPONSES_SORT,
    default:   RESPONSES_DEFAULT,
  };

  return pickRandom(bank[intent] ?? RESPONSES_DEFAULT);
}
