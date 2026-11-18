"use client"

import { CircleAlert, LogIn } from "lucide-react"
import { useState, type FormEvent } from "react"

import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { ApiError, MESSAGES } from "@/lib/api"

export function LoginForm({ expired = false }: { expired?: boolean }) {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(
    expired ? "Din session har gått ut. Logga in igen." : null,
  )
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(username, password)
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : MESSAGES.loginFailed)
      setPassword("")
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-6" aria-labelledby="login-title">
        <div className="space-y-2">
          <h1 id="login-title" className="text-2xl font-semibold tracking-tight">
            Logga in
          </h1>
          <p className="text-sm text-muted-foreground">
            Compileit-assistenten svarar på frågor om compileit.com. Dina konversationer sparas på
            ditt konto.
          </p>
        </div>

        {error && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            {error}
          </p>
        )}

        <div className="space-y-4">
          <Field
            id="username"
            label="Användarnamn"
            value={username}
            onChange={setUsername}
            autoComplete="username"
            autoFocus
          />
          <Field
            id="password"
            label="Lösenord"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />
        </div>

        <Button
          type="submit"
          className="h-10 w-full"
          disabled={submitting || !username.trim() || !password}
        >
          <LogIn aria-hidden />
          {submitting ? "Loggar in…" : "Logga in"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Saknar du konto? Kontakta en administratör.
        </p>
      </form>
    </main>
  )
}

function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  autoFocus = false,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  autoComplete: string
  autoFocus?: boolean
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        autoCapitalize="none"
        spellCheck={false}
        required
        className="h-10 w-full rounded-lg border border-input bg-transparent px-3 text-base transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm dark:bg-input/30"
      />
    </div>
  )
}
