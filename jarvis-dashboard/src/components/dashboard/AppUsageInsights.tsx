import { useState, useEffect } from 'react';

interface AppUsage {
  app: string;
  duration: number;
  sessions: number;
}

export function AppUsageInsights() {
  const [usage, setUsage] = useState<AppUsage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/activity/today')
      .then(r => r.json())
      .then(data => {
        setUsage(data.apps || []);
        setLoading(false);
      })
      .catch(() => {
        setUsage([]);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="text-text-secondary text-sm">Loading...</div>;

  return (
    <div className="space-y-2">
      <h3 className="font-mono text-xs uppercase text-text-secondary tracking-wider">
        TODAY'S ACTIVITY
      </h3>
      {usage.length === 0 ? (
        <p className="text-text-secondary text-sm">No activity captured yet</p>
      ) : (
        <div className="space-y-1">
          {usage.slice(0, 5).map(app => (
            <div key={app.app} className="flex justify-between items-center text-sm">
              <span className="text-text-primary">{app.app}</span>
              <span className="text-text-secondary">{app.duration}m</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
