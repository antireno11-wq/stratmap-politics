import { redirect } from "next/navigation";

export default function LegacyDeputyPage({ params }: any) {
  redirect(`/parliamentarians/${params.id}`);
}
