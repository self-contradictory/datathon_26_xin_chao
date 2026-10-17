import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'

type ButtonVariant = 'primary' | 'secondary'

const BASE =
  'inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-md px-5 text-body font-semibold whitespace-nowrap no-underline transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60'

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-hover active:bg-brand-hover',
  secondary:
    'border border-border bg-bg text-text hover:bg-surface active:bg-surface',
}

function buttonClass(variant: ButtonVariant = 'primary', extra = ''): string {
  return `${BASE} ${VARIANTS[variant]} ${extra}`.trim()
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  icon?: ReactNode
  ref?: Ref<HTMLButtonElement>
}

export function Button({
  variant = 'primary',
  icon,
  className = '',
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button type={type} className={buttonClass(variant, className)} {...rest}>
      {icon}
      {children}
    </button>
  )
}
