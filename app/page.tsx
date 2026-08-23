import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { OperatorShell } from "./components/OperatorShell";


export default async function Home() {
  const session = await auth();
  if (!session?.user?.id || !session.user.email) redirect("/sign-in");
  return <OperatorShell account={{ id: session.user.id, email: session.user.email, name: session.user.name || session.user.email }} />;
}
