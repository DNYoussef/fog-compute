const sectionLabels: Record<string, string> = {
  benchmarks: 'Benchmarks',
  betanet: 'Betanet',
  tasks: 'Tasks',
  nodes: 'Nodes',
  resources: 'Resources',
};

export default function ControlPanelSectionPage({ params }: { params: { section: string[] } }) {
  const section = params.section.join('/');
  const label = sectionLabels[section] || section.replaceAll('-', ' ');

  return (
    <section data-testid="control-panel" className="space-y-4">
      <h1 className="text-3xl font-semibold capitalize">Control Panel {label}</h1>
      <p className="text-sm text-gray-300">
        Authenticated operator workspace for {label.toLowerCase()} operations.
      </p>
    </section>
  );
}
