// Textos de status de um álbum, iguais em todas as telas.

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

export function albumStatus(a) {
  if (a.status === "ended") return `Encerrado · durou ${plural(a.day_number, "dia", "dias")}`;
  if (a.days_left === 0) return "Último dia!";
  if (a.days_left != null) return `Faltam ${plural(a.days_left, "dia", "dias")}`;
  return `Dia ${a.day_number}`; // sem data final: só conta os dias
}

// "YYYY-MM-DD" do dia local daqui a N dias. (toISOString() usa UTC: em Cuiabá,
// depois das 20h ele já estaria no dia seguinte.)
export function localDay(offset = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function formatDay(iso) {
  return new Date(iso + "T12:00").toLocaleDateString("pt-BR", { day: "numeric", month: "short", year: "numeric" });
}
