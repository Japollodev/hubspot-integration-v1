import type { ContactFieldName, ContactFields, FieldEvidence } from '../../lib/api';

function fullName(contact: ContactFields): string | null {
  const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ');
  return name || null;
}

const legibilityText: Record<FieldEvidence['legibility'], string> = {
  clear: 'Read clearly',
  partial: 'Partly readable',
  unreadable: 'Unreadable',
  absent: 'Not on the card',
};

/** Why a field is blank, from the extractor's evidence — e.g. Unreadable — read as "ada.lov??@…" (blurred). */
function evidenceText(ev: FieldEvidence): string {
  let text = legibilityText[ev.legibility];
  if (ev.source_text && ev.legibility !== 'absent') text += ` — read as “${ev.source_text}”`;
  if (ev.note) text += ` (${ev.note})`;
  return text;
}

function Value({ value, evidence }: { value: string | null; evidence: FieldEvidence[] }) {
  if (!value) {
    return (
      <dd aria-label="blank">
        <span className="text-slate-400">—</span>
        {evidence.map((ev, i) => (
          <p key={i} className="text-xs text-amber-800">
            {evidenceText(ev)}
          </p>
        ))}
      </dd>
    );
  }
  return <dd className="font-medium break-all">{value}</dd>;
}

export function ContactCard({ contact }: { contact: ContactFields }) {
  const evidenceFor = (...names: ContactFieldName[]) =>
    names
      .filter((name) => !contact[name])
      .map((name) => contact.evidence?.[name])
      .filter((ev): ev is FieldEvidence => ev !== undefined);

  return (
    <div aria-label="Contact" className="space-y-3 border-t border-slate-200 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">Contact</h3>
        {contact.extractor === 'sample' && (
          <span className="inline-flex rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-medium text-sky-800">
            Sample data
          </span>
        )}
        {contact.extractor === 'openai' && contact.status === 'succeeded' && (
          <span className="inline-flex rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-medium text-violet-800">
            Extracted by OpenAI{contact.model ? ` (${contact.model})` : ''}
          </span>
        )}
      </div>
      {contact.status === 'failed' && (
        <p role="status" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Contact extraction failed{contact.error ? `: ${contact.error}` : '.'} The photo was still
          saved.
        </p>
      )}
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-slate-500">Name</dt>
        <Value value={fullName(contact)} evidence={evidenceFor('first_name', 'last_name')} />
        <dt className="text-slate-500">Email</dt>
        <Value value={contact.email} evidence={evidenceFor('email')} />
        <dt className="text-slate-500">Phone</dt>
        <Value value={contact.phone} evidence={evidenceFor('phone')} />
        <dt className="text-slate-500">Job title</dt>
        <Value value={contact.job_title} evidence={evidenceFor('job_title')} />
      </dl>
    </div>
  );
}
