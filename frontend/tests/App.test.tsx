import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, beforeEach, it, expect } from 'vitest';
import App from '../src/App';

// Global fetch mock to prevent network calls and simulate SSE stream
vi.stubGlobal('fetch', vi.fn((url: string | URL | Request) => {
  const urlStr = url.toString();
  if (urlStr.includes('/api/chat')) {
    return Promise.resolve({
      ok: true,
      headers: new Headers({
        'content-type': 'text/event-stream'
      }),
      body: {
        getReader: () => {
          let isDone = false;
          return {
            read: () => {
              if (isDone) {
                return new Promise(resolve => setTimeout(() => resolve({ done: true }), 2000));
              }
              isDone = true;
              const encoder = new TextEncoder();
              // Simulate the backend streaming a status bubble
              return Promise.resolve({
                done: false,
                value: encoder.encode('data: {"type": "status", "value": "Connecting..."}\\n\\n')
              });
            },
            releaseLock: vi.fn(),
            cancel: vi.fn()
          };
        }
      }
    });
  }
  
  if (urlStr.includes('/api/embed')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status: "success" })
    });
  }

  if (urlStr.includes('/api/health')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status: "ok" })
    });
  }

  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({})
  });
}));

// Mock Element.prototype.scrollIntoView since jsdom doesn't support it
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock chrome API since the app relies on chrome.tabs for active tab context
const mockChrome = {
  runtime: {
    lastError: null
  },
  tabs: {
    query: vi.fn((queryInfo, callback) => {
      if (callback) callback([{ id: 1, url: 'https://example.com', title: 'Example' }]);
    }),
    sendMessage: vi.fn((tabId, msg, callback) => {
      if (callback) callback({ contexts: ['Simulated webpage context.'] });
    })
  },
  scripting: {
    executeScript: vi.fn((config, callback) => {
      if (callback) callback([{ result: { contexts: ['Simulated webpage context.'] } }]);
    })
  }
};
vi.stubGlobal('chrome', mockChrome);
window.chrome = mockChrome as any;

describe('ThinkTab AI App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('asserts that the App renders the ThinkTab AI header and the Empty State correctly on first load', () => {
    render(<App />);

    // Test 1: Header renders
    expect(screen.getByText(/ThinkTab/i)).toBeInTheDocument();

    // Test 1: Empty state text renders
    expect(screen.getByText(/Ask about this page/i)).toBeInTheDocument();
  });

  it('simulates typing Hello into the input and clicking the Send button, asserting that the input clears and a loading/status bubble appears', async () => {
    render(<App />);

    // Find the textarea input
    const input = screen.getByPlaceholderText(/Ask anything about this page.../i);
    expect(input).toBeInTheDocument();

    const inputArea = screen.getByPlaceholderText(/Ask anything/i);

    fireEvent.change(inputArea, { target: { value: 'Hello' } });
    fireEvent.keyDown(inputArea, { key: 'Enter', code: 'Enter', shiftKey: false });

    // Assert that the input was cleared
    await waitFor(() => {
      expect(inputArea).toHaveValue('');
    });

    // Assert the status bubble "Connecting..." appears instantly
    await waitFor(() => {
      expect(screen.getByText(/Connecting.../i)).toBeInTheDocument();
    });
  });
});
