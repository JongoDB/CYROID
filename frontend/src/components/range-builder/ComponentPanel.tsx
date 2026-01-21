// frontend/src/components/range-builder/ComponentPanel.tsx
import { Network, Server } from 'lucide-react'
import clsx from 'clsx'
import type { BaseImage } from '../../types'

interface ComponentPanelProps {
  baseImages: BaseImage[]
}

export function ComponentPanel({ baseImages }: ComponentPanelProps) {
  const onDragStart = (
    event: React.DragEvent,
    type: string,
    baseImageId?: string
  ) => {
    event.dataTransfer.setData('application/reactflow/type', type)
    if (baseImageId) {
      event.dataTransfer.setData('application/reactflow/baseImageId', baseImageId)
    }
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="w-56 bg-gray-50 border-r border-gray-200 p-4 overflow-y-auto">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Components</h3>
      
      {/* Network Component */}
      <div className="mb-4">
        <h4 className="text-xs font-medium text-gray-500 mb-2">Infrastructure</h4>
        <div
          className="p-3 bg-white border border-gray-200 rounded-lg cursor-grab hover:border-primary-400 hover:shadow-sm transition-all"
          draggable
          onDragStart={(e) => onDragStart(e, 'network')}
        >
          <div className="flex items-center gap-2">
            <Network className="w-5 h-5 text-gray-600" />
            <div>
              <div className="text-sm font-medium text-gray-900">Network</div>
              <div className="text-xs text-gray-500">Add subnet segment</div>
            </div>
          </div>
        </div>
      </div>

      {/* Base Images */}
      <div>
        <h4 className="text-xs font-medium text-gray-500 mb-2">Base Images</h4>
        <div className="space-y-2">
          {baseImages.map((image) => (
            <div
              key={image.id}
              className="p-3 bg-white border border-gray-200 rounded-lg cursor-grab hover:border-primary-400 hover:shadow-sm transition-all"
              draggable
              onDragStart={(e) => onDragStart(e, 'vm', image.id)}
            >
              <div className="flex items-center gap-2">
                <Server className={clsx(
                  'w-5 h-5',
                  image.os_type === 'linux' ? 'text-orange-600' :
                  image.os_type === 'windows' ? 'text-blue-600' : 'text-gray-600'
                )} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {image.name}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {image.image_type === 'container' ? 'Container' : 'ISO'} • {image.os_type}
                  </div>
                </div>
              </div>
              <div className="mt-1 flex gap-2 text-[10px] text-gray-400">
                <span>{image.default_cpu} CPU</span>
                <span>{image.default_ram_mb / 1024}GB RAM</span>
              </div>
            </div>
          ))}
          {baseImages.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-4">
              No base images available
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
