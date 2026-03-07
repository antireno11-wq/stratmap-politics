import { redirect } from "next/navigation";

export default function LegacyDeputyPage({ params }: { params: { id: string } }) {
  redirect(`/parliamentarians/${params.id}`);
}
