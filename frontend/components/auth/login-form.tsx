"use client"

import { CircleAlert, Loader2 } from "lucide-react"
import { useState, type FormEvent } from "react"

import { useAuth } from "@/components/auth/auth-provider"
import { BrandMark } from "@/components/brand"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-muted/40 px-4 py-10">
      <div className="bg-dots pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 size-[36rem] -translate-x-1/2 rounded-full bg-brand/15 blur-3xl" />
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <BrandMark size="lg" />
          <div>
            <p className="font-semibold tracking-tight">Compileit-assistenten</p>
            <p className="text-sm text-muted-foreground">Svar med källor från compileit.com</p>
          </div>
        </div>

        <Card className="shadow-xl shadow-black/5">
          <CardHeader>
            <CardTitle id="login-title" className="text-xl">
              Logga in
            </CardTitle>
            <CardDescription>Dina konversationer sparas på ditt konto.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4" aria-labelledby="login-title">
              {error && (
                <p
                  role="alert"
                  className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
                >
                  <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {error}
                </p>
              )}
              <div className="space-y-2">
                <Label htmlFor="username">Användarnamn</Label>
                <Input
                  id="username"
                  name="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  autoFocus
                  required
                  className="h-10"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Lösenord</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                  className="h-10"
                />
              </div>
              <Button
                type="submit"
                className="h-10 w-full"
                disabled={submitting || !username.trim() || !password}
              >
                {submitting && <Loader2 className="animate-spin" aria-hidden />}
                {submitting ? "Loggar in…" : "Logga in"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          Saknar du konto? Kontakta en administratör.
        </p>
      </div>
    </main>
  )
}
