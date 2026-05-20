import { FiDatabase } from 'react-icons/fi';
import { StatusBadge } from '../ui/StatusBadge';
import type { ChatStatus } from './chat.types';

interface ChatHeaderProps {
  status: ChatStatus;
}

const STATUS_LABEL: Record<ChatStatus, string> = {
  idle:     'AI Ready',
  thinking: 'Thinking…',
  error:    'Offline',
};

const STATUS_VARIANT: Record<ChatStatus, 'green' | 'blue' | 'red'> = {
  idle:     'green',
  thinking: 'blue',
  error:    'red',
};

/** Fixed header bar for the chat panel with branding and AI status. */
export function ChatHeader({ status }: ChatHeaderProps) {
  return (
    <header className="chat-header">
      <div className="chat-header__brand">
        <div className="chat-header__icon-wrap">
          <FiDatabase size={15} />
        </div>
        <div className="chat-header__titles">
          <span className="chat-header__name">DebugSQL</span>
          <span className="chat-header__sub">Editable Query Plans for NL2SQL</span>
        </div>
      </div>

      <StatusBadge
        label={STATUS_LABEL[status]}
        variant={STATUS_VARIANT[status]}
        dot
      />
    </header>
  );
}
