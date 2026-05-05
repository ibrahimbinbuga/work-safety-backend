import { X, AlertTriangle, HardHat, ShieldAlert } from 'lucide-react';

const VIOLATION_CONFIG = {
  head:   { label: 'No Helmet',      color: 'bg-red-500',    icon: HardHat },
  vest:   { label: 'No Vest',        color: 'bg-orange-500', icon: ShieldAlert },
  fall:   { label: 'Worker Fell',    color: 'bg-purple-600', icon: AlertTriangle },
  fallen: { label: 'Worker Fell',    color: 'bg-purple-600', icon: AlertTriangle },
};

function ViolationToastItem({ notification, onDismiss }) {
  const config = VIOLATION_CONFIG[notification.violation_type] || {
    label: notification.violation_type,
    color: 'bg-gray-700',
    icon: AlertTriangle,
  };
  const Icon = config.icon;

  return (
    <div className="flex items-start gap-3 bg-white border border-gray-200 rounded-xl shadow-lg p-4 w-80 animate-slide-in">
      <div className={`${config.color} rounded-lg p-2 shrink-0`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900">Safety Violation</p>
        <p className="text-sm text-gray-600">{config.label}</p>
        <p className="text-xs text-gray-400 mt-0.5 truncate">
          Camera: {notification.camera_location || notification.camera_id}
        </p>
      </div>
      <button
        onClick={() => onDismiss(notification.id)}
        className="shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function ViolationToast({ notifications, onDismiss }) {
  if (!notifications.length) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
      {notifications.map((n) => (
        <div key={n.id} className="pointer-events-auto">
          <ViolationToastItem notification={n} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
