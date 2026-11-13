import { BackendStatus } from './components/BackendStatus';
import { UploadForm } from './features/upload/UploadForm';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold">
            <span className="text-brand">HubSpot</span> CRM Importer
          </h1>
          <BackendStatus />
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-10">
        <UploadForm />
      </main>
    </div>
  );
}
