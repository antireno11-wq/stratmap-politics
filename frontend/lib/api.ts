const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getRanking(query = "") {
  const response = await fetch(`${API_URL}/api/v1/ranking${query ? `?${query}` : ""}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Error cargando ranking");
  return response.json();
}

export async function getDeputy(id: string) {
  const response = await fetch(`${API_URL}/api/v1/deputies/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Diputado no encontrado");
  return response.json();
}
