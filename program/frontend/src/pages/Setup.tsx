import { useActiveDomain } from '../shell/ActiveDomainContext';
import { DomainSetupWorkbench } from '../components/domain-setup/DomainSetupWorkbench';
import '../styles/setup.css';

export function Setup() {
  const { activeDomain } = useActiveDomain();

  return (
    <main className="setup-page setup-page--workbench">
      <header className="setup-page__header">
        <h1 className="setup-page__title">Setup</h1>
        <p className="setup-page__lead">
          Build the chapters of <strong>{activeDomain?.id ?? '…'}</strong>: add sources, compile a
          wiki, review and approve it, then generate the question bank.
        </p>
      </header>
      <DomainSetupWorkbench />
    </main>
  );
}
