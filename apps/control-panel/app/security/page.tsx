'use client';

import { useState } from 'react';

interface NetworkPolicy {
  id: string;
  name: string;
  type: 'ingress' | 'egress';
  allowedIPs: string;
  allowedPorts: string;
}

interface TLSConfig {
  enabled: boolean;
  version: string;
  certificatePath: string;
  keyPath: string;
}

interface Role {
  id: string;
  name: string;
  permissions: string[];
}

export default function SecurityPage() {
  const [activeTab, setActiveTab] = useState<'policies' | 'tls' | 'access'>('policies');
  const [policies, setPolicies] = useState<NetworkPolicy[]>([]);
  const [tlsConfig, setTLSConfig] = useState<TLSConfig>({
    enabled: false,
    version: 'TLS1.3',
    certificatePath: '',
    keyPath: ''
  });
  const [roles, setRoles] = useState<Role[]>([]);
  const [showPolicyModal, setShowPolicyModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);

  const handleCreatePolicy = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const newPolicy: NetworkPolicy = {
      id: `policy-${Date.now()}`,
      name: formData.get('policy-name') as string,
      type: formData.get('policy-type') as 'ingress' | 'egress',
      allowedIPs: formData.get('allowed-ips') as string,
      allowedPorts: formData.get('allowed-ports') as string
    };
    setPolicies([...policies, newPolicy]);
    setShowPolicyModal(false);
  };

  const handleApplyTLSConfig = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    setTLSConfig({
      enabled: formData.get('enable-tls') === 'on',
      version: formData.get('tls-version') as string,
      certificatePath: formData.get('certificate-path') as string,
      keyPath: formData.get('key-path') as string
    });
    alert('TLS configuration applied successfully!');
  };

  const handleCreateRole = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const permissions: string[] = [];
    if (formData.get('read-permission')) permissions.push('read');
    if (formData.get('write-permission')) permissions.push('write');
    if (formData.get('delete-permission')) permissions.push('delete');

    const newRole: Role = {
      id: `role-${Date.now()}`,
      name: formData.get('role-name') as string,
      permissions
    };

  useEffect(() => {
    document.title = 'Security | Fog Compute';
  }, []);
    setRoles([...roles, newRole]);
    setShowRoleModal(false);
  };

  return (
    <div className="space-y-6" data-testid="security-dashboard">
      {/* Header */}
      <div className="glass rounded-xl p-6">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
          Security & Access Control
        </h1>
        <p className="text-gray-400 mt-2">
          Configure network policies, TLS/SSL encryption, and role-based access controls
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="glass rounded-xl p-2">
        <div className="flex space-x-2">
          <button
            data-testid="network-policies-tab"
            onClick={() => setActiveTab('policies')}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'policies' ? 'bg-fog-cyan text-white' : 'hover:bg-white/5'
            }`}
          >
            Network Policies
          </button>
          <button
            data-testid="tls-config-tab"
            onClick={() => setActiveTab('tls')}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'tls' ? 'bg-fog-cyan text-white' : 'hover:bg-white/5'
            }`}
          >
            TLS/SSL
          </button>
          <button
            data-testid="access-control-tab"
            onClick={() => setActiveTab('access')}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'access' ? 'bg-fog-cyan text-white' : 'hover:bg-white/5'
            }`}
          >
            Access Control
          </button>
        </div>
      </div>

      {/* Network Policies Tab */}
      {activeTab === 'policies' && (
        <div className="space-y-6">
          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold">Network Policies</h2>
              <button
                data-testid="add-policy-button"
                onClick={() => setShowPolicyModal(true)}
                className="px-4 py-2 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
              >
                + Add Policy
              </button>
            </div>

            <div className="space-y-4">
              {policies.map(policy => (
                <div
                  key={policy.id}
                  data-testid="policy-item"
                  className="glass rounded-lg p-4"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold">{policy.name}</h3>
                      <div className="text-sm text-gray-400 mt-1 space-y-1">
                        <p>Type: {policy.type}</p>
                        <p>Allowed IPs: {policy.allowedIPs}</p>
                        <p>Allowed Ports: {policy.allowedPorts}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {policies.length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  No network policies configured. Click "Add Policy" to create one.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TLS/SSL Tab */}
      {activeTab === 'tls' && (
        <div className="glass rounded-xl p-6">
          <h2 className="text-2xl font-semibold mb-6">TLS/SSL Configuration</h2>
          <form onSubmit={handleApplyTLSConfig} className="space-y-6">
            <div className="flex items-center space-x-3">
              <input
                name="enable-tls"
                data-testid="enable-tls-checkbox"
                type="checkbox"
                checked={tlsConfig.enabled}
                onChange={(e) => setTLSConfig({...tlsConfig, enabled: e.target.checked})}
                className="w-5 h-5"
              />
              <label className="text-lg font-medium">Enable TLS/SSL</label>
            </div>

            {tlsConfig.enabled && (
              <div className="space-y-4 pt-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    TLS Version
                  </label>
                  <select
                    name="tls-version"
                    data-testid="tls-version-select"
                    defaultValue={tlsConfig.version}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  >
                    <option value="TLS1.2">TLS 1.2</option>
                    <option value="TLS1.3">TLS 1.3</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Certificate Path
                  </label>
                  <input
                    name="certificate-path"
                    data-testid="certificate-path-input"
                    type="text"
                    defaultValue={tlsConfig.certificatePath}
                    placeholder="/etc/ssl/certs/cert.pem"
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Private Key Path
                  </label>
                  <input
                    name="key-path"
                    data-testid="key-path-input"
                    type="text"
                    defaultValue={tlsConfig.keyPath}
                    placeholder="/etc/ssl/private/key.pem"
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                  />
                </div>

                <button
                  type="submit"
                  data-testid="apply-tls-config-button"
                  className="w-full px-6 py-3 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
                >
                  Apply TLS Configuration
                </button>

                <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <span className="text-green-400" data-testid="tls-status">Enabled</span>
                  </div>
                </div>
              </div>
            )}

            {!tlsConfig.enabled && (
              <div className="p-4 bg-gray-500/10 border border-gray-500/20 rounded-lg">
                <div className="flex items-center space-x-2">
                  <span className="text-gray-400" data-testid="tls-status">Disabled</span>
                </div>
              </div>
            )}
          </form>
        </div>
      )}

      {/* Access Control Tab */}
      {activeTab === 'access' && (
        <div className="space-y-6">
          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold">Role-Based Access Control</h2>
              <button
                data-testid="add-role-button"
                onClick={() => setShowRoleModal(true)}
                className="px-4 py-2 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
              >
                + Add Role
              </button>
            </div>

            <div className="space-y-4">
              {roles.map(role => (
                <div
                  key={role.id}
                  data-testid="role-item"
                  className="glass rounded-lg p-4"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold">{role.name}</h3>
                      <div className="text-sm text-gray-400 mt-1">
                        Permissions: {role.permissions.join(', ')}
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {roles.length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  No roles configured. Click "Add Role" to create one.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Policy Modal */}
      {showPolicyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowPolicyModal(false)}>
          <div className="glass rounded-xl p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-2xl font-semibold mb-6">Create Network Policy</h2>
            <form onSubmit={handleCreatePolicy} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Policy Name</label>
                <input
                  name="policy-name"
                  data-testid="policy-name-input"
                  type="text"
                  required
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Policy Type</label>
                <select
                  name="policy-type"
                  data-testid="policy-type-select"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                >
                  <option value="ingress">Ingress</option>
                  <option value="egress">Egress</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Allowed IPs</label>
                <input
                  name="allowed-ips"
                  data-testid="allowed-ips-input"
                  type="text"
                  required
                  placeholder="10.0.0.0/8"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Allowed Ports</label>
                <input
                  name="allowed-ports"
                  data-testid="allowed-ports-input"
                  type="text"
                  required
                  placeholder="80,443"
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                />
              </div>

              <div className="flex space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowPolicyModal(false)}
                  className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="create-policy-button"
                  className="flex-1 px-4 py-2 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
                >
                  Create Policy
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Role Modal */}
      {showRoleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowRoleModal(false)}>
          <div className="glass rounded-xl p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-2xl font-semibold mb-6">Create Role</h2>
            <form onSubmit={handleCreateRole} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Role Name</label>
                <input
                  name="role-name"
                  data-testid="role-name-input"
                  type="text"
                  required
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-fog-cyan"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-400 mb-2">Permissions</label>
                <div className="flex items-center space-x-3">
                  <input
                    name="read-permission"
                    data-testid="read-permission-checkbox"
                    type="checkbox"
                    className="w-5 h-5"
                  />
                  <label>Read</label>
                </div>
                <div className="flex items-center space-x-3">
                  <input
                    name="write-permission"
                    data-testid="write-permission-checkbox"
                    type="checkbox"
                    className="w-5 h-5"
                  />
                  <label>Write</label>
                </div>
                <div className="flex items-center space-x-3">
                  <input
                    name="delete-permission"
                    data-testid="delete-permission-checkbox"
                    type="checkbox"
                    className="w-5 h-5"
                  />
                  <label>Delete</label>
                </div>
              </div>

              <div className="flex space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowRoleModal(false)}
                  className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="create-role-button"
                  className="flex-1 px-4 py-2 bg-fog-cyan text-white rounded-lg hover:bg-fog-cyan/80 transition-colors"
                >
                  Create Role
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
