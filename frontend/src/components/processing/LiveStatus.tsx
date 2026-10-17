import { useEffect, useState } from 'react'

export function LiveStatus({ message }: { message: string }) {
  const [shown, setShown] = useState('')
  useEffect(() => {
    const id = setTimeout(() => setShown(message), 100)
    return () => clearTimeout(id)
  }, [message])

  return (
    <p role="status" className="sr-only">
      {shown}
    </p>
  )
}
