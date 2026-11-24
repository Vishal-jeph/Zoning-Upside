import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const metadata = { title: "Sign in — Zoning Upside" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string; error?: string }> }) {
  const { next = "/", error } = await searchParams;
  return (
    <div className="grid flex-1 place-items-center bg-slate-50 p-6">
      <form method="POST" action="/api/login" className="w-full max-w-sm space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <div>
          <h1 className="text-lg font-semibold">Zoning Upside</h1>
          <p className="text-sm text-slate-600">This preview is password protected.</p>
        </div>
        <input type="hidden" name="next" value={next} />
        <Input type="password" name="password" placeholder="Password" autoFocus required />
        {error && <p className="text-sm text-red-600">Incorrect password.</p>}
        <Button type="submit" className="w-full">Continue</Button>
      </form>
    </div>
  );
}
