import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import App from './App';

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    }),
  );
}

describe('App', () => {
  it('renders the title and a healthy backend badge', async () => {
    const fetchSpy = mockFetch(200, { status: 'ok', version: '0.1.0' });
    render(<App />);

    expect(screen.getByRole('heading', { name: /crm importer/i })).toBeInTheDocument();
    expect(await screen.findByText('Backend: ok (v0.1.0)')).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith('/api/health', expect.anything());
  });

  it('shows unreachable when the health check fails', async () => {
    mockFetch(500, { error: { code: 'internal_error', message: 'boom' } });
    render(<App />);
    expect(await screen.findByText('Backend: unreachable')).toBeInTheDocument();
  });
});
