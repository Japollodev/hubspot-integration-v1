import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import type { UploadResponse } from '../../lib/api';
import { formatBytes } from '../../lib/format';
import { getOpenAIKey, setOpenAIKey } from '../../lib/openaiKey';
import { MAX_UPLOAD_BYTES, UploadForm } from './UploadForm';

const USER_KEY = 'sk-test-user-key-abcd';

const result: UploadResponse = {
  id: '6f1c',
  filename: 'card.jpg',
  content_type: 'image/jpeg',
  size_bytes: 12345,
  sha256: 'abc',
  hubspot: { status: 'uploaded', file_id: '987', url: null, error: null },
  contact: {
    extractor: 'sample',
    status: 'succeeded',
    model: null,
    error_code: null,
    error: null,
    evidence: {},
    first_name: 'Ada',
    last_name: 'Lovelace',
    email: 'ada.lovelace@example.com',
    phone: '+1 555 0100',
    job_title: 'Head of Engineering',
  },
};

type Route = { status: number; body: unknown };

/** Route fetches by URL; each call gets a fresh Response. Unlisted URLs 404. */
function mockApi(routes: Record<string, Route>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const route = routes[String(input)] ?? {
      status: 404,
      body: { error: { code: 'http_error', message: 'Not Found' } },
    };
    return new Response(JSON.stringify(route.body), {
      status: route.status,
      headers: { 'content-type': 'application/json' },
    });
  });
}

const noServerKey: Route = {
  status: 200,
  body: { server_key_available: false, model: 'gpt-4o-mini' },
};

function uploadCalls(fetchSpy: ReturnType<typeof mockApi>) {
  return fetchSpy.mock.calls.filter(([url]) => url === '/api/uploads');
}

function selectFile(file: File) {
  fireEvent.change(screen.getByLabelText(/business card photo/i), { target: { files: [file] } });
}

function selectAndUpload() {
  selectFile(new File(['x'], 'card.jpg', { type: 'image/jpeg' }));
  fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
}

beforeAll(() => {
  // jsdom has no object URLs.
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe('UploadForm (with a saved OpenAI key)', () => {
  beforeEach(() => setOpenAIKey(USER_KEY, { remember: false }));

  it('uploads the photo with the key and shows filename, size and HubSpot status', async () => {
    const fetchSpy = mockApi({
      '/api/openai/status': noServerKey,
      '/api/uploads': { status: 200, body: result },
    });
    render(<UploadForm />);

    expect(screen.getByLabelText('OpenAI key status')).toHaveTextContent('sk-…abcd');
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

    const [url, init] = uploadCalls(fetchSpy)[0]!;
    expect(url).toBe('/api/uploads');
    expect(init?.method).toBe('POST');
    expect((init?.body as FormData).get('file')).toBeInstanceOf(File);
    expect((init?.headers as Record<string, string>)['X-OpenAI-Key']).toBe(USER_KEY);
  });

  it('shows the sample contact fields after upload', async () => {
    mockApi({ '/api/openai/status': noServerKey, '/api/uploads': { status: 200, body: result } });
    render(<UploadForm />);
    selectAndUpload();

    const contact = await screen.findByLabelText('Contact');
    expect(contact).toHaveTextContent('Ada Lovelace');
    expect(contact).toHaveTextContent('ada.lovelace@example.com');
    expect(contact).toHaveTextContent('+1 555 0100');
    expect(contact).toHaveTextContent('Head of Engineering');
    expect(contact).toHaveTextContent('Sample data');
  });

  it('renders a blank field as a dash with the evidence for why', async () => {
    mockApi({
      '/api/openai/status': noServerKey,
      '/api/uploads': {
        status: 200,
        body: {
          ...result,
          contact: {
            ...result.contact!,
            extractor: 'openai',
            model: 'gpt-4o-mini',
            email: null,
            evidence: {
              email: { legibility: 'unreadable', source_text: 'ada.lov???@???', note: 'blurred' },
            },
          },
        },
      },
    });
    render(<UploadForm />);
    selectAndUpload();

    const contact = await screen.findByLabelText('Contact');
    const blank = screen.getByLabelText('blank');
    expect(blank).toHaveTextContent('—');
    expect(blank).toHaveTextContent('Unreadable — read as “ada.lov???@???” (blurred)');
    expect(contact).toHaveTextContent('Extracted by OpenAI (gpt-4o-mini)');
    expect(contact).not.toHaveTextContent('Sample data');
  });

  it('shows a banner when extraction failed', async () => {
    mockApi({
      '/api/openai/status': noServerKey,
      '/api/uploads': {
        status: 200,
        body: {
          ...result,
          contact: {
            ...result.contact!,
            extractor: 'openai',
            status: 'failed',
            error_code: 'openai_timeout',
            error: 'OpenAI timed out reading the photo.',
            first_name: null,
            last_name: null,
            email: null,
            phone: null,
            job_title: null,
          },
        },
      },
    });
    render(<UploadForm />);
    selectAndUpload();
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Contact extraction failed: OpenAI timed out reading the photo.',
    );
  });

  it('clears a rejected key and asks for a new one, keeping the selected file', async () => {
    mockApi({
      '/api/openai/status': noServerKey,
      '/api/uploads': {
        status: 401,
        body: {
          error: {
            code: 'openai_key_invalid',
            message: 'OpenAI rejected the API key. Check it and enter it again.',
          },
        },
      },
    });
    render(<UploadForm />);
    selectAndUpload();

    const form = await screen.findByRole('form', { name: 'OpenAI API key' });
    expect(form).toHaveTextContent('OpenAI rejected the API key');
    expect(getOpenAIKey()).toBeNull();
    expect(screen.getByRole('button', { name: 'Upload' })).toBeEnabled();
  });

  it('shows the server error message', async () => {
    mockApi({
      '/api/openai/status': noServerKey,
      '/api/uploads': {
        status: 415,
        body: { error: { code: 'unsupported_type', message: 'Unsupported file type.' } },
      },
    });
    render(<UploadForm />);
    selectAndUpload();
    expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported file type.');
  });

  it('forgets the key on request', () => {
    mockApi({ '/api/openai/status': noServerKey });
    render(<UploadForm />);
    fireEvent.click(screen.getByRole('button', { name: 'Forget' }));
    expect(getOpenAIKey()).toBeNull();
    expect(screen.getByRole('form', { name: 'OpenAI API key' })).toBeInTheDocument();
  });

  it('rejects files over the limit without calling the server', () => {
    const fetchSpy = mockApi({ '/api/openai/status': noServerKey });
    render(<UploadForm />);
    const big = new File(['x'], 'big.jpg', { type: 'image/jpeg' });
    Object.defineProperty(big, 'size', { value: MAX_UPLOAD_BYTES + 1 });
    selectFile(big);
    expect(screen.getByRole('alert')).toHaveTextContent('10 MB limit');
    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled();
    expect(uploadCalls(fetchSpy)).toHaveLength(0);
  });
});

describe('UploadForm (bring your own key)', () => {
  it('asks for a key, verifies and saves it, then sends it with the upload', async () => {
    const fetchSpy = mockApi({
      '/api/openai/status': noServerKey,
      '/api/openai/verify': { status: 200, body: { valid: true, message: null } },
      '/api/uploads': { status: 200, body: result },
    });
    render(<UploadForm />);

    fireEvent.change(screen.getByLabelText('OpenAI API key', { selector: 'input' }), {
      target: { value: `  ${USER_KEY} ` },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Verify & save' }));

    expect(await screen.findByLabelText('OpenAI key status')).toHaveTextContent('sk-…abcd');
    expect(sessionStorage.getItem('hubspot-importer.openai-key')).toBe(USER_KEY);
    expect(localStorage.length).toBe(0);
    const verify = fetchSpy.mock.calls.find(([url]) => url === '/api/openai/verify')!;
    expect((verify[1]?.headers as Record<string, string>)['X-OpenAI-Key']).toBe(USER_KEY);

    selectAndUpload();
    await screen.findByText('Upload complete');
    const [, init] = uploadCalls(fetchSpy)[0]!;
    expect((init?.headers as Record<string, string>)['X-OpenAI-Key']).toBe(USER_KEY);
  });

  it('"Remember on this device" stores the key in localStorage', async () => {
    mockApi({
      '/api/openai/status': noServerKey,
      '/api/openai/verify': { status: 200, body: { valid: true, message: null } },
    });
    render(<UploadForm />);
    fireEvent.change(screen.getByLabelText('OpenAI API key', { selector: 'input' }), {
      target: { value: USER_KEY },
    });
    fireEvent.click(screen.getByRole('checkbox', { name: /remember on this device/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Verify & save' }));

    await screen.findByLabelText('OpenAI key status');
    expect(localStorage.getItem('hubspot-importer.openai-key')).toBe(USER_KEY);
    expect(sessionStorage.length).toBe(0);
  });

  it('does not save a key OpenAI rejects', async () => {
    mockApi({
      '/api/openai/status': noServerKey,
      '/api/openai/verify': {
        status: 200,
        body: { valid: false, message: 'OpenAI rejected this API key.' },
      },
    });
    render(<UploadForm />);
    fireEvent.change(screen.getByLabelText('OpenAI API key', { selector: 'input' }), {
      target: { value: 'sk-bad' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Verify & save' }));

    expect(await screen.findByText('OpenAI rejected this API key.')).toBeInTheDocument();
    expect(getOpenAIKey()).toBeNull();
  });

  it('uses the server dev key when available, and prompts if the server says it is missing', async () => {
    const fetchSpy = mockApi({
      '/api/openai/status': { status: 200, body: { server_key_available: true, model: 'm' } },
      '/api/uploads': {
        status: 400,
        body: {
          error: {
            code: 'openai_key_missing',
            message: 'Add your OpenAI API key to extract contacts.',
          },
        },
      },
    });
    render(<UploadForm />);

    expect(await screen.findByText(/server's development OpenAI key/)).toBeInTheDocument();
    selectAndUpload();

    const form = await screen.findByRole('form', { name: 'OpenAI API key' });
    expect(form).toHaveTextContent('Add your OpenAI API key to extract contacts.');
    await waitFor(() => expect(uploadCalls(fetchSpy)).toHaveLength(1));
    const [, init] = uploadCalls(fetchSpy)[0]!;
    expect((init?.headers as Record<string, string>)['X-OpenAI-Key']).toBeUndefined();
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
