// Interruptor "tem data final?" + o campo de data, que só aparece se ligado.
// value: "" (sem data) ou "YYYY-MM-DD". suggest: a data que aparece ao ligar.
export default function EndDateField({ value, onChange, min, suggest }) {
  const enabled = value !== "" && value != null;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <label className="toggle">
        <input type="checkbox" role="switch" checked={enabled}
          onChange={(e) => onChange(e.target.checked ? (suggest || min) : "")} />
        <span>Tem data final</span>
      </label>
      {enabled ? (
        <label>
          Último dia do álbum
          <input type="date" value={value} min={min} onChange={(e) => onChange(e.target.value)} required />
        </label>
      ) : (
        <p className="muted small">Sem data final: o álbum fica aberto até alguém encerrar.</p>
      )}
    </div>
  );
}
