interface Track {
  name: string
  progress: number
  status: string
}

const tracks: Track[] = [
  { name: 'Series B Fundraise', progress: 72, status: 'On Track' },
  { name: 'Product V2 Launch', progress: 45, status: 'At Risk' },
  { name: 'Team Expansion', progress: 88, status: 'Ahead' },
]

function ProgressBar({ progress, status }: { progress: number; status: string }) {
  const color =
    status === 'At Risk'
      ? 'bg-warning'
      : status === 'Ahead'
        ? 'bg-success'
        : 'bg-accent'

  return (
    <div className="w-full bg-border/50 h-1.5 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${progress}%` }}
      />
    </div>
  )
}

export function ActiveTracks() {
  return (
    <div>
      <h3 className="section-title">ACTIVE TRACKS</h3>

      <div className="space-y-0">
        {tracks.map((track) => (
          <div
            key={track.name}
            className="py-3.5 border-b border-border/50 last:border-b-0"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-[14px] text-text-primary">{track.name}</p>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[12px] text-text-secondary">
                  {track.progress}%
                </span>
                <span
                  className={`text-[11px] font-mono tracking-wider ${
                    track.status === 'At Risk'
                      ? 'text-warning'
                      : track.status === 'Ahead'
                        ? 'text-success'
                        : 'text-accent'
                  }`}
                >
                  {track.status.toUpperCase()}
                </span>
              </div>
            </div>
            <ProgressBar progress={track.progress} status={track.status} />
          </div>
        ))}
      </div>
    </div>
  )
}
