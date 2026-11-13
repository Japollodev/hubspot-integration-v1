import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import type { UploadResponse } from '../../lib/api';
import { formatBytes } from '../../lib/format';
import { MAX_UPLOAD_BYTES, UploadForm } from './UploadForm';

const result: UploadResponse = {
  id: '6f1c',
  filename: 'card.jpg',
  content_type: 'image/jpeg',
  size_bytes: 12345,
  sha256: 'abc',
  hubspot: { status: 'uploaded', file_id: '987', url: null, error: null },
};

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    }),
  );
}

function selectFile(file: File) {
  fireEvent.change(screen.getByLabelText(/business card photo/i), { target: { files: [file] } });
}

beforeAll(() => {
  // jsdom has no object URLs.
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
});

describe('UploadForm', () => {
  it('uploads the photo and shows filename, size and HubSpot status', async () => {
    const fetchSpy = mockFetch(200, result);
    render(<UploadForm />);

    const upload = screen.getByRole('button', { name: 'Upload' });
    expect(upload).toBeDisabled();

    selectFile(new File(['x'.repeat(10)], 'card.jpg', { type: 'image/jpeg' }));
    expect(screen.getByAltText(/preview/i)).toHaveAttribute('src', 'blob:preview');
    fireEvent.click(upload);

    expect(await screen.findByText('Upload complete')).toBeInTheDocument();
    expect(screen.getByText('card.jpg')).toBeInTheDocument();
    expect(screen.getByText(/12\.1 KB/)).toBeInTheDocument();
    expect(screen.getByText('Saved to HubSpot')).toBeInTheDocument();
    expect(screen.getByText('file #987')).toBeInTheDocument();

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toBe('/api/uploads');
    expect(init?.method).toBe('POST');
    expect((init?.body as FormData).get('file')).toBeInstanceOf(File);
  });

  it('shows the server error message', async () => {
    mockFetch(415, { error: { code: 'unsupported_type', message: 'Unsupported file type.' } });
    render(<UploadForm />);
    selectFile(new File(['hello'], 'notes.jpg', { type: 'image/jpeg' }));
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported file type.');
  });

  it('rejects files over the limit without calling the server', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(<UploadForm />);
    const big = new File(['x'], 'big.jpg', { type: 'image/jpeg' });
    Object.defineProperty(big, 'size', { value: MAX_UPLOAD_BYTES + 1 });
    selectFile(big);
    expect(screen.getByRole('alert')).toHaveTextContent('10 MB limit');
    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [1023, '1023 B'],
    [1536, '1.5 KB'],
    [10 * 1024 * 1024, '10.0 MB'],
  ])('%i -> %s', (n, expected) => {
    expect(formatBytes(n)).toBe(expected);
  });
});
