import { useState, useCallback, useEffect } from "react";

// ── Config API ───────────────────────────────────────────
// ⚠️ Adaptez si votre backend tourne ailleurs qu'en local sur le port 8000
const API_BASE = "http://localhost:8000";

// ── Design tokens (cohérents avec la page de résa) ──────
const T = {
  navy:    "#0F1B2D",
  teal:    "#1A7F72",
  tealLt:  "#E8F5F3",
  tealMid: "#B2DDD8",
  slate:   "#4A5568",
  border:  "#D1DCE8",
  white:   "#FFFFFF",
  cream:   "#F8FAFB",
  amber:   "#D97706",
  amberLt: "#FEF3C7",
  red:     "#C0392B",
  redLt:   "#FDECEA",
};

// ── Utilitaires ─────────────────────────────────────────
const fmt  = dt => new Date(dt).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const fmtD = dt => new Date(dt).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });

const STATUS = {
  confirmed: { label: "Confirmé",  bg: T.tealLt,  color: T.teal,  dot: T.teal  },
  pending:   { label: "En attente",bg: T.amberLt, color: T.amber, dot: T.amber },
  no_show:   { label: "Absent",    bg: T.redLt,   color: T.red,   dot: T.red   },
  done:      { label: "Terminé",   bg: "#F0F0F0", color: T.slate, dot: T.slate },
  cancelled: { label: "Annulé",    bg: "#F0F0F0", color: T.slate, dot: T.slate },
};

// ── Composants UI ────────────────────────────────────────

function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.done;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      background: s.bg, color: s.color,
      fontSize: 11, fontWeight: 700, letterSpacing: "0.05em",
      textTransform: "uppercase", padding: "3px 10px",
      borderRadius: 99,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.dot }} />
      {s.label}
    </span>
  );
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: T.white, border: `1px solid ${T.border}`,
      borderRadius: 14, padding: "1.25rem 1.5rem",
      borderLeft: `4px solid ${accent || T.teal}`,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, color: T.navy, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: T.slate, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function MiniBar({ data }) {
  const max = Math.max(...data.map(d => d.total));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 80, marginTop: 12 }}>
      {data.map(d => (
        <div key={d.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <div style={{ width: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end", height: 60, gap: 2 }}>
            <div style={{
              width: "100%", borderRadius: "4px 4px 0 0",
              height: `${(d.no_show / max) * 60}px`,
              background: T.red, opacity: 0.7,
            }} />
            <div style={{
              width: "100%", borderRadius: d.no_show ? 0 : "4px 4px 0 0",
              height: `${((d.total - d.no_show) / max) * 60}px`,
              background: T.teal,
            }} />
          </div>
          <span style={{ fontSize: 10, color: T.slate, fontWeight: 600 }}>{d.day}</span>
        </div>
      ))}
    </div>
  );
}

function AppointmentRow({ appt, onAction }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      padding: "0.9rem 1.25rem",
      borderBottom: `1px solid ${T.border}`,
      display: "flex", alignItems: "center", gap: 12,
      transition: "background 0.15s",
      background: open ? T.cream : T.white,
    }}>
      {/* Avatar */}
      <div style={{
        width: 38, height: 38, borderRadius: "50%",
        background: T.tealLt, color: T.teal,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 13, fontWeight: 700, flexShrink: 0,
      }}>
        {appt.patient_name.split(" ").map(n => n[0]).join("")}
      </div>
      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: T.navy, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {appt.patient_name}
        </div>
        <div style={{ fontSize: 12, color: T.slate }}>
          {fmt(appt.start_time)} – {fmt(appt.end_time)}
        </div>
      </div>
      <StatusBadge status={appt.status} />
      {/* Actions */}
      {appt.status === "confirmed" && (
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button onClick={() => onAction(appt.id, "complete")} style={btnStyle(T.teal)}>✓</button>
          <button onClick={() => onAction(appt.id, "no_show")} style={btnStyle(T.amber)}>–</button>
          <button onClick={() => onAction(appt.id, "cancel")} style={btnStyle(T.red)}>✕</button>
        </div>
      )}
    </div>
  );
}

const btnStyle = (color) => ({
  width: 28, height: 28, border: `1px solid ${color}`,
  borderRadius: 7, background: "transparent", color,
  cursor: "pointer", fontSize: 12, fontWeight: 700,
  display: "flex", alignItems: "center", justifyContent: "center",
  transition: "all 0.15s",
});

// ── États partagés (chargement / erreur) ─────────────────
function LoadingState({ label = "Chargement…" }) {
  return (
    <div style={{ padding: "3rem", textAlign: "center", color: T.slate, fontSize: 13 }}>
      {label}
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div style={{
      padding: "2rem", textAlign: "center",
      background: T.redLt, border: `1px solid ${T.red}`, borderRadius: 12,
    }}>
      <p style={{ color: T.red, fontSize: 13, marginBottom: 12 }}>{message}</p>
      {onRetry && (
        <button onClick={onRetry} style={{
          padding: "0.5rem 1.1rem", border: `1px solid ${T.red}`, borderRadius: 8,
          background: "transparent", color: T.red, cursor: "pointer",
          fontSize: 12, fontWeight: 700,
        }}>
          Réessayer
        </button>
      )}
    </div>
  );
}

const inputStyle = {
  padding: "0.65rem 0.9rem", border: `1px solid ${T.border}`, borderRadius: 8,
  fontSize: 14, fontFamily: "inherit", outline: "none", width: "100%",
  boxSizing: "border-box",
};

// ── Écran de connexion ───────────────────────────────────
function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/token/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Identifiants invalides.");
      }
      const data = await res.json();
      onLogin({ access: data.access, refresh: data.refresh });
    } catch (err) {
      setError(err.message || "Impossible de se connecter à l'API. Vérifiez que le backend tourne et que CORS est bien configuré.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif",
    }}>
      <form onSubmit={submit} style={{
        background: T.white, border: `1px solid ${T.border}`, borderRadius: 14,
        padding: "2rem", width: 320, display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ fontFamily: "Georgia, serif", fontSize: "1.5rem", color: T.navy, textAlign: "center", marginBottom: 4 }}>
          Cabin<span style={{ color: T.teal }}>Book</span>
        </div>
        <input type="email" placeholder="Email" value={email}
          onChange={e => setEmail(e.target.value)} required style={inputStyle} />
        <input type="password" placeholder="Mot de passe" value={password}
          onChange={e => setPassword(e.target.value)} required style={inputStyle} />
        {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.75rem", fontSize: 14, fontWeight: 700,
          cursor: loading ? "default" : "pointer", opacity: loading ? 0.7 : 1,
        }}>
          {loading ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}

// ── Sidebar nav ──────────────────────────────────────────
const NAV = [
  { id: "dashboard", icon: "⬛", label: "Tableau de bord" },
  { id: "agenda",    icon: "📅", label: "Agenda"          },
  { id: "patients",  icon: "👥", label: "Patients"        },
  { id: "settings",  icon: "⚙️",  label: "Paramètres"     },
];

function Sidebar({ active, onNav, onLogout, userLabel }) {
  return (
    <aside style={{
      width: 220, background: T.navy, flexShrink: 0,
      display: "flex", flexDirection: "column",
      minHeight: "100vh", padding: "0 0 2rem",
    }}>
      {/* Logo */}
      <div style={{ padding: "1.5rem 1.25rem 2rem", borderBottom: `1px solid rgba(255,255,255,0.08)` }}>
        <span style={{
          fontFamily: "Georgia, serif", fontSize: "1.35rem",
          color: T.white, letterSpacing: "-0.02em",
        }}>
          Cabin<span style={{ color: "#5DD6C8" }}>Book</span>
        </span>
      </div>
      {/* Nav */}
      <nav style={{ flex: 1, padding: "1rem 0.75rem" }}>
        {NAV.map(n => (
          <button key={n.id} onClick={() => onNav(n.id)} style={{
            width: "100%", display: "flex", alignItems: "center", gap: 10,
            padding: "0.65rem 0.75rem", borderRadius: 10, border: "none",
            background: active === n.id ? "rgba(26,127,114,0.25)" : "transparent",
            color: active === n.id ? "#5DD6C8" : "rgba(255,255,255,0.55)",
            fontSize: 13.5, fontWeight: active === n.id ? 600 : 400,
            cursor: "pointer", marginBottom: 2, textAlign: "left",
            transition: "all 0.15s",
          }}>
            <span style={{ fontSize: 15 }}>{n.icon}</span>
            {n.label}
          </button>
        ))}
      </nav>
      {/* User */}
      <button onClick={onLogout} title="Se déconnecter" style={{
        margin: "0 0.75rem",
        padding: "0.75rem 0.75rem",
        borderRadius: 10,
        background: "rgba(255,255,255,0.06)",
        display: "flex", alignItems: "center", gap: 10,
        border: "none", cursor: "pointer", textAlign: "left",
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: "50%",
          background: T.teal, color: T.white,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 700, flexShrink: 0,
        }}>
          {(userLabel || "?").slice(0, 2).toUpperCase()}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12.5, color: T.white, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {userLabel || "Utilisateur"}
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>Se déconnecter</div>
        </div>
      </button>
    </aside>
  );
}

// ── Vue Dashboard ────────────────────────────────────────
function getWeekRange() {
  const now = new Date();
  const day = now.getDay(); // 0=dim, 1=lun, ...
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + diffToMonday);
  monday.setHours(0, 0, 0, 0);
  const friday = new Date(monday);
  friday.setDate(monday.getDate() + 4);
  friday.setHours(23, 59, 59, 999);
  return { monday, friday };
}

function DashboardView({ apiFetch, userLabel }) {
  const [stats, setStats] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [week, setWeek] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsData, todayData] = await Promise.all([
        apiFetch("/api/appointments/stats/"),
        apiFetch("/api/appointments/today/"),
      ]);
      setStats(statsData);
      setAppointments(todayData);

      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(0, 0, 0, 0);
      const upcomingData = await apiFetch(
        `/api/appointments/?date_from=${encodeURIComponent(tomorrow.toISOString())}&ordering=start_time`
      );
      setUpcoming((upcomingData || []).filter(a => a.status !== "cancelled").slice(0, 5));

      const { monday, friday } = getWeekRange();
      const weekData = await apiFetch(
        `/api/appointments/?date_from=${encodeURIComponent(monday.toISOString())}&date_to=${encodeURIComponent(friday.toISOString())}&ordering=start_time`
      );
      const labels = ["Lun", "Mar", "Mer", "Jeu", "Ven"];
      const buckets = labels.map(d => ({ day: d, total: 0, no_show: 0 }));
      (weekData || []).forEach(a => {
        if (a.status === "cancelled") return;
        const idx = new Date(a.start_time).getDay() - 1;
        if (idx >= 0 && idx < 5) {
          buckets[idx].total += 1;
          if (a.status === "no_show") buckets[idx].no_show += 1;
        }
      });
      setWeek(buckets);
    } catch (err) {
      setError(err.message || "Erreur de chargement des données.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleAction = useCallback(async (id, action) => {
    try {
      await apiFetch(`/api/appointments/${id}/${action}/`, { method: "POST" });
      loadAll();
    } catch (err) {
      setError(err.message || "Action impossible.");
    }
  }, [apiFetch, loadAll]);

  if (loading) return <LoadingState label="Chargement du tableau de bord…" />;
  if (error) return <ErrorState message={error} onRetry={loadAll} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: T.navy }}>Bonjour, {userLabel || ""} 👋</h1>
        <p style={{ fontSize: 13, color: T.slate, marginTop: 2 }}>
          {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        <StatCard label="RDV ce mois"      value={stats.total_month}    sub="depuis le 1er du mois"     accent={T.teal}  />
        <StatCard label="À venir aujourd'hui" value={stats.upcoming_today} sub="prochains créneaux"      accent="#2563EB" />
        <StatCard label="Confirmés"        value={stats.confirmed}      sub="rendez-vous confirmés"      accent={T.amber} />
        <StatCard label="No-shows ce mois" value={stats.no_shows_month}
          sub={stats.total_month ? `${Math.round(stats.no_shows_month / stats.total_month * 100)}% des RDV` : "—"}
          accent={T.red} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>
        <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden" }}>
          <div style={{ padding: "1rem 1.25rem", borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>Rendez-vous du jour</span>
            <span style={{ fontSize: 11, color: T.slate, background: T.cream, padding: "3px 10px", borderRadius: 99, fontWeight: 600 }}>
              {appointments.filter(a => a.status === "confirmed").length} confirmés
            </span>
          </div>
          {appointments.length === 0 && (
            <div style={{ padding: "1.5rem 1.25rem", fontSize: 13, color: T.slate }}>Aucun rendez-vous aujourd'hui.</div>
          )}
          {appointments.map(a => (
            <AppointmentRow key={a.id} appt={a} onAction={handleAction} />
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1rem 1.25rem" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>Activité de la semaine</div>
            <div style={{ fontSize: 11, color: T.slate, display: "flex", gap: 12 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: T.teal, display: "inline-block" }} /> Présents
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: T.red, opacity: 0.7, display: "inline-block" }} /> Absents
              </span>
            </div>
            <MiniBar data={week.length ? week : [{ day: "Lun", total: 0, no_show: 0 }]} />
          </div>

          <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden" }}>
            <div style={{ padding: "0.9rem 1.25rem", borderBottom: `1px solid ${T.border}`, fontSize: 13, fontWeight: 700, color: T.navy }}>
              Prochains rendez-vous
            </div>
            {upcoming.length === 0 && (
              <div style={{ padding: "1rem 1.25rem", fontSize: 12, color: T.slate }}>Aucun rendez-vous à venir.</div>
            )}
            {upcoming.map(a => (
              <div key={a.id} style={{
                padding: "0.7rem 1.25rem",
                borderBottom: `1px solid ${T.border}`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.navy }}>{a.patient_name}</div>
                  <div style={{ fontSize: 11, color: T.slate }}>{fmtD(a.start_time)} · {fmt(a.start_time)}</div>
                </div>
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AgendaView({ apiFetch }) {
  const hours = Array.from({ length: 10 }, (_, i) => i + 8);
  const { monday, friday } = getWeekRange();
  const days = Array.from({ length: 5 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d.toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit" });
  });

  const [placed, setPlaced] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiFetch(
      `/api/appointments/?date_from=${encodeURIComponent(monday.toISOString())}&date_to=${encodeURIComponent(friday.toISOString())}&ordering=start_time`
    )
      .then(data => {
        if (!active) return;
        const events = (data || [])
          .filter(a => a.status !== "cancelled")
          .map(a => {
            const start = new Date(a.start_time);
            const end = new Date(a.end_time);
            const dayIdx = start.getDay() - 1;
            const startHour = start.getHours() + start.getMinutes() / 60;
            const durationH = Math.max((end - start) / 3600000, 0.25);
            return { day: dayIdx, start: startHour, duration: durationH, patient: a.patient_name, status: a.status };
          })
          .filter(ev => ev.day >= 0 && ev.day < 5);
        setPlaced(events);
      })
      .catch(err => { if (active) setError(err.message || "Erreur de chargement de l'agenda."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch]);

  const CELL_H = 56;

  if (loading) return <LoadingState label="Chargement de l'agenda…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: T.navy, marginBottom: 16 }}>
        Agenda — semaine du {monday.toLocaleDateString("fr-FR", { day: "numeric", month: "long" })}
      </h1>
      <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "52px repeat(5, 1fr)", borderBottom: `1px solid ${T.border}` }}>
          <div />
          {days.map(d => (
            <div key={d} style={{ padding: "0.6rem 0.5rem", textAlign: "center", fontSize: 12, fontWeight: 700, color: T.slate, borderLeft: `1px solid ${T.border}` }}>
              {d}
            </div>
          ))}
        </div>
        <div style={{ position: "relative" }}>
          <div style={{ display: "grid", gridTemplateColumns: "52px repeat(5, 1fr)" }}>
            {hours.map(h => (
              <div key={`row-${h}`} style={{ display: "contents" }}>
                <div style={{ height: CELL_H, borderBottom: `1px solid ${T.border}`, padding: "4px 6px", fontSize: 10, color: T.slate, fontWeight: 600 }}>
                  {h}:00
                </div>
                {days.map((_, di) => (
                  <div key={`${h}-${di}`} style={{ height: CELL_H, borderBottom: `1px solid ${T.border}`, borderLeft: `1px solid ${T.border}` }} />
                ))}
              </div>
            ))}
          </div>
          {placed.map((ev, i) => {
            const s = STATUS[ev.status];
            const top  = (ev.start - 8) * CELL_H + 2;
            return (
              <div key={i} style={{
                position: "absolute",
                top, left: `calc(52px + ${ev.day} * (100% - 52px) / 5 + 4px)`,
                width: "calc((100% - 52px) / 5 - 8px)",
                height: ev.duration * CELL_H - 4,
                background: s.bg, border: `1px solid ${s.dot}`,
                borderLeft: `3px solid ${s.dot}`,
                borderRadius: 7, padding: "4px 8px", overflow: "hidden",
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: s.color }}>{ev.patient}</div>
                <div style={{ fontSize: 10, color: s.color, opacity: 0.8 }}>{ev.start}:00</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function PatientsView({ apiFetch }) {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/api/accounts/patients/");
      setPatients(data || []);
    } catch (err) {
      setError(err.message || "Erreur de chargement des patients.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => { load(); }, [load]);

  const filtered = patients.filter(p =>
    `${p.first_name} ${p.last_name}`.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <LoadingState label="Chargement des patients…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: T.navy }}>Patients</h1>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Rechercher un patient…"
          style={{
            padding: "0.55rem 1rem", border: `1px solid ${T.border}`,
            borderRadius: 10, fontSize: 13, outline: "none",
            fontFamily: "inherit", width: 220, background: T.white,
          }}
        />
      </div>
      <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1.5fr 2fr 1.3fr 1.5fr 100px",
          padding: "0.6rem 1.25rem", borderBottom: `1px solid ${T.border}`,
          fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          <span>Nom</span><span>Email</span><span>Téléphone</span><span>Praticien</span><span>Créé le</span>
        </div>
        {filtered.length === 0 && (
          <div style={{ padding: "1.25rem", fontSize: 13, color: T.slate }}>Aucun patient trouvé.</div>
        )}
        {filtered.map(p => (
          <div key={p.id} style={{
            display: "grid", gridTemplateColumns: "1.5fr 2fr 1.3fr 1.5fr 100px",
            padding: "0.85rem 1.25rem", borderBottom: `1px solid ${T.border}`,
            fontSize: 13, alignItems: "center",
          }}>
            <span style={{ fontWeight: 600, color: T.navy }}>{p.first_name} {p.last_name}</span>
            <span style={{ color: T.slate, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.email}</span>
            <span style={{ color: T.slate }}>{p.phone}</span>
            <span style={{ color: T.slate, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.practitioner_name}</span>
            <span style={{ color: T.slate, fontSize: 12 }}>
              {p.created_at ? new Date(p.created_at).toLocaleDateString("fr-FR") : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [nav, setNav] = useState("dashboard");
  const [tokens, setTokens] = useState(null);
  const [me, setMe] = useState(null);

  const logout = useCallback(() => {
    setTokens(null);
    setMe(null);
  }, []);

  const apiFetch = useCallback(async (path, options = {}) => {
    if (!tokens) throw new Error("Non authentifié.");

    const doFetch = (accessToken) => fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
        Authorization: `Bearer ${accessToken}`,
      },
    });

    let res;
    try {
      res = await doFetch(tokens.access);
    } catch (err) {
      throw new Error("Impossible de joindre l'API. Vérifiez que le backend tourne sur " + API_BASE + " et que CORS est configuré.");
    }

    if (res.status === 401 && tokens.refresh) {
      const refreshRes = await fetch(`${API_BASE}/api/auth/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: tokens.refresh }),
      });
      if (refreshRes.ok) {
        const data = await refreshRes.json();
        setTokens(prev => ({ ...prev, access: data.access }));
        res = await doFetch(data.access);
      } else {
        logout();
        throw new Error("Session expirée, reconnectez-vous.");
      }
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Erreur API (${res.status})`);
    }

    return res.status === 204 ? null : res.json();
  }, [tokens, logout]);

  useEffect(() => {
    if (!tokens) return;
    apiFetch("/api/accounts/me/")
      .then(setMe)
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokens]);

  if (!tokens) {
    return <LoginScreen onLogin={setTokens} />;
  }

  const userLabel = me ? `${me.first_name || ""} ${me.last_name || ""}`.trim() || me.email : "…";

  const views = {
    dashboard: <DashboardView apiFetch={apiFetch} userLabel={userLabel} />,
    agenda:    <AgendaView apiFetch={apiFetch} />,
    patients:  <PatientsView apiFetch={apiFetch} />,
    settings:  <div style={{ color: T.slate, padding: 8 }}>Paramètres — à venir</div>,
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <Sidebar active={nav} onNav={setNav} onLogout={logout} userLabel={userLabel} />
      <main style={{ flex: 1, padding: "2rem 2.5rem", overflow: "auto" }}>
        {views[nav]}
      </main>
    </div>
  );
}
