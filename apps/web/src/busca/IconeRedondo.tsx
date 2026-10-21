import type { Icon } from '@phosphor-icons/react'

export function IconeRedondo({ icon: Icone, tom = 'agua' }: { icon: Icon; tom?: 'agua' | 'amarelo' | 'cinza' }) {
  return (
    <span className={`ga-icone ga-icone--${tom}`}>
      <Icone size={19} weight="duotone" aria-hidden="true" />
    </span>
  )
}
