import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { AuthForm } from "../components/AuthForm";


export default async function SignInPage() {
  const session = await auth();
  if (session?.user?.id) redirect("/");
  return <AuthForm />;
}
