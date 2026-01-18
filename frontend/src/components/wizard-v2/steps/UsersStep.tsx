// frontend/src/components/wizard-v2/steps/UsersStep.tsx
import { Users, UserPlus, Shield, Eye, Swords } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore } from '../../../stores/wizardStore';

const ROLE_ICONS = {
  'red-team': Swords,
  'blue-team': Shield,
  'white-cell': Users,
  'observer': Eye,
  'custom': UserPlus,
};

const ROLE_COLORS = {
  'red-team': 'text-red-600 bg-red-50 border-red-200',
  'blue-team': 'text-blue-600 bg-blue-50 border-blue-200',
  'white-cell': 'text-purple-600 bg-purple-50 border-purple-200',
  'observer': 'text-gray-600 bg-gray-50 border-gray-200',
  'custom': 'text-green-600 bg-green-50 border-green-200',
};

export function UsersStep() {
  const { users, setGroupCount, networks } = useWizardStore();

  // Generate usernames based on group counts
  const generatedUsers = users.groups.flatMap((group) =>
    Array.from({ length: group.count }, (_, i) => ({
      id: `${group.id}-${i + 1}`,
      username: `${group.role.split('-')[0]}-${String(i + 1).padStart(2, '0')}`,
      group: group.name,
      role: group.role,
      accessLevel: group.accessLevel,
    }))
  );

  const totalUsers = generatedUsers.length;

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Users & Groups</h2>
      <p className="text-gray-600 mb-8">
        Configure team sizes and access levels. Users will be auto-generated based on your settings.
      </p>

      <div className="grid grid-cols-2 gap-8">
        {/* Team segments */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Team Segments</h3>
          <div className="space-y-3">
            {users.groups.map((group) => {
              const Icon = ROLE_ICONS[group.role] || Users;
              const colors = ROLE_COLORS[group.role] || ROLE_COLORS.custom;

              return (
                <div
                  key={group.id}
                  className={clsx('flex items-center justify-between p-4 rounded-lg border', colors)}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-5 h-5" />
                    <div>
                      <div className="font-medium">{group.name}</div>
                      <div className="text-xs opacity-75">
                        {group.accessLevel === 'full'
                          ? 'Full access to all VMs'
                          : group.accessLevel === 'limited'
                          ? 'Limited access'
                          : 'Read-only access'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setGroupCount(group.id, Math.max(0, group.count - 1))}
                      className="w-8 h-8 flex items-center justify-center rounded bg-white border border-current text-current hover:bg-opacity-50"
                    >
                      -
                    </button>
                    <span className="w-8 text-center font-semibold">{group.count}</span>
                    <button
                      onClick={() => setGroupCount(group.id, Math.min(10, group.count + 1))}
                      className="w-8 h-8 flex items-center justify-center rounded bg-white border border-current text-current hover:bg-opacity-50"
                    >
                      +
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="text-sm font-medium text-gray-700 mb-2">Naming Pattern</div>
            <code className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">
              [team]-[number]
            </code>
            <div className="text-xs text-gray-500 mt-1">
              Example: red-01, blue-02, white-01
            </div>
          </div>
        </div>

        {/* Generated users preview */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Generated Users ({totalUsers})
          </h3>

          {totalUsers === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">
                Adjust team sizes to generate users
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Users are optional - you can skip this step
              </p>
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Username</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Team</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Access</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {generatedUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-gray-900">{user.username}</td>
                      <td className="px-4 py-2 text-gray-600">{user.group}</td>
                      <td className="px-4 py-2">
                        <span
                          className={clsx(
                            'px-2 py-0.5 text-xs font-medium rounded',
                            user.accessLevel === 'full'
                              ? 'bg-green-100 text-green-700'
                              : user.accessLevel === 'limited'
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-gray-100 text-gray-600'
                          )}
                        >
                          {user.accessLevel}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Access rules summary */}
          {totalUsers > 0 && networks.segments.length > 0 && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="text-sm font-medium text-blue-800 mb-2">Access Rules</div>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• Red Team → Full access to all VMs</li>
                <li>• Blue Team → Access to defender workstations only</li>
                <li>• White Cell → Full access + console override</li>
                <li>• Observers → Read-only monitoring</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
