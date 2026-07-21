import { signIn } from "@/auth";
import { isOidcConfigured, isOidcPartiallyConfigured } from "@/lib/auth-status";

const ERROR_MESSAGES: Record<string, string> = {
  AccessDenied: "Your account isn't a member of the required group.",
  Configuration: "Authentication is not correctly configured. Contact the administrator.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; callbackUrl?: string }>;
}) {
  const params = await searchParams;

  if (isOidcPartiallyConfigured()) {
    return (
      <Shell>
        <p className="text-sm text-red-600">
          Authentication is not correctly configured. Contact the administrator.
        </p>
      </Shell>
    );
  }

  if (!isOidcConfigured()) {
    return (
      <Shell>
        <p className="text-sm text-slate-600">
          Login is not required — this deployment does not have OIDC configured.
        </p>
      </Shell>
    );
  }

  const providerName = process.env.OIDC_PROVIDER_NAME || "Single Sign-On";
  const errorMessage = params.error ? (ERROR_MESSAGES[params.error] ?? "Sign-in failed. Please try again.") : null;
  const callbackUrl = params.callbackUrl || "/";

  return (
    <Shell>
      {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}
      <form
        action={async () => {
          "use server";
          await signIn("oidc", { redirectTo: callbackUrl });
        }}
      >
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Continue with {providerName}
        </button>
      </form>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold text-slate-900">Firefly III Assistant</h1>
      {children}
    </main>
  );
}
