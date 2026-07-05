// ================================================
// DebugSQL – Chat-specific types
// ================================================

/** Extends the global ChatMessage for chat UI rendering. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  proposedActions?: import('../../services/api/chatApi').ProposedToolAction[];
  actionResults?: Record<string, string>;
  confidence?: number | null;
  assumptions?: string[];
  tablesUsed?: string[];
  usedContext?: boolean | null;
  conversationMode?: 'new_query' | 'refine_query' | 'schema_answer' | 'clarify' | null;
  workingStateRevision?: number | null;
  mediaMatches?: Array<Record<string, unknown>>;
  mediaPredicate?: string | null;
  mediaType?: string | null;
  mediaLimit?: number | null;
}

/** A parsed segment of a message (plain text vs. code block). */
export interface ContentSegment {
  type: 'text' | 'code';
  content: string;
  language?: string;
}

/** Clickable prompt suggestion shown in the empty state. */
export interface SuggestedPrompt {
  id: string;
  label: string;
  description: string;
  icon: 'chart' | 'filter' | 'join' | 'sort' | 'question';
}

/** Status of the chat AI (typing / idle / error). */
export type ChatStatus = 'idle' | 'thinking' | 'error';
