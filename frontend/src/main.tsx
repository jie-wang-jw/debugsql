import React from 'react';
import ReactDOM from 'react-dom/client';

// Bootstrap CSS (base utilities — overridden by our global.css)
import 'bootstrap/dist/css/bootstrap.min.css';

// Global design system (variables, reset, scrollbar, typography)
import './styles/global.css';

import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
