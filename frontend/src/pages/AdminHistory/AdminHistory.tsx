import { useEffect, useState } from 'react';
import {
  getAdminHistoryConversation,
  getAdminHistorySummary,
  type AdminHistoryConversationDetail,
  type AdminHistoryConversationSummary,
} from '../../services/api/adminHistoryApi';
import './AdminHistory.css';

const PAGE_SIZE = 20;

export default function AdminHistory() {
  const [items, setItems] = useState<AdminHistoryConversationSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminHistoryConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPage = async (nextOffset = 0) => {
    setLoading(true);
    setError(null);
    try {
      const summary = await getAdminHistorySummary({ limit: PAGE_SIZE, offset: nextOffset });
      setItems((current) => (nextOffset === 0 ? summary.conversations : [...current, ...summary.conversations]));
      setOffset(nextOffset + summary.conversations.length);
      setHasMore(summary.pagination.hasMoreConversations);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load admin history.');
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (conversationId: string) => {
    setSelectedId(conversationId);
    setDetail(null);
    setDetailLoading(true);
    setError(null);
    try {
      setDetail(await getAdminHistoryConversation(conversationId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load conversation detail.');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    void loadPage(0);
  }, []);

  return (
    <main className="admin-history">
      <header className="admin-history__header">
        <div>
          <p className="admin-history__eyebrow">Admin</p>
          <h1>All User History</h1>
          <p className="admin-history__copy">Read-only view of recent conversations and execution previews.</p>
        </div>
        <a className="admin-history__back" href="/">
          Back to workspace
        </a>
      </header>

      {error && <div className="admin-history__error">{error}</div>}

      <section className="admin-history__grid">
        <aside className="admin-history__panel">
          <div className="admin-history__panel-header">
            <h2>Recent conversations</h2>
            <p className="admin-history__meta">{items.length} loaded</p>
          </div>
          {loading && items.length === 0 ? (
            <div className="admin-history__empty">Loading history...</div>
          ) : items.length === 0 ? (
            <div className="admin-history__empty">No conversations found.</div>
          ) : (
            <>
              <div className="admin-history__list">
                {items.map((item) => (
                  <button
                    className={`admin-history__item${item.id === selectedId ? ' admin-history__item--active' : ''}`}
                    key={item.id}
                    type="button"
                    onClick={() => void loadDetail(item.id)}
                  >
                    <span className="admin-history__item-title">{item.title || 'Untitled conversation'}</span>
                    <span className="admin-history__item-subtitle">{item.user.email}</span>
                    <span className="admin-history__item-subtitle">
                      {formatDataset(item)} · {new Date(item.updatedAt).toLocaleString()}
                    </span>
                  </button>
                ))}
              </div>
              {hasMore && (
                <button className="admin-history__load" type="button" onClick={() => void loadPage(offset)}>
                  Load more
                </button>
              )}
            </>
          )}
        </aside>

        <section className="admin-history__panel">
          <div className="admin-history__panel-header">
            <h2>Conversation detail</h2>
            <p className="admin-history__meta">
              {detail ? `${detail.user.email} · ${formatDetailDataset(detail)}` : 'Select a conversation'}
            </p>
          </div>
          {detailLoading ? (
            <div className="admin-history__empty">Loading conversation...</div>
          ) : detail ? (
            <ConversationDetail detail={detail} />
          ) : (
            <div className="admin-history__empty">Choose a conversation to inspect messages and execution status.</div>
          )}
        </section>
      </section>
    </main>
  );
}

function ConversationDetail({ detail }: { detail: AdminHistoryConversationDetail }) {
  return (
    <div className="admin-history__detail">
      <p className="admin-history__meta">Active plan: {detail.activePlanId || 'none'}</p>
      <p className="admin-history__meta">
        Latest execution: {detail.latestExecutionStatus || 'none'}
        {detail.latestExecutionResultPreview
          ? ` · ${detail.latestExecutionResultPreview.rowCount ?? 0} preview rows`
          : ''}
      </p>
      <div className="admin-history__messages">
        {detail.messages.map((message) => (
          <article className="admin-history__message" key={message.id}>
            <div className="admin-history__message-role">
              {message.role} · {new Date(message.timestamp).toLocaleString()}
            </div>
            <div className="admin-history__message-content">{message.content}</div>
          </article>
        ))}
      </div>
    </div>
  );
}

function formatDataset(item: AdminHistoryConversationSummary): string {
  const context = item.datasetContext;
  if (!context) {
    return 'no dataset';
  }
  return `${context.benchmark || 'benchmark'} / ${context.dbId || 'database'}`;
}

function formatDetailDataset(item: AdminHistoryConversationDetail): string {
  const context = item.datasetContext;
  if (!context) {
    return 'no dataset';
  }
  return `${context.benchmark || 'benchmark'} / ${context.dbId || 'database'}`;
}
