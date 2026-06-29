// ================================================
// DebugSQL – SQLPreview  (Phase 5)
//
// Renders SQL with lightweight keyword/token highlighting.
// No external syntax-highlighting library required.
//
// TODO: Replace tokenizer with a proper SQL grammar parser
// TODO: Add diff view when SQL changes after inspector edits
// TODO: Support editable SQL with live backend validation
// ================================================

import { useState, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import { FiCopy, FiCheck, FiCode, FiChevronDown, FiChevronRight } from 'react-icons/fi';

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

type TokenKind = 'keyword' | 'function' | 'string' | 'number' | 'comment' | 'operator' | 'text';

interface SQLToken {
  text: string;
  kind: TokenKind;
}

const SQL_KEYWORDS = new Set([
  'SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT',
  'OFFSET', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'FULL', 'OUTER', 'CROSS',
  'ON', 'AS', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL', 'LIKE', 'BETWEEN',
  'DISTINCT', 'UNION', 'ALL', 'EXCEPT', 'INTERSECT', 'WITH', 'CASE',
  'WHEN', 'THEN', 'ELSE', 'END', 'INSERT', 'INTO', 'VALUES', 'UPDATE',
  'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'INDEX', 'ASC',
  'DESC', 'TRUE', 'FALSE', 'INTERVAL', 'CURRENT_DATE', 'CURRENT_TIMESTAMP',
]);

const SQL_FUNCTIONS = new Set([
  'SUM', 'COUNT', 'AVG', 'MAX', 'MIN', 'COALESCE', 'NULLIF', 'CAST',
  'DATE_TRUNC', 'DATE_PART', 'NOW', 'EXTRACT', 'FLOOR', 'CEIL', 'ROUND',
  'LENGTH', 'UPPER', 'LOWER', 'TRIM', 'CONCAT', 'SUBSTRING', 'REPLACE',
  'TO_CHAR', 'TO_DATE', 'ARRAY_AGG', 'STRING_AGG', 'ROW_NUMBER', 'RANK',
]);

function tokenizeSQL(sql: string): SQLToken[] {
  const tokens: SQLToken[] = [];
  let i = 0;

  while (i < sql.length) {
    // Single-line comment
    if (sql[i] === '-' && sql[i + 1] === '-') {
      const end = sql.indexOf('\n', i);
      const text = end === -1 ? sql.slice(i) : sql.slice(i, end);
      tokens.push({ text, kind: 'comment' });
      i += text.length;
      continue;
    }

    // Single-quoted string
    if (sql[i] === "'") {
      let j = i + 1;
      while (j < sql.length && sql[j] !== "'") j++;
      tokens.push({ text: sql.slice(i, j + 1), kind: 'string' });
      i = j + 1;
      continue;
    }

    // Word (keyword / function / identifier)
    if (/[a-zA-Z_]/.test(sql[i])) {
      let j = i;
      while (j < sql.length && /[\w]/.test(sql[j])) j++;
      const word  = sql.slice(i, j);
      const upper = word.toUpperCase();
      let kind: TokenKind = 'text';
      if (SQL_KEYWORDS.has(upper))  kind = 'keyword';
      if (SQL_FUNCTIONS.has(upper)) kind = 'function';
      tokens.push({ text: word, kind });
      i = j;
      continue;
    }

    // Number
    if (/\d/.test(sql[i])) {
      let j = i;
      while (j < sql.length && /[\d.]/.test(sql[j])) j++;
      tokens.push({ text: sql.slice(i, j), kind: 'number' });
      i = j;
      continue;
    }

    // Operators and punctuation worth highlighting
    if (/[=<>!]/.test(sql[i])) {
      let j = i;
      while (j < sql.length && /[=<>!]/.test(sql[j])) j++;
      tokens.push({ text: sql.slice(i, j), kind: 'operator' });
      i = j;
      continue;
    }

    // Everything else (whitespace, commas, semicolons…)
    tokens.push({ text: sql[i], kind: 'text' });
    i++;
  }

  return tokens;
}

const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword:  'sql-kw',
  function: 'sql-fn',
  string:   'sql-str',
  number:   'sql-num',
  comment:  'sql-cmt',
  operator: 'sql-op',
  text:     '',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SQLPreviewProps {
  sql: string;
}

export function SQLPreview({ sql }: SQLPreviewProps) {
  const [copied, setCopied] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setIsOpen(false);
  }, [sql]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard unavailable in some environments
    }
  }, [sql]);

  const tokens = tokenizeSQL(sql);

  return (
    <motion.div
      className={`sql-preview ${isOpen ? 'sql-preview--open' : 'sql-preview--collapsed'}`}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Header bar */}
      <div className="sql-preview__header">
        <button
          type="button"
          className="sql-preview__toggle"
          onClick={() => setIsOpen((value) => !value)}
          aria-expanded={isOpen}
          aria-controls="generated-sql-preview"
        >
          {isOpen ? <FiChevronDown size={13} /> : <FiChevronRight size={13} />}
          <FiCode size={11} />
          <span className="sql-preview__title">Generated SQL</span>
        </button>
        <motion.button
          className={`sql-preview__copy-btn ${copied ? 'sql-preview__copy-btn--done' : ''}`}
          onClick={handleCopy}
          whileTap={{ scale: 0.94 }}
          transition={{ duration: 0.1 }}
          aria-label="Copy SQL to clipboard"
        >
          {copied ? <FiCheck size={11} /> : <FiCopy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </motion.button>
      </div>

      {isOpen && (
        <pre id="generated-sql-preview" className="sql-preview__code" aria-label="SQL query">
          <code>
            {tokens.map((token, idx) => {
              const cls = TOKEN_CLASS[token.kind];
              return cls
                ? <span key={idx} className={cls}>{token.text}</span>
                : token.text;
            })}
          </code>
        </pre>
      )}
    </motion.div>
  );
}
