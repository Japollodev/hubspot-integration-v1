import type { ContactFields } from '../../lib/api';

function fullName(contact: ContactFields): string | null {
  const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ');
  return name || null;
}

function Value({ value }: { value: string | null }) {
  if (!value) {
    return (
      <dd className="text-slate-400" aria-label="blank">
        —
      </dd>
    );
  }
  return <dd className="font-medium break-all">{value}</dd>;
}

export function ContactCard({ contact }: { contact: ContactFields }) {
  return (
    <div aria-label="Contact" className="space-y-3 border-t border-slate-200 pt-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">Contact</h3>
        {contact.extractor === 'sample' && (
          <span className="inline-flex rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-medium text-sky-800">
            Sample data
          </span>
        )}
      </div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-slate-500">Name</dt>
        <Value value={fullName(contact)} />
        <dt className="text-slate-500">Email</dt>
        <Value value={contact.email} />
        <dt className="text-slate-500">Phone</dt>
        <Value value={contact.phone} />
        <dt className="text-slate-500">Job title</dt>
        <Value value={contact.job_title} />
      </dl>
    </div>
  );
}
