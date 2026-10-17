import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <main className="flex min-h-svh items-center justify-center bg-slate-950 px-6 py-12 text-slate-100">
      <section className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 p-8 sm:p-12">
        <p className="text-sm font-medium text-emerald-400">Datathon 2026</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
          Xin Chao
        </h1>
        <p className="mt-5 leading-relaxed text-slate-300">
          Frontend starter with Bun, React, TypeScript, and Tailwind CSS.
        </p>
        <button
          type="button"
          className="mt-8 cursor-pointer rounded-lg bg-emerald-400 px-5 py-3 font-medium text-slate-950 transition-colors hover:bg-emerald-300 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
          onClick={() => setCount((value) => value + 1)}
        >
          Count is {count}
        </button>
      </section>
    </main>
  )
}

export default App
