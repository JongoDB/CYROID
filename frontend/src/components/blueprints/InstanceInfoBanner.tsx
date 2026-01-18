// frontend/src/components/blueprints/InstanceInfoBanner.tsx
import { Link } from 'react-router-dom';
import { Instance, Blueprint } from '../../services/api';
import { Info, ExternalLink, RefreshCw } from 'lucide-react';

interface Props {
  instance: Instance;
  blueprint: Blueprint;
  onRedeploy?: () => void;
}

export default function InstanceInfoBanner({ instance, blueprint, onRedeploy }: Props) {
  const isOutdated = instance.blueprint_version < blueprint.version;

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
      <div className="flex items-start">
        <Info className="h-5 w-5 text-blue-500 mt-0.5" />
        <div className="ml-3 flex-1">
          <p className="text-sm text-blue-700">
            This range is an instance of{' '}
            <Link
              to={`/blueprints/${blueprint.id}`}
              className="font-medium underline hover:text-blue-800"
            >
              {blueprint.name}
            </Link>{' '}
            (v{instance.blueprint_version})
            {isOutdated && (
              <span className="ml-2 text-amber-600">
                — Latest is v{blueprint.version}
              </span>
            )}
          </p>
          <div className="mt-2 flex space-x-3">
            <Link
              to={`/blueprints/${blueprint.id}`}
              className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
            >
              <ExternalLink className="h-3.5 w-3.5 mr-1" />
              View Blueprint
            </Link>
            {isOutdated && onRedeploy && (
              <button
                onClick={onRedeploy}
                className="inline-flex items-center text-sm text-amber-600 hover:text-amber-800"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1" />
                Redeploy from v{blueprint.version}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
