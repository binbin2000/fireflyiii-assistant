import { signOut } from "@/auth";

export function SignOutButton({ label }: { label: string }) {
  return (
    <form
      action={async () => {
        "use server";
        await signOut();
      }}
    >
      <button
        type="submit"
        className="text-xs font-medium text-slate-500 hover:text-slate-800"
      >
        Sign out ({label})
      </button>
    </form>
  );
}
