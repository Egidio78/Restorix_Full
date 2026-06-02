import { LucideIcon } from 'lucide-react'


interface ComingSoonProps {
  icon: LucideIcon
  title: string
  description: string
  features?: string[]
}

export function ComingSoon({ icon: Icon, title, description, features }: ComingSoonProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="bg-primary/10 rounded-full p-6 mb-6">
        <Icon className="h-12 w-12 text-primary" />
      </div>
      <h1 className="text-2xl font-bold mb-2">{title}</h1>
      <p className="text-muted-foreground max-w-md mb-6">{description}</p>
      {features && features.length > 0 && (
        <div className="bg-muted/50 rounded-lg p-4 text-left max-w-sm w-full">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Funzionalità in arrivo</p>
          <ul className="space-y-2">
            {features.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm">
                <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-8 inline-flex items-center gap-2 bg-primary/5 border border-primary/20 rounded-full px-4 py-2">
        <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
        <span className="text-sm text-primary font-medium">In sviluppo — Piano 2</span>
      </div>
    </div>
  )
}
