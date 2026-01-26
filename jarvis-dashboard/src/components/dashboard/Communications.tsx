export function Communications() {
  const items = [
    { label: 'Unread Volume', value: '23', trend: '+5 today' },
    { label: 'Priority Threads', value: '4', trend: '2 urgent' },
    { label: 'Avg Response Time', value: '12m', trend: '-3m from avg' },
  ]

  return (
    <div>
      <h3 className="section-title">COMMUNICATIONS</h3>

      <div className="space-y-0">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex items-center justify-between py-3.5 border-b border-border/50 last:border-b-0"
          >
            <div>
              <p className="text-[14px] text-text-primary">{item.label}</p>
              <p className="text-[11px] text-text-secondary mt-0.5">{item.trend}</p>
            </div>
            <span className="font-mono text-xl font-bold text-text-primary">
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
