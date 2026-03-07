const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getParliamentarians(query = "") {
  const response = await fetch(`${API_URL}/api/v1/parliamentarians${query ? `?${query}` : ""}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Error cargando parlamentarios");
  return response.json();
}

export async function getParliamentarian(id: string) {
  const response = await fetch(`${API_URL}/api/v1/parliamentarians/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Parlamentario no encontrado");
  return response.json();
}
