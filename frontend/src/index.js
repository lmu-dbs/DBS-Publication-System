import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/App.css';
import App from './App';

// Sanity check: ensure React loaded correctly to help debug issues where React is null
if (!React || typeof React.useState !== 'function') {
  // Print diagnostic info to the console to help debugging duplicate/missing React
  // This will make the failure explicit instead of causing a vague "useState of null" error.
  // Keep this check minimal and easy to remove once the root cause is found.
  // eslint-disable-next-line no-console
  console.error('React appears to be missing or improperly loaded:', React);
  throw new Error('React not loaded correctly. Run `npm install` and ensure a single React version is used.');
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);