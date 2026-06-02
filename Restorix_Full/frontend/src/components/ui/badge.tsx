import { cn } from "@/lib/utils"

interface BadgeProps {
  children: React.ReactNode
  variant?: "default" | "success" | "warning" | "destructive" | "secondary"
  className?: string
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  const variants = {
    default: "bg-primary/10 text-primary",
    success: "bg-green-100 text-green-700",
    warning: "bg-yellow-100 text-yellow-700",
    destructive: "bg-red-100 text-red-700",
    secondary: "bg-muted text-muted-foreground",
  }
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  )
}
