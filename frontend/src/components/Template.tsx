import { Fragment, type ReactNode } from 'react'

export function Template({
  text,
  values,
}: {
  text: string
  values: Record<string, ReactNode>
}) {
  const parts = text.split(/\{(\w+)\}/)
  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>
          {index % 2 === 0 ? part : (values[part] ?? `{${part}}`)}
        </Fragment>
      ))}
    </>
  )
}
