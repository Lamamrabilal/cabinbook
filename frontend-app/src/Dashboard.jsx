import { useState, useCallback, useEffect, useMemo } from "react";
import QRCode from "qrcode";

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
      <div style={{
        fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase",
        letterSpacing: "0.07em", marginBottom: 6,
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, color: T.navy, lineHeight: 1 }}>{value}</div>
      <div style={{
        fontSize: 12, color: T.slate, marginTop: 4,
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>{sub || "\u00a0"}</div>
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

function AppointmentRow({ appt, onAction, showPractitioner }) {
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
          {showPractitioner && appt.practitioner_name && (
            <span style={{ color: T.teal, fontWeight: 600 }}> · {appt.practitioner_name}</span>
          )}
        </div>
      </div>
      {appt.video_room_url && appt.status === "confirmed" && (
        <a href={appt.video_room_url} target="_blank" rel="noopener noreferrer" title="Rejoindre la visioconférence" style={{
          ...btnStyle(T.navy), display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none",
        }}>🎥</a>
      )}
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
function LoginScreen({ onLogin, onGoToRegister, onGoToForgotPassword }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [needsOtp, setNeedsOtp] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/token/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, ...(needsOtp ? { otp_code: otpCode } : {}) }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (body.requires_otp) {
          setNeedsOtp(true);
          setError(needsOtp ? "Code invalide, réessayez." : "");
          return;
        }
        throw new Error(body.detail || "Identifiants invalides.");
      }
      onLogin();
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
        <input type="email" placeholder="Email" value={email} disabled={needsOtp}
          onChange={e => setEmail(e.target.value)} required style={inputStyle} />
        <input type="password" placeholder="Mot de passe" value={password} disabled={needsOtp}
          onChange={e => setPassword(e.target.value)} required style={inputStyle} />
        {needsOtp && (
          <input type="text" inputMode="numeric" placeholder="Code à 6 chiffres" value={otpCode}
            onChange={e => setOtpCode(e.target.value)} maxLength={6} required autoFocus
            style={inputStyle} />
        )}
        {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.75rem", fontSize: 14, fontWeight: 700,
          cursor: loading ? "default" : "pointer", opacity: loading ? 0.7 : 1,
        }}>
          {loading ? "Connexion…" : needsOtp ? "Valider le code" : "Se connecter"}
        </button>
        <button type="button" onClick={onGoToForgotPassword} style={{
          background: "transparent", border: "none", color: T.slate,
          fontSize: 12, cursor: "pointer", textDecoration: "underline", textAlign: "center",
        }}>
          Mot de passe oublié ?
        </button>
        <button type="button" onClick={onGoToRegister} style={{
          background: "transparent", border: "none", color: T.slate,
          fontSize: 12.5, cursor: "pointer", textDecoration: "underline",
        }}>
          Pas encore de compte ? Créer un compte praticien
        </button>
      </form>
    </div>
  );
}

// ── Écran d'inscription ──────────────────────────────────
function RegisterScreen({ onRegistered, onGoToLogin }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/accounts/register/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email,
          phone,
          password,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const firstError = body && typeof body === "object"
          ? Object.values(body).flat().find(Boolean)
          : null;
        throw new Error(firstError || "Impossible de créer le compte.");
      }
      // Une fois inscrit, connexion automatique
      const loginRes = await fetch(`${API_BASE}/api/auth/token/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!loginRes.ok) {
        // Inscription réussie mais connexion auto échouée : renvoyer vers login
        onGoToLogin();
        return;
      }
      onRegistered();
    } catch (err) {
      setError(err.message || "Erreur lors de la création du compte.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif", padding: "2rem 0",
    }}>
      <form onSubmit={submit} style={{
        background: T.white, border: `1px solid ${T.border}`, borderRadius: 14,
        padding: "2rem", width: 360, display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ fontFamily: "Georgia, serif", fontSize: "1.5rem", color: T.navy, textAlign: "center", marginBottom: 4 }}>
          Cabin<span style={{ color: T.teal }}>Book</span>
        </div>
        <p style={{ fontSize: 12.5, color: T.slate, textAlign: "center", marginTop: -8 }}>
          Créer votre compte praticien
        </p>
        <div style={{ display: "flex", gap: 10 }}>
          <input type="text" placeholder="Prénom" value={firstName}
            onChange={e => setFirstName(e.target.value)} required style={inputStyle} />
          <input type="text" placeholder="Nom" value={lastName}
            onChange={e => setLastName(e.target.value)} required style={inputStyle} />
        </div>
        <input type="email" placeholder="Email" value={email}
          onChange={e => setEmail(e.target.value)} required style={inputStyle} />
        <input type="tel" placeholder="Téléphone (optionnel)" value={phone}
          onChange={e => setPhone(e.target.value)} style={inputStyle} />
        <input type="password" placeholder="Mot de passe (8 caractères min.)" value={password}
          onChange={e => setPassword(e.target.value)} required minLength={8} style={inputStyle} />
        {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.75rem", fontSize: 14, fontWeight: 700,
          cursor: loading ? "default" : "pointer", opacity: loading ? 0.7 : 1,
        }}>
          {loading ? "Création…" : "Créer mon compte"}
        </button>
        <button type="button" onClick={onGoToLogin} style={{
          background: "transparent", border: "none", color: T.slate,
          fontSize: 12.5, cursor: "pointer", textDecoration: "underline",
        }}>
          Déjà un compte ? Se connecter
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
  { id: "waitlist",  icon: "⏳", label: "Liste d'attente" },
  { id: "settings",  icon: "⚙️",  label: "Paramètres"     },
];

function Sidebar({ active, onNav, onLogout, userLabel, allPractitioners, practitionerFilter, onPractitionerChange }) {
  return (
    <aside style={{
      width: 220, background: T.navy, flexShrink: 0,
      display: "flex", flexDirection: "column",
      minHeight: "100vh", padding: "0 0 2rem",
    }}>
      {/* Logo */}
      <div style={{ padding: "1.5rem 1.25rem 1.25rem", borderBottom: `1px solid rgba(255,255,255,0.08)` }}>
        <span style={{
          fontFamily: "Georgia, serif", fontSize: "1.35rem",
          color: T.white, letterSpacing: "-0.02em",
        }}>
          Cabin<span style={{ color: "#5DD6C8" }}>Book</span>
        </span>
      </div>

      {/* Sélecteur de praticien (visible si plusieurs praticiens) */}
      {allPractitioners && allPractitioners.length > 1 && (
        <div style={{ padding: "0.75rem 1.25rem", borderBottom: `1px solid rgba(255,255,255,0.08)` }}>
          <label style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: 5 }}>
            Praticien
          </label>
          <select
            value={practitionerFilter || (allPractitioners[0] && allPractitioners[0].id) || ""}
            onChange={e => onPractitionerChange(parseInt(e.target.value))}
            style={{
              width: "100%", padding: "0.4rem 0.5rem", borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.06)",
              color: T.white, fontSize: 12.5, fontWeight: 600, fontFamily: "inherit",
            }}
          >
            {allPractitioners.map(p => (
              <option key={p.id} value={p.id} style={{ color: T.navy }}>
                {p.first_name} {p.last_name}
              </option>
            ))}
          </select>
        </div>
      )}

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

function DashboardView({ apiFetch, userLabel, filterSuffix, plan, practitionerFilter }) {
  const [showNewAppt, setShowNewAppt] = useState(false);
  const [stats, setStats] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [week, setWeek] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [byPractitioner, setByPractitioner] = useState([]);
  const [loadingByPractitioner, setLoadingByPractitioner] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const suffix = filterSuffix || "";
      const [statsData, todayData] = await Promise.all([
        apiFetch(`/api/appointments/stats/?_=${Date.now()}${suffix}`),
        apiFetch(`/api/appointments/today/?_=${Date.now()}${suffix}`),
      ]);
      setStats(statsData);
      setAppointments(todayData);

      // Prochains RDV (hors aujourd'hui, non annulés)
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(0, 0, 0, 0);
      const upcomingData = await apiFetch(
        `/api/appointments/?date_from=${encodeURIComponent(tomorrow.toISOString())}&ordering=start_time${suffix}`
      );
      setUpcoming((upcomingData || []).filter(a => a.status !== "cancelled").slice(0, 5));

      // Activité de la semaine (lundi → vendredi)
      const { monday, friday } = getWeekRange();
      const weekData = await apiFetch(
        `/api/appointments/?date_from=${encodeURIComponent(monday.toISOString())}&date_to=${encodeURIComponent(friday.toISOString())}&ordering=start_time${suffix}`
      );
      const labels = ["Lun", "Mar", "Mer", "Jeu", "Ven"];
      const buckets = labels.map(d => ({ day: d, total: 0, no_show: 0 }));
      (weekData || []).forEach(a => {
        if (a.status === "cancelled") return;
        const idx = new Date(a.start_time).getDay() - 1; // 1=lun..5=ven → 0..4
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
  }, [apiFetch, filterSuffix]);

  useEffect(() => { loadAll(); }, [loadAll]);

  useEffect(() => {
    if (plan === "cabinet" && practitionerFilter === "all") {
      setLoadingByPractitioner(true);
      apiFetch("/api/appointments/stats_by_practitioner/")
        .then(data => setByPractitioner(data || []))
        .catch(() => setByPractitioner([]))
        .finally(() => setLoadingByPractitioner(false));
    } else {
      setByPractitioner([]);
    }
  }, [apiFetch, plan, practitionerFilter]);

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

  const weekMax = week.length ? Math.max(...week.map(d => d.total), 1) : 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: T.navy }}>Bonjour, {userLabel || ""} 👋</h1>
        <p style={{ fontSize: 13, color: T.slate, marginTop: 2 }}>
          {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        <StatCard label="RDV ce mois"      value={stats.total_month}    sub="depuis le 1er du mois"     accent={T.teal}  />
        <StatCard label="À venir aujourd'hui" value={stats.upcoming_today} sub="prochains créneaux"      accent="#2563EB" />
        <StatCard label="Confirmés"        value={stats.confirmed}      sub="rendez-vous confirmés"      accent={T.amber} />
        <StatCard label="No-shows ce mois" value={stats.no_shows_month}
          sub={stats.total_month ? `${Math.round(stats.no_shows_month / stats.total_month * 100)}% des RDV` : "—"}
          accent={T.red} />
      </div>

      {byPractitioner.length > 0 && (
        <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden" }}>
          <div style={{ padding: "1rem 1.25rem", borderBottom: `1px solid ${T.border}`, fontSize: 14, fontWeight: 700, color: T.navy }}>
            Comparatif par praticien — ce mois-ci
          </div>
          <div style={{
            display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
            padding: "0.6rem 1.25rem", borderBottom: `1px solid ${T.border}`,
            fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", letterSpacing: "0.05em",
          }}>
            <span>Praticien</span><span>RDV</span><span>Confirmés</span><span>No-shows</span><span>Remplissage</span>
          </div>
          {byPractitioner.map(p => (
            <div key={p.practitioner_id} style={{
              display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
              padding: "0.75rem 1.25rem", borderBottom: `1px solid ${T.border}`,
              fontSize: 13, alignItems: "center",
            }}>
              <span style={{ fontWeight: 600, color: T.navy }}>{p.practitioner_name}</span>
              <span>{p.total_month}</span>
              <span style={{ color: T.teal, fontWeight: 600 }}>{p.confirmed}</span>
              <span style={{ color: p.no_shows > 0 ? T.red : T.slate, fontWeight: p.no_shows > 0 ? 600 : 400 }}>{p.no_shows}</span>
              <span style={{ fontWeight: 600, color: T.navy }}>{p.fill_rate}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Main grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>
        {/* Aujourd'hui */}
        <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden" }}>
          <div style={{ padding: "1rem 1.25rem", borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>Rendez-vous du jour</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: T.slate, background: T.cream, padding: "3px 10px", borderRadius: 99, fontWeight: 600 }}>
                {appointments.filter(a => a.status === "confirmed").length} confirmés
              </span>
              <button onClick={() => setShowNewAppt(true)} style={{
                background: T.teal, color: T.white, border: "none", borderRadius: 8,
                padding: "0.4rem 0.75rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
              }}>
                + Nouveau RDV
              </button>
            </div>
          </div>
          {appointments.length === 0 && (
            <div style={{ padding: "1.5rem 1.25rem", fontSize: 13, color: T.slate }}>Aucun rendez-vous aujourd'hui.</div>
          )}
          {appointments.map(a => (
            <AppointmentRow key={a.id} appt={a} onAction={handleAction} showPractitioner={practitionerFilter === "all"} />
          ))}
        </div>

        {/* Colonne droite */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Semaine */}
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

          {/* Prochains RDV */}
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
                  <div style={{ fontSize: 11, color: T.slate }}>
                    {fmtD(a.start_time)} · {fmt(a.start_time)}
                    {practitionerFilter === "all" && a.practitioner_name && (
                      <span style={{ color: T.teal, fontWeight: 600 }}> · {a.practitioner_name}</span>
                    )}
                  </div>
                </div>
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
      {showNewAppt && (
        <NewAppointmentModal
          apiFetch={apiFetch}
          practitionerFilter={practitionerFilter}
          canUseSeries={plan === "pro" || plan === "cabinet"}
          onClose={() => setShowNewAppt(false)}
          onCreated={() => { setShowNewAppt(false); loadAll(); }}
        />
      )}
    </div>
  );
}

// ── Vue Agenda (calendrier hebdo) ────────────────────────
function AgendaView({ apiFetch, filterSuffix }) {
  const hours = Array.from({ length: 10 }, (_, i) => i + 8); // 8h–17h
  const [weekOffset, setWeekOffset] = useState(0);

  const { monday, friday } = useMemo(() => {
    const base = getWeekRange();
    const m = new Date(base.monday);
    m.setDate(m.getDate() + weekOffset * 7);
    const f = new Date(base.friday);
    f.setDate(f.getDate() + weekOffset * 7);
    return { monday: m, friday: f };
  }, [weekOffset]);

  const days = Array.from({ length: 5 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d.toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit" });
  });

  const [placed, setPlaced] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedAppt, setSelectedAppt] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    apiFetch(
      `/api/appointments/?date_from=${encodeURIComponent(monday.toISOString())}&date_to=${encodeURIComponent(friday.toISOString())}&ordering=start_time${filterSuffix || ""}`
    )
      .then(data => {
        const events = (data || [])
          .filter(a => a.status !== "cancelled")
          .map(a => {
            const start = new Date(a.start_time);
            const end = new Date(a.end_time);
            const dayIdx = start.getDay() - 1; // 1=lun..5=ven → 0..4
            const startHour = start.getHours() + start.getMinutes() / 60;
            const durationH = Math.max((end - start) / 3600000, 0.25);
            return {
              id: a.id, day: dayIdx, start: startHour, duration: durationH, patient: a.patient_name,
              status: a.status, start_time: a.start_time, end_time: a.end_time,
              series: a.series, series_position: a.series_position, series_total: a.series_total,
              video_room_url: a.video_room_url,
            };
          })
          .filter(ev => ev.day >= 0 && ev.day < 5);
        setPlaced(events);
      })
      .catch(err => { setError(err.message || "Erreur de chargement de l'agenda."); })
      .finally(() => { setLoading(false); });
  }, [apiFetch, monday, friday, filterSuffix]);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (id, action) => {
    try {
      await apiFetch(`/api/appointments/${id}/${action}/`, { method: "POST" });
      setSelectedAppt(null);
      load();
    } catch (err) {
      setError(err.message || "Action impossible.");
    }
  };

  const cancelSeriesFollowing = async (seriesId) => {
    const ok = window.confirm("Annuler cette séance et toutes les suivantes de cette série ?");
    if (!ok) return;
    try {
      await apiFetch(`/api/appointments/series/${seriesId}/cancel/`, {
        method: "POST",
        body: JSON.stringify({ scope: "future" }),
      });
      setSelectedAppt(null);
      load();
    } catch (err) {
      setError(err.message || "Action impossible.");
    }
  };

  const CELL_H = 56;

  const now = new Date();
  const isCurrentWeek = now >= monday && now <= friday;
  const todayColIndex = isCurrentWeek ? now.getDay() - 1 : -1;
  const nowHourFraction = now.getHours() + now.getMinutes() / 60;
  const nowLineTop = (isCurrentWeek && todayColIndex >= 0 && nowHourFraction >= 8 && nowHourFraction <= 18)
    ? (nowHourFraction - 8) * CELL_H
    : null;

  if (loading) return <LoadingState label="Chargement de l'agenda…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: T.navy }}>
          Agenda — semaine du {monday.toLocaleDateString("fr-FR", { day: "numeric", month: "long" })}
        </h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setWeekOffset(o => o - 1)} style={{
            width: 32, height: 32, borderRadius: 8, border: `1px solid ${T.border}`,
            background: T.white, cursor: "pointer", fontSize: 14,
          }}>←</button>
          {weekOffset !== 0 && (
            <button onClick={() => setWeekOffset(0)} style={{
              padding: "0 0.75rem", height: 32, borderRadius: 8, border: `1px solid ${T.border}`,
              background: T.white, cursor: "pointer", fontSize: 12, fontWeight: 600, color: T.slate,
            }}>Aujourd'hui</button>
          )}
          <button onClick={() => setWeekOffset(o => o + 1)} style={{
            width: 32, height: 32, borderRadius: 8, border: `1px solid ${T.border}`,
            background: T.white, cursor: "pointer", fontSize: 14,
          }}>→</button>
        </div>
      </div>
      <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "auto" }}>
        {/* Header jours */}
        <div style={{ display: "grid", gridTemplateColumns: "52px repeat(5, 1fr)", borderBottom: `1px solid ${T.border}` }}>
          <div />
          {days.map((d, di) => {
            const isToday = todayColIndex === di;
            return (
              <div key={d} style={{
                padding: "0.65rem 0.5rem", textAlign: "center",
                fontSize: 12, fontWeight: isToday ? 800 : 600,
                color: isToday ? T.teal : T.slate,
                background: isToday ? T.tealLt : "transparent",
                borderLeft: `1px solid ${T.border}`,
              }}>
                {d}
              </div>
            );
          })}
        </div>
        {/* Corps */}
        <div style={{ position: "relative" }}>
          <div style={{ display: "grid", gridTemplateColumns: "52px repeat(5, 1fr)" }}>
            {hours.map(h => (
              <div key={`row-${h}`} style={{ display: "contents" }}>
                <div style={{ height: CELL_H, borderBottom: `1px solid ${T.border}`, padding: "4px 8px 0 0", textAlign: "right", fontSize: 10.5, color: T.slate }}>
                  {h}h
                </div>
                {days.map((_, di) => (
                  <div key={`${h}-${di}`} style={{
                    height: CELL_H, borderBottom: `1px solid ${T.border}`, borderLeft: `1px solid ${T.border}`,
                    background: todayColIndex === di ? "rgba(26,127,114,0.035)" : "transparent",
                  }} />
                ))}
              </div>
            ))}
          </div>

          {/* Ligne d'heure actuelle */}
          {nowLineTop !== null && (
            <div style={{
              position: "absolute", top: nowLineTop,
              left: `calc(52px + ${todayColIndex} * (100% - 52px) / 5)`,
              width: "calc((100% - 52px) / 5)",
              height: 2, background: T.red, zIndex: 5, pointerEvents: "none",
            }}>
              <span style={{
                position: "absolute", left: -5, top: -4,
                width: 9, height: 9, borderRadius: "50%", background: T.red,
              }} />
            </div>
          )}

          {/* Events superposés */}
          {placed.map((ev, i) => {
            const s = STATUS[ev.status];
            const top  = (ev.start - 8) * CELL_H + 2;
            const initials = ev.patient.split(" ").map(n => n[0]).slice(0, 2).join("").toUpperCase();
            const needsAction = ev.status === "confirmed" && new Date(ev.end_time) < now;
            return (
              <div key={i} onClick={() => setSelectedAppt(ev)} title={needsAction ? "RDV passé — à marquer Terminé ou Absent" : undefined} style={{
                position: "absolute",
                top, left: `calc(52px + ${ev.day} * (100% - 52px) / 5 + 4px)`,
                width: "calc((100% - 52px) / 5 - 8px)",
                height: ev.duration * CELL_H - 4,
                background: s.bg, border: `1px solid ${needsAction ? T.amber : s.dot}`,
                borderLeft: `3px solid ${needsAction ? T.amber : s.dot}`,
                borderStyle: needsAction ? "dashed" : "solid",
                borderRadius: 10, padding: "5px 8px", overflow: "hidden",
                cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
                boxShadow: "0 1px 2px rgba(15,27,45,0.05)",
              }}>
                <div style={{
                  width: 20, height: 20, borderRadius: "50%", flexShrink: 0,
                  background: T.white, color: s.color, fontSize: 9, fontWeight: 700,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>{initials}</div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: s.color, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {needsAction && <span title="RDV passé, non traité">⚠️ </span>}
                    {ev.series && <span title={`Séance ${ev.series_position}${ev.series_total ? `/${ev.series_total}` : ""}`}>🔁 </span>}
                    {ev.patient}
                  </div>
                  <div style={{ fontSize: 9.5, color: s.color, opacity: 0.75 }}>{String(Math.floor(ev.start)).padStart(2, "0")}:{String(Math.round((ev.start % 1) * 60)).padStart(2, "0")}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {selectedAppt && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(15,27,45,0.5)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
        }}>
          <div style={{ background: T.white, borderRadius: 14, padding: "1.75rem", width: 340 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 style={{ fontFamily: "Georgia, serif", fontSize: 16, color: T.navy }}>{selectedAppt.patient}</h3>
              <button onClick={() => setSelectedAppt(null)} style={{ background: "none", border: "none", fontSize: 18, color: T.slate, cursor: "pointer" }}>✕</button>
            </div>
            <p style={{ fontSize: 13, color: T.slate, marginBottom: 4 }}>
              {fmtD(selectedAppt.start_time)} · {fmt(selectedAppt.start_time)} – {fmt(selectedAppt.end_time)}
            </p>
            {selectedAppt.series && (
              <p style={{ fontSize: 12, color: T.slate, marginBottom: 4 }}>
                🔁 Séance {selectedAppt.series_position}{selectedAppt.series_total ? ` / ${selectedAppt.series_total}` : ""}
              </p>
            )}
            {selectedAppt.status === "confirmed" && new Date(selectedAppt.end_time) < new Date() && (
              <p style={{
                fontSize: 12, fontWeight: 600, color: T.amber, background: T.amberLt,
                borderRadius: 8, padding: "0.5rem 0.65rem", marginBottom: 12,
              }}>⚠️ Ce RDV est passé et n'a pas été marqué Terminé ou Absent.</p>
            )}
            <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <StatusBadge status={selectedAppt.status} />
              {selectedAppt.video_room_url && selectedAppt.status === "confirmed" && (
                <a href={selectedAppt.video_room_url} target="_blank" rel="noopener noreferrer" style={{
                  fontSize: 12, fontWeight: 700, color: T.teal, textDecoration: "none",
                  display: "flex", alignItems: "center", gap: 4,
                }}>🎥 Rejoindre la visio</a>
              )}
            </div>
            {selectedAppt.status === "confirmed" && (
              <div style={{ display: "flex", gap: 8, marginBottom: selectedAppt.series ? 8 : 0 }}>
                <button onClick={() => handleAction(selectedAppt.id, "complete")} style={{
                  flex: 1, background: T.teal, color: T.white, border: "none", borderRadius: 8,
                  padding: "0.5rem", fontSize: 12, fontWeight: 700, cursor: "pointer",
                }}>✓ Terminé</button>
                <button onClick={() => handleAction(selectedAppt.id, "no_show")} style={{
                  flex: 1, background: "transparent", color: T.amber, border: `1px solid ${T.amber}`, borderRadius: 8,
                  padding: "0.5rem", fontSize: 12, fontWeight: 700, cursor: "pointer",
                }}>Absent</button>
                <button onClick={() => handleAction(selectedAppt.id, "cancel")} style={{
                  flex: 1, background: "transparent", color: T.red, border: `1px solid ${T.red}`, borderRadius: 8,
                  padding: "0.5rem", fontSize: 12, fontWeight: 700, cursor: "pointer",
                }}>Annuler</button>
              </div>
            )}
            {selectedAppt.status === "confirmed" && selectedAppt.series && (
              <button onClick={() => cancelSeriesFollowing(selectedAppt.series)} style={{
                width: "100%", background: "transparent", color: T.red, border: `1px solid ${T.red}`, borderRadius: 8,
                padding: "0.5rem", fontSize: 12, fontWeight: 700, cursor: "pointer",
              }}>Annuler cette séance et les suivantes</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Vue Liste d'attente ───────────────────────────────────
const WAITLIST_STATUS = {
  waiting:   { label: "En attente", bg: T.amberLt, color: T.amber },
  notified:  { label: "Prévenu",    bg: T.tealLt,  color: T.teal  },
  booked:    { label: "Réservé",    bg: "#F0F0F0", color: T.slate },
  cancelled: { label: "Annulé",     bg: "#F0F0F0", color: T.slate },
};

function WaitlistView({ apiFetch, practitionerFilter }) {
  const [entries, setEntries] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [patientSearch, setPatientSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const suffix = (practitionerFilter && practitionerFilter !== "all") ? `?practitioner=${practitionerFilter}` : "";
      const [entriesData, patientsData] = await Promise.all([
        apiFetch(`/api/appointments/waitlist/${suffix}`),
        apiFetch(`/api/accounts/patients/${suffix}`),
      ]);
      setEntries(entriesData || []);
      setPatients(patientsData || []);
    } catch (err) {
      setError(err.message || "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch, practitionerFilter]);

  useEffect(() => { load(); }, [load]);

  const filteredPatients = patients
    .filter(p => `${p.first_name} ${p.last_name}`.toLowerCase().includes(patientSearch.toLowerCase()))
    .slice(0, 8);

  const addEntry = async () => {
    if (!selectedPatientId) { setError("Choisissez un patient."); return; }
    const practitionerId = patients.find(p => p.id === selectedPatientId)?.practitioner;
    setSubmitting(true);
    setError("");
    try {
      await apiFetch("/api/appointments/waitlist/", {
        method: "POST",
        body: JSON.stringify({ practitioner: practitionerId, patient_id: selectedPatientId, notes }),
      });
      setShowAdd(false);
      setSelectedPatientId(null);
      setNotes("");
      setPatientSearch("");
      load();
    } catch (err) {
      setError(err.message || "Impossible d'ajouter à la liste d'attente.");
    } finally {
      setSubmitting(false);
    }
  };

  const doAction = async (id, action) => {
    setBusyId(id);
    try {
      if (action === "remove") {
        await apiFetch(`/api/appointments/waitlist/${id}/`, { method: "DELETE" });
      } else {
        await apiFetch(`/api/appointments/waitlist/${id}/${action}/`, { method: "POST" });
      }
      load();
    } catch (err) {
      setError(err.message || "Action impossible.");
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <LoadingState label="Chargement de la liste d'attente…" />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.navy }}>Liste d'attente</h1>
          <p style={{ fontSize: 12.5, color: T.slate, marginTop: 2 }}>
            Quand un RDV est annulé, le premier patient de la liste est prévenu automatiquement par email.
          </p>
        </div>
        <button onClick={() => setShowAdd(s => !s)} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.6rem 1.1rem", fontSize: 13, fontWeight: 700, cursor: "pointer",
        }}>
          + Ajouter un patient
        </button>
      </div>

      {error && (
        <div style={{ color: T.red, fontSize: 12, marginBottom: 12, background: T.redLt, padding: "0.5rem 0.75rem", borderRadius: 8 }}>
          {error}
        </div>
      )}

      {showAdd && (
        <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.25rem", marginBottom: 16 }}>
          <input type="text" placeholder="Rechercher un patient…" value={patientSearch}
            onChange={e => setPatientSearch(e.target.value)} style={{ ...inputStyle, marginBottom: 8 }} />
          <div style={{ maxHeight: 140, overflowY: "auto", marginBottom: 10 }}>
            {filteredPatients.map(p => (
              <div key={p.id} onClick={() => setSelectedPatientId(p.id)} style={{
                padding: "0.5rem 0.6rem", borderRadius: 7, cursor: "pointer", fontSize: 13,
                background: selectedPatientId === p.id ? T.tealLt : "transparent",
                border: `1px solid ${selectedPatientId === p.id ? T.teal : "transparent"}`,
              }}>
                {p.first_name} {p.last_name} <span style={{ color: T.slate, fontSize: 11 }}>· {p.email}</span>
              </div>
            ))}
          </div>
          <input type="text" placeholder="Note (optionnel) — ex: disponible le matin" value={notes}
            onChange={e => setNotes(e.target.value)} style={{ ...inputStyle, marginBottom: 10 }} />
          <button onClick={addEntry} disabled={submitting} style={{
            background: T.navy, color: T.white, border: "none", borderRadius: 8,
            padding: "0.55rem 1.1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
          }}>
            {submitting ? "Ajout…" : "Ajouter à la liste"}
          </button>
        </div>
      )}

      {entries.length === 0 ? (
        <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "2rem", textAlign: "center", color: T.slate, fontSize: 13 }}>
          Personne en liste d'attente pour le moment.
        </div>
      ) : (
        <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, overflow: "hidden" }}>
          {entries.map((e, i) => {
            const s = WAITLIST_STATUS[e.status] || WAITLIST_STATUS.waiting;
            return (
              <div key={e.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "0.85rem 1.25rem", borderBottom: i < entries.length - 1 ? `1px solid ${T.border}` : "none",
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.navy }}>
                    {i === 0 && e.status === "waiting" && <span style={{ marginRight: 6 }}>①</span>}
                    {e.patient.first_name} {e.patient.last_name}
                  </div>
                  {e.notes && <div style={{ fontSize: 11.5, color: T.slate, marginTop: 2 }}>{e.notes}</div>}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: "0.2rem 0.55rem", borderRadius: 6,
                    background: s.bg, color: s.color,
                  }}>{s.label}</span>
                  {e.status === "waiting" && (
                    <button onClick={() => doAction(e.id, "notify")} disabled={busyId === e.id} style={{
                      background: T.teal, color: T.white, border: "none", borderRadius: 7,
                      padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
                    }}>Prévenir</button>
                  )}
                  {e.status === "notified" && (
                    <button onClick={() => doAction(e.id, "mark_booked")} disabled={busyId === e.id} style={{
                      background: T.navy, color: T.white, border: "none", borderRadius: 7,
                      padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
                    }}>Marquer réservé</button>
                  )}
                  <button onClick={() => doAction(e.id, "remove")} disabled={busyId === e.id} style={{
                    background: "transparent", color: T.red, border: `1px solid ${T.red}`, borderRadius: 7,
                    padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
                  }}>Retirer</button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Vue Patients ─────────────────────────────────────────
function PatientsView({ apiFetch, practitionerFilter, plan, role }) {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [newApptForPatient, setNewApptForPatient] = useState(null);
  const [showImport, setShowImport] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const suffix = (practitionerFilter && practitionerFilter !== "all") ? `?practitioner=${practitionerFilter}` : "";
      const data = await apiFetch(`/api/accounts/patients/${suffix}`);
      setPatients(data || []);
    } catch (err) {
      setError(err.message || "Erreur de chargement des patients.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch, practitionerFilter]);

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
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => setShowImport(true)} style={{
            background: "transparent", border: `1px solid ${T.teal}`, color: T.teal,
            borderRadius: 10, padding: "0 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
          }}>
            📄 Importer (CSV)
          </button>
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
      </div>

      {showImport && (
        <ImportPatientsCsvModal
          apiFetch={apiFetch}
          defaultPractitioner={practitionerFilter !== "all" ? practitionerFilter : null}
          onClose={() => setShowImport(false)}
          onImported={() => { setShowImport(false); load(); }}
        />
      )}
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
          <div key={p.id} onClick={() => setSelectedPatient(p)} style={{
            display: "grid", gridTemplateColumns: "1.5fr 2fr 1.3fr 1.5fr 100px",
            padding: "0.85rem 1.25rem", borderBottom: `1px solid ${T.border}`,
            fontSize: 13, alignItems: "center", cursor: "pointer",
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

      {selectedPatient && !newApptForPatient && (
        <PatientDetailModal
          apiFetch={apiFetch}
          patient={selectedPatient}
          role={role}
          onClose={() => setSelectedPatient(null)}
          onUpdated={(updated) => {
            setSelectedPatient(updated);
            setPatients(prev => prev.map(p => p.id === updated.id ? updated : p));
          }}
          onNewAppointment={(p) => setNewApptForPatient(p)}
          onDeactivated={(id) => {
            setPatients(prev => prev.filter(p => p.id !== id));
            setSelectedPatient(null);
          }}
        />
      )}

      {newApptForPatient && (
        <NewAppointmentModal
          apiFetch={apiFetch}
          preselectedPatient={newApptForPatient}
          practitionerFilter={newApptForPatient ? newApptForPatient.practitioner : null}
          canUseSeries={plan === "pro" || plan === "cabinet"}
          onClose={() => setNewApptForPatient(null)}
          onCreated={() => { setNewApptForPatient(null); setSelectedPatient(null); }}
        />
      )}
    </div>
  );
}

// ── Écran d'onboarding (création du profil praticien) ────
const SPECIALTY_OPTIONS = [
  { value: "kine", label: "Kinésithérapeute" },
  { value: "osteo", label: "Ostéopathe" },
  { value: "psy", label: "Psychologue" },
  { value: "infirmier", label: "Infirmier libéral" },
  { value: "autre", label: "Autre" },
];

function slugify(text) {
  return text
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // retire les accents
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function OnboardingScreen({ apiFetch, userLabel, onDone }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [specialty, setSpecialty] = useState("kine");
  const [phone, setPhone] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleNameChange = (setter) => (e) => {
    setter(e.target.value);
    if (!slugTouched) {
      const fn = setter === setFirstName ? e.target.value : firstName;
      const ln = setter === setLastName ? e.target.value : lastName;
      setSlug(slugify(`${fn} ${ln}`.trim()));
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiFetch("/api/accounts/practitioners/", {
        method: "POST",
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          specialty,
          phone,
          booking_page_slug: slug,
        }),
      });
      onDone();
    } catch (err) {
      setError(err.message || "Impossible de créer le profil praticien.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif", padding: "2rem 0",
    }}>
      <form onSubmit={submit} style={{
        background: T.white, border: `1px solid ${T.border}`, borderRadius: 14,
        padding: "2rem", width: 420, display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ fontFamily: "Georgia, serif", fontSize: "1.4rem", color: T.navy }}>
          Bienvenue, {userLabel} 👋
        </div>
        <p style={{ fontSize: 13, color: T.slate, marginTop: -8, lineHeight: 1.5 }}>
          Configurons votre profil praticien pour activer votre agenda et votre page de réservation en ligne.
        </p>

        <div style={{ display: "flex", gap: 10 }}>
          <input type="text" placeholder="Prénom" value={firstName}
            onChange={handleNameChange(setFirstName)} required style={inputStyle} />
          <input type="text" placeholder="Nom" value={lastName}
            onChange={handleNameChange(setLastName)} required style={inputStyle} />
        </div>

        <select value={specialty} onChange={e => setSpecialty(e.target.value)} style={inputStyle}>
          {SPECIALTY_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        <input type="tel" placeholder="Téléphone du cabinet (optionnel)" value={phone}
          onChange={e => setPhone(e.target.value)} style={inputStyle} />

        <div>
          <label style={{ fontSize: 12, color: T.slate, display: "block", marginBottom: 4 }}>
            Adresse de votre page de réservation
          </label>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: 13, color: T.slate, whiteSpace: "nowrap" }}>cabinbook.fr/book/</span>
            <input type="text" value={slug}
              onChange={e => { setSlug(slugify(e.target.value)); setSlugTouched(true); }}
              placeholder="jean-dupont" required
              style={{ ...inputStyle, width: "100%" }} />
          </div>
        </div>

        {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}

        <button type="submit" disabled={loading} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.75rem", fontSize: 14, fontWeight: 700,
          cursor: loading ? "default" : "pointer", opacity: loading ? 0.7 : 1,
        }}>
          {loading ? "Création…" : "Créer mon profil et continuer →"}
        </button>
      </form>
    </div>
  );
}

// ── Vue Paramètres — Disponibilités récurrentes ──────────
const WEEKDAYS = [
  { value: 0, label: "Lundi" },
  { value: 1, label: "Mardi" },
  { value: 2, label: "Mercredi" },
  { value: 3, label: "Jeudi" },
  { value: 4, label: "Vendredi" },
  { value: 5, label: "Samedi" },
  { value: 6, label: "Dimanche" },
];

function AvailabilityRulesManager({ apiFetch, practitionerId }) {
  const [practitioner, setPractitioner] = useState(null);
  const [rules, setRules] = useState({}); // { weekday: { id, start_time, end_time, slot_duration_minutes, is_active } }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingDay, setSavingDay] = useState(null);
  const [savedDay, setSavedDay] = useState(null);

  const load = useCallback(async () => {
    if (!practitionerId) return;
    setLoading(true);
    setError("");
    try {
      const existing = await apiFetch("/api/appointments/availability-rules/");
      const byDay = {};
      (existing || [])
        .filter(r => r.practitioner === practitionerId)
        .forEach(r => { byDay[r.weekday] = r; });
      setRules(byDay);
    } catch (err) {
      setError(err.message || "Erreur de chargement des disponibilités.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch, practitionerId]);

  useEffect(() => { load(); }, [load]);

  const updateLocalRule = (weekday, patch) => {
    setRules(prev => ({
      ...prev,
      [weekday]: {
        ...(prev[weekday] || { start_time: "09:00", end_time: "18:00", slot_duration_minutes: 45, is_active: true }),
        ...patch,
      },
    }));
  };

  const saveDay = async (weekday) => {
    if (!practitionerId) return;
    const rule = rules[weekday];
    if (!rule) return;
    setSavingDay(weekday);
    setError("");
    try {
      const payload = {
        practitioner: practitionerId,
        weekday,
        start_time: rule.start_time,
        end_time: rule.end_time,
        slot_duration_minutes: rule.slot_duration_minutes || 45,
        is_active: rule.is_active !== false,
      };
      let saved;
      if (rule.id) {
        saved = await apiFetch(`/api/appointments/availability-rules/${rule.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        saved = await apiFetch("/api/appointments/availability-rules/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      updateLocalRule(weekday, saved);
      setSavedDay(weekday);
      setTimeout(() => setSavedDay(null), 1500);
    } catch (err) {
      setError(err.message || "Erreur lors de l'enregistrement.");
    } finally {
      setSavingDay(null);
    }
  };

  if (loading) return <LoadingState label="Chargement de vos disponibilités…" />;

  return (
    <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>
        Vos horaires récurrents
      </div>
      <p style={{ fontSize: 12.5, color: T.slate, marginBottom: 16, lineHeight: 1.5 }}>
        Définissez vos créneaux disponibles pour chaque jour. Les rendez-vous seront générés automatiquement chaque nuit pour les 14 prochains jours.
      </p>

      {error && (
        <div style={{ color: T.red, fontSize: 12, marginBottom: 12, background: T.redLt, padding: "0.5rem 0.75rem", borderRadius: 8 }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {WEEKDAYS.map(day => {
          const rule = rules[day.value] || {};
          const isOn = rule.is_active !== false && !!rule.start_time || (rule.is_active === true);
          const duration = rule.slot_duration_minutes || 45;

          const toggle = (checked) => {
            updateLocalRule(day.value, {
              is_active: checked,
              start_time: rule.start_time || "09:00",
              end_time: rule.end_time || "18:00",
              slot_duration_minutes: rule.slot_duration_minutes || 45,
            });
          };

          return (
            <div key={day.value} style={{
              background: isOn ? T.white : T.cream,
              border: `1px solid ${isOn ? T.border : T.border}`,
              borderRadius: 12,
              padding: "0.9rem 1.1rem",
              opacity: isOn ? 1 : 0.75,
              transition: "opacity 0.15s",
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: isOn ? 12 : 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {/* Toggle switch */}
                  <button
                    type="button"
                    onClick={() => toggle(!isOn)}
                    aria-label={isOn ? "Désactiver ce jour" : "Activer ce jour"}
                    style={{
                      width: 38, height: 22, borderRadius: 99, border: "none", cursor: "pointer",
                      background: isOn ? T.teal : T.border, position: "relative",
                      flexShrink: 0, padding: 0, transition: "background 0.15s",
                    }}
                  >
                    <span style={{
                      position: "absolute", top: 2, left: isOn ? 18 : 2,
                      width: 18, height: 18, borderRadius: "50%", background: T.white,
                      transition: "left 0.15s", boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
                    }} />
                  </button>
                  <span style={{ fontSize: 14, fontWeight: 700, color: T.navy, minWidth: 90 }}>
                    {day.label}
                  </span>
                  {!isOn && (
                    <span style={{ fontSize: 12, color: T.slate, fontStyle: "italic" }}>Fermé</span>
                  )}
                </div>

                {isOn && (
                  <button onClick={() => saveDay(day.value)} disabled={savingDay === day.value} style={{
                    background: savedDay === day.value ? T.teal : T.navy, color: T.white, border: "none",
                    borderRadius: 8, padding: "0.45rem 0.9rem", fontSize: 12, fontWeight: 700,
                    cursor: "pointer", whiteSpace: "nowrap",
                  }}>
                    {savingDay === day.value ? "Enregistrement…" : savedDay === day.value ? "✓ Enregistré" : "Enregistrer"}
                  </button>
                )}
              </div>

              {isOn && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, paddingLeft: 50 }}>
                  <div>
                    <label style={{ fontSize: 10.5, fontWeight: 700, color: T.slate, textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: 4 }}>
                      Début
                    </label>
                    <input type="time" value={rule.start_time || "09:00"}
                      onChange={e => updateLocalRule(day.value, { start_time: e.target.value })}
                      style={{ ...inputStyle, padding: "0.5rem 0.6rem", fontSize: 13, width: "100%" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 10.5, fontWeight: 700, color: T.slate, textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: 4 }}>
                      Fin
                    </label>
                    <input type="time" value={rule.end_time || "18:00"}
                      onChange={e => updateLocalRule(day.value, { end_time: e.target.value })}
                      style={{ ...inputStyle, padding: "0.5rem 0.6rem", fontSize: 13, width: "100%" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 10.5, fontWeight: 700, color: T.slate, textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: 4 }}>
                      Durée du créneau
                    </label>
                    <select value={duration}
                      onChange={e => updateLocalRule(day.value, { slot_duration_minutes: parseInt(e.target.value) })}
                      style={{ ...inputStyle, padding: "0.5rem 0.6rem", fontSize: 13, width: "100%" }}>
                      <option value={15}>15 min</option>
                      <option value={20}>20 min</option>
                      <option value={30}>30 min</option>
                      <option value={45}>45 min</option>
                      <option value={60}>1 heure</option>
                      <option value={90}>1h30</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Formulaire d'ajout d'un praticien (plan Cabinet) ─────
const MAX_PRACTITIONERS_BY_PLAN = { starter: 1, pro: 1, cabinet: 5 };

function AddPractitionerForm({ apiFetch, onAdded, onCancel }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [specialty, setSpecialty] = useState("kine");
  const [phone, setPhone] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleNameChange = (setter) => (e) => {
    setter(e.target.value);
    if (!slugTouched) {
      const fn = setter === setFirstName ? e.target.value : firstName;
      const ln = setter === setLastName ? e.target.value : lastName;
      setSlug(slugify(`${fn} ${ln}`.trim()));
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const created = await apiFetch("/api/accounts/practitioners/", {
        method: "POST",
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          specialty,
          phone,
          booking_page_slug: slug,
        }),
      });
      onAdded(created);
    } catch (err) {
      setError(err.message || "Impossible de créer le praticien.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} style={{
      background: T.cream, border: `1px solid ${T.border}`, borderRadius: 12,
      padding: "1.25rem", display: "flex", flexDirection: "column", gap: 10, marginTop: 12,
    }}>
      <div style={{ display: "flex", gap: 10 }}>
        <input type="text" placeholder="Prénom" value={firstName}
          onChange={handleNameChange(setFirstName)} required style={{ ...inputStyle, background: T.white }} />
        <input type="text" placeholder="Nom" value={lastName}
          onChange={handleNameChange(setLastName)} required style={{ ...inputStyle, background: T.white }} />
      </div>
      <select value={specialty} onChange={e => setSpecialty(e.target.value)} style={{ ...inputStyle, background: T.white }}>
        {SPECIALTY_OPTIONS.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <input type="tel" placeholder="Téléphone (optionnel)" value={phone}
        onChange={e => setPhone(e.target.value)} style={{ ...inputStyle, background: T.white }} />
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: 12.5, color: T.slate, whiteSpace: "nowrap" }}>cabinbook.fr/book/</span>
        <input type="text" value={slug}
          onChange={e => { setSlug(slugify(e.target.value)); setSlugTouched(true); }}
          placeholder="marie-dubois" required
          style={{ ...inputStyle, background: T.white, width: "100%" }} />
      </div>
      {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={loading} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 8,
          padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
        }}>
          {loading ? "Création…" : "Ajouter ce praticien"}
        </button>
        <button type="button" onClick={onCancel} style={{
          background: "transparent", color: T.slate, border: `1px solid ${T.border}`, borderRadius: 8,
          padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 600, cursor: "pointer",
        }}>
          Annuler
        </button>
      </div>
    </form>
  );
}

// ── Vue Paramètres ────────────────────────────────────────
function ConsultationPriceField({ apiFetch, practitioner, onUpdated }) {
  const [value, setValue] = useState(
    practitioner.consultation_price_cents ? (practitioner.consultation_price_cents / 100).toFixed(2) : ""
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const save = async () => {
    const cents = value ? Math.round(parseFloat(value.replace(",", ".")) * 100) : 0;
    setSaving(true);
    try {
      await apiFetch(`/api/accounts/practitioners/${practitioner.id}/`, {
        method: "PATCH", body: JSON.stringify({ consultation_price_cents: cents }),
      });
      setSaved(true);
      onUpdated();
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      // silencieux
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
      <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 4 }}>
        Tarif de consultation (utilisé pour pré-remplir vos notes d'honoraires)
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <input type="text" inputMode="decimal" placeholder="Ex: 50" value={value}
          onChange={e => setValue(e.target.value)}
          style={{ ...inputStyle, width: 110 }} />
        <span style={{ alignSelf: "center", color: T.slate, fontSize: 13 }}>€</span>
        <button onClick={save} disabled={saving} style={{
          background: saved ? T.teal : T.navy, color: T.white, border: "none", borderRadius: 8,
          padding: "0 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
        }}>
          {saving ? "…" : saved ? "✓ Enregistré" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}

function DepositAmountField({ apiFetch, practitioner, onUpdated }) {
  const [value, setValue] = useState(
    practitioner.deposit_amount_cents ? (practitioner.deposit_amount_cents / 100).toFixed(2) : ""
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const save = async () => {
    const cents = value ? Math.round(parseFloat(value.replace(",", ".")) * 100) : 0;
    setSaving(true);
    try {
      await apiFetch(`/api/accounts/practitioners/${practitioner.id}/`, {
        method: "PATCH", body: JSON.stringify({ deposit_amount_cents: cents }),
      });
      setSaved(true);
      onUpdated();
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      // silencieux
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
      <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 4 }}>
        Acompte exigé à la réservation en ligne (0 = aucun acompte, paiement classique en cabinet)
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <input type="text" inputMode="decimal" placeholder="Ex: 20" value={value}
          onChange={e => setValue(e.target.value)}
          style={{ ...inputStyle, width: 110 }} />
        <span style={{ alignSelf: "center", color: T.slate, fontSize: 13 }}>€</span>
        <button onClick={save} disabled={saving} style={{
          background: saved ? T.teal : T.navy, color: T.white, border: "none", borderRadius: 8,
          padding: "0 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
        }}>
          {saving ? "…" : saved ? "✓ Enregistré" : "Enregistrer"}
        </button>
      </div>
      {value && parseFloat(value.replace(",", ".")) > 0 && (
        <p style={{ fontSize: 11, color: T.slate, marginTop: 6 }}>
          Un patient réservant en ligne devra payer cet acompte par carte avant que le RDV soit confirmé.
        </p>
      )}
    </div>
  );
}

function TeleconsultationToggleField({ apiFetch, practitioner, onUpdated }) {
  const [enabled, setEnabled] = useState(practitioner.offers_teleconsultation === true);
  const [saving, setSaving] = useState(false);

  const toggle = async (checked) => {
    setEnabled(checked);
    setSaving(true);
    try {
      await apiFetch(`/api/accounts/practitioners/${practitioner.id}/`, {
        method: "PATCH", body: JSON.stringify({ offers_teleconsultation: checked }),
      });
      onUpdated();
    } catch (err) {
      setEnabled(!checked); // revert
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: T.navy, cursor: saving ? "default" : "pointer" }}>
        <input type="checkbox" checked={enabled} disabled={saving} onChange={e => toggle(e.target.checked)} />
        Proposer la téléconsultation (lien de visio Jitsi Meet ajouté à chaque RDV)
      </label>
    </div>
  );
}

function GoogleCalendarSyncField({ apiFetch, practitioner, onUpdated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const connect = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await apiFetch(`/api/accounts/calendar/google/connect/?practitioner=${practitioner.id}`);
      window.location.href = data.authorization_url;
    } catch (err) {
      setError(err.message || "Impossible de démarrer la connexion.");
      setBusy(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm("Déconnecter Google Calendar ? Les RDV ne seront plus synchronisés automatiquement.")) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/api/accounts/calendar/google/disconnect/", {
        method: "POST", body: JSON.stringify({ practitioner: practitioner.id }),
      });
      onUpdated();
    } catch (err) {
      setError(err.message || "Échec de la déconnexion.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
      <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 6 }}>
        Synchro Google Calendar
      </label>
      {practitioner.google_calendar_connected ? (
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{
            fontSize: 12, fontWeight: 600, color: T.teal, background: T.tealLt,
            borderRadius: 8, padding: "0.35rem 0.65rem",
          }}>
            ✓ Connecté{practitioner.google_calendar_email ? ` — ${practitioner.google_calendar_email}` : ""}
          </span>
          <button onClick={disconnect} disabled={busy} style={{
            background: "transparent", color: T.red, border: `1px solid ${T.red}`, borderRadius: 8,
            padding: "0.35rem 0.75rem", fontSize: 12, fontWeight: 700, cursor: "pointer",
          }}>
            {busy ? "…" : "Déconnecter"}
          </button>
        </div>
      ) : (
        <button onClick={connect} disabled={busy} style={{
          background: T.navy, color: T.white, border: "none", borderRadius: 8,
          padding: "0.5rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
        }}>
          {busy ? "…" : "Connecter Google Calendar"}
        </button>
      )}
      {practitioner.google_calendar_connected && (
        <p style={{ fontSize: 11, color: T.slate, marginTop: 6 }}>
          Vos RDV confirmés sont ajoutés automatiquement à cet agenda. Les créneaux occupés
          dans votre agenda Google perso sont bloqués côté CabinBook pour éviter les doublons.
        </p>
      )}
      {error && <p style={{ fontSize: 11.5, color: T.red, marginTop: 6 }}>{error}</p>}
    </div>
  );
}

function DirectoryVisibilityField({ apiFetch, practitioner, onUpdated }) {
  const [city, setCity] = useState(practitioner.city || "");
  const [address, setAddress] = useState(practitioner.address || "");
  const [isListed, setIsListed] = useState(practitioner.is_listed !== false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await apiFetch(`/api/accounts/practitioners/${practitioner.id}/`, {
        method: "PATCH", body: JSON.stringify({ city, address, is_listed: isListed }),
      });
      setSaved(true);
      onUpdated();
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      // silencieux
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
      <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 4 }}>
        Ville (annuaire public de recherche)
      </label>
      <input type="text" placeholder="Ex: Lyon" value={city} onChange={e => setCity(e.target.value)}
        style={{ ...inputStyle, marginBottom: 8 }} />
      <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 4 }}>
        Adresse du cabinet (optionnel)
      </label>
      <input type="text" placeholder="Ex: 12 rue de la République" value={address} onChange={e => setAddress(e.target.value)}
        style={{ ...inputStyle, marginBottom: 10 }} />
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: T.navy, marginBottom: 10, cursor: "pointer" }}>
        <input type="checkbox" checked={isListed} onChange={e => setIsListed(e.target.checked)} />
        Apparaître dans l'annuaire public (recherche par ville/spécialité)
      </label>
      <button onClick={save} disabled={saving} style={{
        background: saved ? T.teal : T.navy, color: T.white, border: "none", borderRadius: 8,
        padding: "0.5rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
      }}>
        {saving ? "…" : saved ? "✓ Enregistré" : "Enregistrer"}
      </button>
    </div>
  );
}

function ReviewsSection({ apiFetch, practitionerId }) {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch(`/api/appointments/reviews/?practitioner=${practitionerId}`)
      .then(data => setReviews(data || []))
      .catch(() => setReviews([]))
      .finally(() => setLoading(false));
  }, [apiFetch, practitionerId]);

  useEffect(() => { load(); }, [load]);

  const toggleHidden = async (id) => {
    setBusyId(id);
    try {
      const updated = await apiFetch(`/api/appointments/reviews/${id}/toggle_hidden/`, { method: "POST" });
      setReviews(prev => prev.map(r => r.id === id ? updated : r));
    } catch (err) {
      // silencieux
    } finally {
      setBusyId(null);
    }
  };

  const visible = reviews.filter(r => !r.is_hidden);
  const avg = visible.length ? (visible.reduce((s, r) => s + r.rating, 0) / visible.length).toFixed(1) : null;

  if (loading) return null;

  return (
    <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>Avis patients</div>
        {avg && (
          <div style={{ fontSize: 12.5, color: T.amber, fontWeight: 700 }}>
            {"★".repeat(Math.round(avg))}{"☆".repeat(5 - Math.round(avg))} {avg}/5 · {visible.length} avis
          </div>
        )}
      </div>
      {reviews.length === 0 ? (
        <p style={{ fontSize: 12.5, color: T.slate }}>Aucun avis reçu pour le moment.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 260, overflowY: "auto" }}>
          {reviews.map(r => (
            <div key={r.id} style={{
              border: `1px solid ${T.border}`, borderRadius: 8, padding: "0.6rem 0.85rem",
              opacity: r.is_hidden ? 0.5 : 1,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: T.amber, fontSize: 12.5 }}>
                  {"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}
                </span>
                <button onClick={() => toggleHidden(r.id)} disabled={busyId === r.id} style={{
                  background: "transparent", border: `1px solid ${T.border}`, color: T.slate, borderRadius: 6,
                  padding: "0.2rem 0.5rem", fontSize: 10.5, fontWeight: 700, cursor: "pointer",
                }}>
                  {r.is_hidden ? "Réafficher" : "Masquer"}
                </button>
              </div>
              {r.comment && <p style={{ fontSize: 12, color: T.navy, marginTop: 4 }}>{r.comment}</p>}
              <div style={{ fontSize: 10.5, color: T.slate, marginTop: 4 }}>
                {r.patient_name} · {new Date(r.created_at).toLocaleDateString("fr-FR")}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Regroupe les cartes de la page Paramètres sous un même thème, avec un
// intitulé de section — évite d'avoir une simple liste plate de cartes
// sans hiérarchie visuelle.
function SettingsSection({ title, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 800, color: T.slate, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function SettingsView({ apiFetch, plan, isSubscriptionActive, practitionerFilter, role, ownerName, otpEnabled, onMeUpdated, calendarReturn, onCalendarReturnHandled }) {
  const isOwner = role !== "secretary";
  const [practitioners, setPractitioners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  const loadPractitioners = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await apiFetch("/api/accounts/practitioners/");
      setPractitioners(list || []);
    } catch (err) {
      setError(err.message || "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => { loadPractitioners(); }, [loadPractitioners]);

  const [showComparative, setShowComparative] = useState(false);
  const [comparativeData, setComparativeData] = useState([]);
  const [loadingComparative, setLoadingComparative] = useState(false);

  const loadComparative = () => {
    setLoadingComparative(true);
    apiFetch("/api/appointments/stats_by_practitioner/")
      .then(data => setComparativeData(data || []))
      .catch(() => setComparativeData([]))
      .finally(() => setLoadingComparative(false));
    setShowComparative(true);
  };

  if (loading) return <LoadingState label="Chargement des paramètres…" />;
  if (error) return <ErrorState message={error} />;

  const practitioner = practitioners.find(p => p.id === practitionerFilter) || practitioners[0] || null;
  const maxPractitioners = MAX_PRACTITIONERS_BY_PLAN[plan] || 1;
  const canAddMore = practitioners.length < maxPractitioners;

  const bookingUrl = practitioner
    ? `${window.location.origin}/book/${practitioner.booking_page_slug}/`
    : "";

  const copyLink = () => {
    navigator.clipboard.writeText(bookingUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 640 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: T.navy }}>Paramètres</h1>

      {calendarReturn && (
        <div style={{
          background: calendarReturn === "connected" ? T.tealLt : "#FEE2E2",
          border: `1px solid ${calendarReturn === "connected" ? T.teal : T.red}`,
          borderRadius: 12, padding: "0.75rem 1rem", fontSize: 12.5,
          color: calendarReturn === "connected" ? T.navy : T.red,
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
        }}>
          <span>
            {calendarReturn === "connected"
              ? "✓ Google Calendar connecté avec succès."
              : "La connexion à Google Calendar a échoué. Réessayez depuis la fiche du praticien."}
          </span>
          <button onClick={() => { onCalendarReturnHandled(); loadPractitioners(); }} style={{
            background: "none", border: "none", fontSize: 14, cursor: "pointer",
            color: "inherit", fontWeight: 700,
          }}>✕</button>
        </div>
      )}

      {!isOwner && (
        <div style={{
          background: T.tealLt, border: `1px solid ${T.teal}`, borderRadius: 12,
          padding: "0.75rem 1rem", fontSize: 12.5, color: T.navy,
        }}>
          Compte secrétaire — vous gérez l'agenda de <strong>{ownerName || "votre titulaire"}</strong>.
          L'abonnement et les notes de séance ne sont pas accessibles depuis ce compte.
        </div>
      )}

      <SettingsSection title="Cabinet & praticiens">
        {plan === "cabinet" && practitioners.length > 1 && (
          <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>
                  Comparatif par praticien
                </div>
                <p style={{ fontSize: 12, color: T.slate }}>
                  Comparez l'activité de vos praticiens ce mois-ci.
                </p>
              </div>
              <button onClick={loadComparative} style={{
                background: T.navy, color: T.white, border: "none", borderRadius: 8,
                padding: "0.5rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
              }}>
                Voir le comparatif
              </button>
            </div>

            {showComparative && (
              <div style={{ marginTop: 16, borderTop: `1px solid ${T.border}`, paddingTop: 16 }}>
                {loadingComparative ? (
                  <LoadingState label="Chargement…" />
                ) : (
                  <>
                    <div style={{
                      display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                      fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase",
                      letterSpacing: "0.05em", paddingBottom: 8, borderBottom: `1px solid ${T.border}`,
                    }}>
                      <span>Praticien</span><span>RDV</span><span>Confirmés</span><span>No-shows</span><span>Remplissage</span>
                    </div>
                    {comparativeData.map(p => (
                      <div key={p.practitioner_id} style={{
                        display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                        padding: "0.6rem 0", borderBottom: `1px solid ${T.border}`, fontSize: 13, alignItems: "center",
                      }}>
                        <span style={{ fontWeight: 600, color: T.navy }}>{p.practitioner_name}</span>
                        <span>{p.total_month}</span>
                        <span style={{ color: T.teal, fontWeight: 600 }}>{p.confirmed}</span>
                        <span style={{ color: p.no_shows > 0 ? T.red : T.slate }}>{p.no_shows}</span>
                        <span style={{ fontWeight: 600, color: T.navy }}>{p.fill_rate}%</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        )}
        {practitioners.length === 0 && !showAddForm && (
          <div style={{ color: T.slate, padding: 8 }}>Aucun profil praticien trouvé.</div>
        )}

        {practitioners.length > 0 && (
          <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: practitioners.length > 1 ? 12 : 0 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>
                {practitioners.length > 1 ? "Praticiens du cabinet" : "Praticien"}
              </div>
              {isOwner && canAddMore && !showAddForm && (
                <button onClick={() => setShowAddForm(true)} style={{
                  background: "transparent", border: `1px solid ${T.teal}`, color: T.teal,
                  borderRadius: 8, padding: "0.35rem 0.75rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
                }}>
                  + Ajouter un praticien
                </button>
              )}
            </div>

            {practitioners.length > 1 && (
              <p style={{ fontSize: 11.5, color: T.slate, marginBottom: 4 }}>
                Praticien affiché : <strong style={{ color: T.navy }}>{practitioner ? `${practitioner.first_name} ${practitioner.last_name}` : "—"}</strong>
                {" "}(changez via le sélecteur dans le menu de gauche)
              </p>
            )}

            {!canAddMore && !showAddForm && practitioners.length > 1 && (
              <p style={{ fontSize: 11.5, color: T.slate, marginTop: 6 }}>
                Limite de {maxPractitioners} praticien(s) atteinte pour le plan {plan}.
              </p>
            )}

            {showAddForm && (
              <AddPractitionerForm
                apiFetch={apiFetch}
                onCancel={() => setShowAddForm(false)}
                onAdded={() => {
                  setShowAddForm(false);
                  loadPractitioners();
                }}
              />
            )}
          </div>
        )}
      </SettingsSection>

      {practitioner && (
        <>
          <SettingsSection title="Profil">
            <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13, color: T.slate }}>
                <div><strong style={{ color: T.navy }}>Nom :</strong> {practitioner.first_name} {practitioner.last_name}</div>
                <div><strong style={{ color: T.navy }}>Spécialité :</strong> {practitioner.specialty}</div>
                {practitioner.phone && <div><strong style={{ color: T.navy }}>Téléphone :</strong> {practitioner.phone}</div>}
              </div>
            </div>
          </SettingsSection>

          <SettingsSection title="Réservation en ligne">
            <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>
                Page de réservation — {practitioner.first_name} {practitioner.last_name}
              </div>
              <p style={{ fontSize: 12.5, color: T.slate, marginBottom: 12, lineHeight: 1.5 }}>
                Partagez ce lien à vos patients pour qu'ils puissent réserver un créneau directement.
              </p>
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <input readOnly value={bookingUrl} style={{ ...inputStyle, flex: 1, background: T.cream }} />
                <button onClick={copyLink} style={{
                  background: copied ? T.teal : T.navy, color: T.white, border: "none",
                  borderRadius: 8, padding: "0 1rem", fontSize: 13, fontWeight: 700, cursor: "pointer",
                  whiteSpace: "nowrap",
                }}>
                  {copied ? "Copié ✓" : "Copier"}
                </button>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 16, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=${encodeURIComponent(bookingUrl)}`}
                  alt="QR code de la page de réservation"
                  width={140} height={140}
                  style={{ border: `1px solid ${T.border}`, borderRadius: 10, background: T.white, padding: 8 }}
                />
                <div style={{ fontSize: 12.5, color: T.slate, lineHeight: 1.6 }}>
                  Affichez ce QR code en salle d'attente ou imprimez-le sur vos supports.
                  Vos patients pourront le scanner pour réserver directement.
                </div>
              </div>
            </div>

            <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 10 }}>Options de réservation</div>
              <ConsultationPriceField apiFetch={apiFetch} practitioner={practitioner} onUpdated={loadPractitioners} />
              {isOwner && <DepositAmountField apiFetch={apiFetch} practitioner={practitioner} onUpdated={loadPractitioners} />}
              {isOwner && <TeleconsultationToggleField apiFetch={apiFetch} practitioner={practitioner} onUpdated={loadPractitioners} />}
              <DirectoryVisibilityField apiFetch={apiFetch} practitioner={practitioner} onUpdated={loadPractitioners} />
            </div>

            <ReviewsSection apiFetch={apiFetch} practitionerId={practitioner.id} />
          </SettingsSection>

          <SettingsSection title="Agenda & disponibilités">
            <AvailabilityRulesManager apiFetch={apiFetch} practitionerId={practitioner.id} />

            {isOwner && (
              <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 10 }}>Synchronisation calendrier</div>
                <GoogleCalendarSyncField apiFetch={apiFetch} practitioner={practitioner} onUpdated={loadPractitioners} />
              </div>
            )}

            {(plan === "pro" || plan === "cabinet") && (
              <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>Export agenda</div>
                <p style={{ fontSize: 12.5, color: T.slate, marginBottom: 12, lineHeight: 1.5 }}>
                  Téléchargez vos rendez-vous au format iCal pour les importer dans Google Calendar,
                  Apple Calendar ou Outlook.
                </p>
                <button
                  onClick={async () => {
                    try {
                      const res = await apiFetch("/api/appointments/export_ical/", { raw: true });
                      const blob = await res.blob();
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "cabinbook-agenda.ics";
                      a.click();
                      window.URL.revokeObjectURL(url);
                    } catch (err) {
                      alert(err.message || "Impossible de télécharger l'export pour le moment.");
                    }
                  }}
                  style={{
                    background: T.navy, color: T.white, border: "none",
                    borderRadius: 8, padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
                  }}
                >
                  📅 Télécharger mon agenda (.ics)
                </button>
              </div>
            )}
          </SettingsSection>
        </>
      )}

      {isOwner && (plan === "pro" || plan === "cabinet") && (
        <SettingsSection title="Équipe & salles">
          {(plan === "pro" || plan === "cabinet") && <TeamSection apiFetch={apiFetch} plan={plan} />}
          {plan === "cabinet" && <RoomsSection apiFetch={apiFetch} />}
        </SettingsSection>
      )}

      <SettingsSection title="Sécurité">
        <TwoFactorSection apiFetch={apiFetch} otpEnabled={otpEnabled} onMeUpdated={onMeUpdated} />
      </SettingsSection>

      {isOwner && (
        <SettingsSection title="Abonnement">
          <BillingSection apiFetch={apiFetch} currentPlan={plan} isActive={isSubscriptionActive} />
        </SettingsSection>
      )}
    </div>
  );
}

// ── Section Sécurité (authentification à deux facteurs) ──
function TwoFactorSection({ apiFetch, otpEnabled, onMeUpdated }) {
  const [step, setStep] = useState("idle"); // idle | setup | disable
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const startSetup = async () => {
    setError("");
    setBusy(true);
    try {
      const data = await apiFetch("/api/accounts/2fa/setup/", { method: "POST" });
      setSecret(data.secret);
      const dataUrl = await QRCode.toDataURL(data.otpauth_url, { width: 200, margin: 1 });
      setQrDataUrl(dataUrl);
      setStep("setup");
    } catch (err) {
      setError(err.message || "Impossible de démarrer la configuration.");
    } finally {
      setBusy(false);
    }
  };

  const confirmSetup = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiFetch("/api/accounts/2fa/confirm/", { method: "POST", body: JSON.stringify({ code }) });
      setStep("idle");
      setCode("");
      onMeUpdated && onMeUpdated();
    } catch (err) {
      setError(err.message || "Code invalide.");
    } finally {
      setBusy(false);
    }
  };

  const confirmDisable = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiFetch("/api/accounts/2fa/disable/", { method: "POST", body: JSON.stringify({ code }) });
      setStep("idle");
      setCode("");
      onMeUpdated && onMeUpdated();
    } catch (err) {
      setError(err.message || "Code invalide.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>Sécurité — Authentification à deux facteurs</div>
          <p style={{ fontSize: 11.5, color: T.slate, marginTop: 2 }}>
            {otpEnabled
              ? "Activée : un code de votre application d'authentification est demandé à chaque connexion."
              : "Ajoutez une couche de sécurité supplémentaire à votre connexion."}
          </p>
        </div>
        {step === "idle" && (
          otpEnabled
            ? <button onClick={() => setStep("disable")} style={{
                background: "transparent", border: `1px solid ${T.red}`, color: T.red,
                borderRadius: 8, padding: "0.4rem 0.9rem", fontSize: 12, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
              }}>Désactiver</button>
            : <button onClick={startSetup} disabled={busy} style={{
                background: T.teal, color: T.white, border: "none",
                borderRadius: 8, padding: "0.4rem 0.9rem", fontSize: 12, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
              }}>{busy ? "…" : "Activer"}</button>
        )}
      </div>

      {error && step === "idle" && <div style={{ color: T.red, fontSize: 12, marginTop: 10 }}>{error}</div>}

      {step === "setup" && (
        <form onSubmit={confirmSetup} style={{
          marginTop: 14, paddingTop: 14, borderTop: `1px solid ${T.border}`,
          display: "flex", flexDirection: "column", gap: 10,
        }}>
          <p style={{ fontSize: 12.5, color: T.slate }}>
            Scannez ce QR code avec Google Authenticator, Authy ou une application équivalente,
            puis saisissez le code à 6 chiffres généré pour confirmer.
          </p>
          <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
            {qrDataUrl && <img src={qrDataUrl} alt="QR code 2FA" width={160} height={160} style={{ borderRadius: 10, border: `1px solid ${T.border}` }} />}
            <div style={{ fontSize: 11.5, color: T.slate }}>
              Ou saisissez manuellement cette clé :<br />
              <code style={{ fontSize: 12, color: T.navy, fontWeight: 700, wordBreak: "break-all" }}>{secret}</code>
            </div>
          </div>
          <input type="text" inputMode="numeric" placeholder="Code à 6 chiffres" value={code}
            onChange={e => setCode(e.target.value)} maxLength={6} required
            style={{ ...inputStyle, width: 160 }} />
          {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={busy} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 8,
              padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
            }}>{busy ? "Vérification…" : "Confirmer et activer"}</button>
            <button type="button" onClick={() => { setStep("idle"); setError(""); }} style={{
              background: "transparent", color: T.slate, border: `1px solid ${T.border}`, borderRadius: 8,
              padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 600, cursor: "pointer",
            }}>Annuler</button>
          </div>
        </form>
      )}

      {step === "disable" && (
        <form onSubmit={confirmDisable} style={{
          marginTop: 14, paddingTop: 14, borderTop: `1px solid ${T.border}`,
          display: "flex", flexDirection: "column", gap: 10,
        }}>
          <p style={{ fontSize: 12.5, color: T.slate }}>
            Saisissez un code actuel de votre application d'authentification pour désactiver la 2FA.
          </p>
          <input type="text" inputMode="numeric" placeholder="Code à 6 chiffres" value={code}
            onChange={e => setCode(e.target.value)} maxLength={6} required
            style={{ ...inputStyle, width: 160 }} />
          {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={busy} style={{
              background: T.red, color: T.white, border: "none", borderRadius: 8,
              padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
            }}>{busy ? "…" : "Désactiver la 2FA"}</button>
            <button type="button" onClick={() => { setStep("idle"); setError(""); }} style={{
              background: "transparent", color: T.slate, border: `1px solid ${T.border}`, borderRadius: 8,
              padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 600, cursor: "pointer",
            }}>Annuler</button>
          </div>
        </form>
      )}
    </div>
  );
}

// ── Section Équipe (comptes secrétaire) ──────────────────
const MAX_STAFF_BY_PLAN = { starter: 0, pro: 1, cabinet: 3 };

function TeamSection({ apiFetch, plan }) {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await apiFetch("/api/accounts/staff/");
      setStaff(list || []);
    } catch (err) {
      setError(err.message || "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => { load(); }, [load]);

  const removeStaff = async (id) => {
    if (!window.confirm("Supprimer ce compte secrétaire ? Il ne pourra plus se connecter.")) return;
    try {
      await apiFetch(`/api/accounts/staff/${id}/`, { method: "DELETE" });
      setStaff(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      alert(err.message || "Suppression impossible.");
    }
  };

  const maxStaff = MAX_STAFF_BY_PLAN[plan] || 0;
  const canAddMore = staff.length < maxStaff;

  return (
    <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>Équipe (comptes secrétaire)</div>
          <p style={{ fontSize: 11.5, color: T.slate, marginTop: 2 }}>
            Accès restreint : agenda et patients, sans abonnement ni notes de séance.
          </p>
        </div>
        {canAddMore && !showAddForm && (
          <button onClick={() => setShowAddForm(true)} style={{
            background: "transparent", border: `1px solid ${T.teal}`, color: T.teal,
            borderRadius: 8, padding: "0.35rem 0.75rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
          }}>
            + Inviter
          </button>
        )}
      </div>

      {loading ? (
        <LoadingState label="Chargement…" />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          {staff.length === 0 && !showAddForm && (
            <div style={{ color: T.slate, fontSize: 12.5 }}>Aucun compte secrétaire.</div>
          )}
          {staff.map(s => (
            <div key={s.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0.6rem 0", borderBottom: `1px solid ${T.border}`, fontSize: 13,
            }}>
              <div>
                <div style={{ fontWeight: 600, color: T.navy }}>{s.first_name} {s.last_name}</div>
                <div style={{ color: T.slate, fontSize: 11.5 }}>{s.email}</div>
              </div>
              <button onClick={() => removeStaff(s.id)} style={{
                background: "transparent", border: `1px solid ${T.border}`, color: T.red,
                borderRadius: 7, padding: "0.3rem 0.7rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
              }}>
                Retirer
              </button>
            </div>
          ))}
          {!canAddMore && !showAddForm && (
            <p style={{ fontSize: 11.5, color: T.slate, marginTop: 8 }}>
              Limite de {maxStaff} compte(s) secrétaire atteinte pour le plan {plan}.
            </p>
          )}
          {showAddForm && (
            <AddStaffForm
              apiFetch={apiFetch}
              onCancel={() => setShowAddForm(false)}
              onAdded={(created) => { setShowAddForm(false); setStaff(prev => [...prev, created]); }}
            />
          )}
        </>
      )}
    </div>
  );
}

function AddStaffForm({ apiFetch, onAdded, onCancel }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const created = await apiFetch("/api/accounts/staff/", {
        method: "POST",
        body: JSON.stringify({ first_name: firstName, last_name: lastName, email, phone }),
      });
      onAdded(created);
    } catch (err) {
      setError(err.message || "Impossible de créer ce compte.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} style={{
      background: T.cream, border: `1px solid ${T.border}`, borderRadius: 12,
      padding: "1.25rem", display: "flex", flexDirection: "column", gap: 10, marginTop: 12,
    }}>
      <div style={{ display: "flex", gap: 10 }}>
        <input type="text" placeholder="Prénom" value={firstName}
          onChange={e => setFirstName(e.target.value)} required style={{ ...inputStyle, background: T.white }} />
        <input type="text" placeholder="Nom" value={lastName}
          onChange={e => setLastName(e.target.value)} required style={{ ...inputStyle, background: T.white }} />
      </div>
      <input type="email" placeholder="Email" value={email}
        onChange={e => setEmail(e.target.value)} required style={{ ...inputStyle, background: T.white }} />
      <input type="tel" placeholder="Téléphone (optionnel)" value={phone}
        onChange={e => setPhone(e.target.value)} style={{ ...inputStyle, background: T.white }} />
      <p style={{ fontSize: 11.5, color: T.slate }}>
        Un mot de passe temporaire sera envoyé par email à cette adresse.
      </p>
      {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={loading} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 8,
          padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
        }}>
          {loading ? "Création…" : "Créer ce compte"}
        </button>
        <button type="button" onClick={onCancel} style={{
          background: "transparent", color: T.slate, border: `1px solid ${T.border}`, borderRadius: 8,
          padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 600, cursor: "pointer",
        }}>
          Annuler
        </button>
      </div>
    </form>
  );
}

// ── Section Salles (plan Cabinet) ────────────────────────
function RoomsSection({ apiFetch }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRooms(await apiFetch("/api/accounts/rooms/") || []);
    } catch (err) {
      setError(err.message || "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => { load(); }, [load]);

  const addRoom = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setAdding(true);
    setAddError("");
    try {
      const created = await apiFetch("/api/accounts/rooms/", {
        method: "POST", body: JSON.stringify({ name: newName.trim() }),
      });
      setRooms(prev => [...prev, created]);
      setNewName("");
    } catch (err) {
      setAddError(err.message || "Impossible de créer cette salle.");
    } finally {
      setAdding(false);
    }
  };

  const removeRoom = async (id) => {
    if (!window.confirm("Supprimer cette salle ?")) return;
    try {
      await apiFetch(`/api/accounts/rooms/${id}/`, { method: "DELETE" });
      setRooms(prev => prev.filter(r => r.id !== id));
    } catch (err) {
      alert(err.message || "Suppression impossible.");
    }
  };

  return (
    <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>Salles du cabinet</div>
      <p style={{ fontSize: 11.5, color: T.slate, marginBottom: 12 }}>
        Assignez une salle à un RDV pour éviter qu'elle soit réservée deux fois en même temps,
        quel que soit le praticien.
      </p>

      {loading ? (
        <LoadingState label="Chargement…" />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          {rooms.length === 0 && <div style={{ color: T.slate, fontSize: 12.5, marginBottom: 10 }}>Aucune salle enregistrée.</div>}
          {rooms.map(r => (
            <div key={r.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0.5rem 0", borderBottom: `1px solid ${T.border}`, fontSize: 13,
            }}>
              <span style={{ fontWeight: 600, color: T.navy }}>{r.name}</span>
              <button onClick={() => removeRoom(r.id)} style={{
                background: "transparent", border: `1px solid ${T.border}`, color: T.red,
                borderRadius: 7, padding: "0.3rem 0.7rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
              }}>
                Retirer
              </button>
            </div>
          ))}
          <form onSubmit={addRoom} style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <input type="text" placeholder="Ex: Salle 1" value={newName}
              onChange={e => setNewName(e.target.value)} style={{ ...inputStyle, flex: 1 }} />
            <button type="submit" disabled={adding} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 8,
              padding: "0 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap",
            }}>
              {adding ? "…" : "+ Ajouter"}
            </button>
          </form>
          {addError && <div style={{ color: T.red, fontSize: 12, marginTop: 6 }}>{addError}</div>}
        </>
      )}
    </div>
  );
}

// ── Section Abonnement / Facturation ─────────────────────
const PLANS = [
  { id: "starter", name: "Starter", price: "29€/mois", desc: "1 praticien, rappels email" },
  { id: "pro", name: "Pro", price: "49€/mois", desc: "1 praticien, rappels email + SMS" },
  { id: "cabinet", name: "Cabinet", price: "99€/mois", desc: "Jusqu'à 5 praticiens" },
];

function BillingSection({ apiFetch, currentPlan, isActive }) {
  const [loadingPlan, setLoadingPlan] = useState(null);
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [cancelMessage, setCancelMessage] = useState("");

  const cancelSubscription = async () => {
    const ok = window.confirm("Etes-vous sur de vouloir resilier votre abonnement ? Il restera actif jusqu'a la fin de la periode en cours, sans aucun prelevement supplementaire.");
    if (!ok) return;
    setCancelling(true);
    setError("");
    try {
      const data = await apiFetch("/api/billing/cancel/", { method: "POST" });
      setCancelMessage(data.message || "Abonnement resilie.");
    } catch (err) {
      setError(err.message || "Impossible de resilier l'abonnement.");
    } finally {
      setCancelling(false);
    }
  };

  const [planChangeMessage, setPlanChangeMessage] = useState("");

  const choosePlan = async (planId) => {
    setError("");
    setPlanChangeMessage("");
    setLoadingPlan(planId);
    try {
      const data = await apiFetch("/api/billing/checkout/", {
        method: "POST",
        body: JSON.stringify({ plan: planId }),
      });
      if (data && data.checkout_url) {
        window.location.href = data.checkout_url;
      } else if (data && data.message) {
        // Changement de plan applique directement (abonnement deja actif)
        setPlanChangeMessage(data.message);
        setLoadingPlan(null);
      } else {
        throw new Error("Réponse inattendue du serveur.");
      }
    } catch (err) {
      setError(err.message || "Impossible de démarrer le paiement.");
      setLoadingPlan(null);
    }
  };

  return (
    <div style={{ background: T.white, border: `1px solid ${T.border}`, borderRadius: 14, padding: "1.5rem" }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 4 }}>Abonnement</div>
      <p style={{ fontSize: 12.5, color: T.slate, marginBottom: 16 }}>
        {isActive
          ? <>Vous êtes actuellement sur le plan <strong style={{ color: T.teal }}>{currentPlan}</strong>.</>
          : "Choisissez un plan pour activer votre page de réservation en ligne."}
      </p>

      {error && (
        <div style={{ color: T.red, fontSize: 12, marginBottom: 12, background: T.redLt, padding: "0.5rem 0.75rem", borderRadius: 8 }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        {PLANS.map(plan => {
          const isCurrent = isActive && currentPlan === plan.id;
          return (
            <div key={plan.id} style={{
              border: `1px solid ${isCurrent ? T.teal : T.border}`,
              borderRadius: 12, padding: "1rem", textAlign: "center",
              background: isCurrent ? T.tealLt : T.white,
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.navy, textTransform: "uppercase" }}>{plan.name}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: T.navy, margin: "6px 0" }}>{plan.price}</div>
              <div style={{ fontSize: 11, color: T.slate, marginBottom: 12, minHeight: 28 }}>{plan.desc}</div>
              <button
                onClick={() => choosePlan(plan.id)}
                disabled={loadingPlan !== null || isCurrent}
                style={{
                  width: "100%", padding: "0.5rem", border: "none", borderRadius: 8,
                  background: isCurrent ? T.border : T.teal, color: isCurrent ? T.slate : T.white,
                  fontSize: 12, fontWeight: 700, cursor: isCurrent ? "default" : "pointer",
                  opacity: loadingPlan && loadingPlan !== plan.id ? 0.5 : 1,
                }}
              >
                {isCurrent ? "Plan actuel" : loadingPlan === plan.id ? "Redirection…" : "Choisir ce plan"}
              </button>
            </div>
          );
        })}
      </div>

      {planChangeMessage && (
        <div style={{ marginTop: 16, fontSize: 12.5, color: T.teal, background: T.tealLt, padding: "0.75rem", borderRadius: 8 }}>
          {planChangeMessage}
        </div>
      )}

      {isActive && !cancelMessage && (
        <div style={{ marginTop: 16, textAlign: "center" }}>
          <button onClick={cancelSubscription} disabled={cancelling} style={{
            background: "transparent", border: "none", color: T.slate,
            fontSize: 12, textDecoration: "underline", cursor: "pointer",
          }}>
            {cancelling ? "Résiliation en cours…" : "Résilier mon abonnement"}
          </button>
        </div>
      )}

      {cancelMessage && (
        <div style={{ marginTop: 16, fontSize: 12.5, color: T.teal, background: T.tealLt, padding: "0.75rem", borderRadius: 8 }}>
          {cancelMessage}
        </div>
      )}
    </div>
  );
}

function BillingReturnScreen({ status, onContinue }) {
  const isSuccess = status === "success";
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif",
    }}>
      <div style={{
        background: T.white, border: `1px solid ${T.border}`, borderRadius: 14,
        padding: "2.5rem", width: 380, textAlign: "center",
      }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>{isSuccess ? "✅" : "↩️"}</div>
        <h2 style={{ fontFamily: "Georgia, serif", fontSize: 20, color: T.navy, marginBottom: 8 }}>
          {isSuccess ? "Paiement confirmé !" : "Paiement annulé"}
        </h2>
        <p style={{ fontSize: 13, color: T.slate, lineHeight: 1.6, marginBottom: 20 }}>
          {isSuccess
            ? "Votre abonnement est activé. Vous pouvez maintenant profiter de toutes les fonctionnalités de CabinBook."
            : "Aucun paiement n'a été effectué. Vous pouvez choisir un plan à tout moment depuis vos Paramètres."}
        </p>
        <button onClick={onContinue} style={{
          background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.75rem 1.5rem", fontSize: 14, fontWeight: 700, cursor: "pointer",
        }}>
          Accéder à mon tableau de bord →
        </button>
      </div>
    </div>
  );
}

function NewAppointmentModal({ apiFetch, onClose, onCreated, preselectedPatient, practitionerFilter, canUseSeries }) {
  const [slots, setSlots] = useState([]);
  const [patients, setPatients] = useState([]);
  const [practitioners, setPractitioners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [apptType, setApptType] = useState("single"); // "single" | "series"
  const [selectedSlotId, setSelectedSlotId] = useState(null);
  const [mode, setMode] = useState("existing"); // "existing" | "new"
  const [patientSearch, setPatientSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState(preselectedPatient ? preselectedPatient.id : null);
  const [newFirstName, setNewFirstName] = useState("");
  const [newLastName, setNewLastName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [reason, setReason] = useState("");
  const [rooms, setRooms] = useState([]);
  const [selectedRoomId, setSelectedRoomId] = useState("");

  const [seriesPractitionerId, setSeriesPractitionerId] = useState(
    practitionerFilter && practitionerFilter !== "all" ? practitionerFilter : null
  );
  const [seriesStart, setSeriesStart] = useState("");
  const [seriesDuration, setSeriesDuration] = useState(45);
  const [seriesFrequency, setSeriesFrequency] = useState("weekly");
  const [seriesEndMode, setSeriesEndMode] = useState("count");
  const [seriesOccurrences, setSeriesOccurrences] = useState(8);
  const [seriesUntil, setSeriesUntil] = useState("");
  const [seriesResult, setSeriesResult] = useState(null);

  useEffect(() => {
    let active = true;
    const slotSuffix = (practitionerFilter && practitionerFilter !== "all") ? `&practitioner=${practitionerFilter}` : "";
    Promise.all([
      apiFetch(`/api/appointments/timeslots/?is_available=true&ordering=start_time${slotSuffix}`),
      apiFetch("/api/accounts/patients/"),
      apiFetch("/api/accounts/practitioners/"),
      apiFetch("/api/accounts/rooms/").catch(() => []), // absent (plan non-Cabinet) : pas bloquant
    ])
      .then(([slotsData, patientsData, practitionersData, roomsData]) => {
        if (!active) return;
        setSlots((slotsData || []).slice(0, 60));
        setPatients(patientsData || []);
        setPractitioners(practitionersData || []);
        setRooms((roomsData || []).filter(r => r.is_active !== false));
      })
      .catch(err => { if (active) setError(err.message || "Erreur de chargement."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch, practitionerFilter]);

  useEffect(() => {
    if (!seriesPractitionerId && practitioners.length === 1) {
      setSeriesPractitionerId(practitioners[0].id);
    }
  }, [practitioners, seriesPractitionerId]);

  const slotsByDay = {};
  slots.forEach(s => {
    const day = fmtD(s.start_time);
    if (!slotsByDay[day]) slotsByDay[day] = [];
    slotsByDay[day].push(s);
  });

  const selectedSlot = slots.find(s => s.id === selectedSlotId) || null;
  const effectivePractitionerId = apptType === "series"
    ? seriesPractitionerId
    : (selectedSlot ? selectedSlot.practitioner : (practitionerFilter && practitionerFilter !== "all" ? practitionerFilter : null));
  const filteredPatients = patients
    .filter(p => !effectivePractitionerId || p.practitioner === effectivePractitionerId)
    .filter(p =>
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(patientSearch.toLowerCase())
    ).slice(0, 8);

  const submitSingle = async () => {
    if (!selectedSlotId) { setError("Choisissez un créneau."); return; }
    if (mode === "existing" && !selectedPatientId) { setError("Choisissez un patient."); return; }
    if (mode === "new" && (!newFirstName || !newLastName || !newEmail)) {
      setError("Prénom, nom et email du patient sont requis."); return;
    }

    setSubmitting(true);
    try {
      const payload = { timeslot_id: selectedSlotId, reason };
      if (selectedRoomId) payload.room_id = selectedRoomId;
      if (mode === "existing") {
        payload.patient_id = selectedPatientId;
      } else {
        payload.patient = { first_name: newFirstName, last_name: newLastName, email: newEmail, phone: newPhone };
      }
      await apiFetch("/api/appointments/book_manual/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      onCreated();
    } catch (err) {
      setError(err.message || "Impossible de créer le rendez-vous.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitSeries = async () => {
    if (!seriesPractitionerId) { setError("Choisissez un praticien."); return; }
    if (mode === "existing" && !selectedPatientId) { setError("Choisissez un patient."); return; }
    if (mode === "new" && (!newFirstName || !newLastName || !newEmail)) {
      setError("Prénom, nom et email du patient sont requis."); return;
    }
    if (!seriesStart) { setError("Choisissez la date et l'heure de la première séance."); return; }
    if (seriesEndMode === "count" && (!seriesOccurrences || seriesOccurrences < 1)) {
      setError("Indiquez un nombre de séances valide."); return;
    }
    if (seriesEndMode === "until" && !seriesUntil) {
      setError("Indiquez une date de fin."); return;
    }

    setSubmitting(true);
    try {
      let patientId = selectedPatientId;
      if (mode === "new") {
        const createdPatient = await apiFetch("/api/accounts/patients/", {
          method: "POST",
          body: JSON.stringify({
            practitioner: seriesPractitionerId,
            first_name: newFirstName, last_name: newLastName, email: newEmail, phone: newPhone,
          }),
        });
        patientId = createdPatient.id;
      }

      const payload = {
        practitioner: seriesPractitionerId,
        patient_id: patientId,
        first_start_time: new Date(seriesStart).toISOString(),
        duration_minutes: Number(seriesDuration),
        frequency: seriesFrequency,
        reason,
      };
      if (seriesEndMode === "count") payload.occurrences_total = Number(seriesOccurrences);
      else payload.until = seriesUntil;

      const result = await apiFetch("/api/appointments/series/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSeriesResult(result);
    } catch (err) {
      setError(err.message || "Impossible de créer la série.");
    } finally {
      setSubmitting(false);
    }
  };

  const submit = () => {
    setError("");
    return apptType === "series" ? submitSeries() : submitSingle();
  };

  if (seriesResult) {
    const total = (seriesResult.created || []).length + (seriesResult.conflicts || []).length;
    return (
      <div style={{
        position: "fixed", inset: 0, background: "rgba(15,27,45,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
      }}>
        <div style={{ background: T.white, borderRadius: 14, padding: "1.75rem", width: 460 }}>
          <h2 style={{ fontFamily: "Georgia, serif", fontSize: 18, color: T.navy, marginBottom: 12 }}>Série créée</h2>
          <p style={{ fontSize: 13.5, color: T.navy, marginBottom: 12 }}>
            <strong>{(seriesResult.created || []).length}</strong> séance(s) programmée(s) sur {total}.
          </p>
          {(seriesResult.conflicts || []).length > 0 && (
            <div style={{ background: T.amberLt, borderRadius: 10, padding: "0.75rem 1rem", marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.amber, marginBottom: 6 }}>
                {seriesResult.conflicts.length} séance(s) en conflit — à reprogrammer manuellement :
              </div>
              {seriesResult.conflicts.map((c, i) => (
                <div key={i} style={{ fontSize: 12, color: T.navy, marginBottom: 2 }}>
                  · Séance {c.series_position} — {fmtD(c.date)} {fmt(c.date)} ({c.reason})
                </div>
              ))}
            </div>
          )}
          <button onClick={onCreated} style={{
            width: "100%", background: T.teal, color: T.white, border: "none", borderRadius: 10,
            padding: "0.75rem", fontSize: 14, fontWeight: 700, cursor: "pointer",
          }}>Fermer</button>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15,27,45,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div style={{
        background: T.white, borderRadius: 14, padding: "1.75rem", width: 480,
        maxHeight: "85vh", overflowY: "auto",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ fontFamily: "Georgia, serif", fontSize: 18, color: T.navy }}>
            {apptType === "series" ? "Nouvelle série de rendez-vous" : "Nouveau rendez-vous"}
          </h2>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, color: T.slate, cursor: "pointer" }}>✕</button>
        </div>

        {loading ? (
          <LoadingState label="Chargement des créneaux…" />
        ) : (
          <>
            {error && (
              <div style={{ color: T.red, fontSize: 12, marginBottom: 12, background: T.redLt, padding: "0.5rem 0.75rem", borderRadius: 8 }}>
                {error}
              </div>
            )}

            {canUseSeries && (
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <button onClick={() => setApptType("single")} style={{
                  flex: 1, padding: "0.4rem", borderRadius: 8, fontSize: 12, fontWeight: 700,
                  border: `1px solid ${apptType === "single" ? T.teal : T.border}`,
                  background: apptType === "single" ? T.tealLt : T.white, color: T.navy, cursor: "pointer",
                }}>
                  RDV unique
                </button>
                <button onClick={() => setApptType("series")} style={{
                  flex: 1, padding: "0.4rem", borderRadius: 8, fontSize: 12, fontWeight: 700,
                  border: `1px solid ${apptType === "series" ? T.teal : T.border}`,
                  background: apptType === "series" ? T.tealLt : T.white, color: T.navy, cursor: "pointer",
                }}>
                  🔁 Série récurrente
                </button>
              </div>
            )}

            {apptType === "series" ? (
              <div style={{ marginBottom: 16 }}>
                {practitioners.length > 1 && (
                  <div style={{ marginBottom: 10 }}>
                    <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                      Praticien
                    </label>
                    <select value={seriesPractitionerId || ""} onChange={e => setSeriesPractitionerId(Number(e.target.value) || null)} style={inputStyle}>
                      <option value="">Choisir…</option>
                      {practitioners.map(p => (
                        <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                      ))}
                    </select>
                  </div>
                )}
                <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                  Première séance
                </label>
                <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                  <input type="datetime-local" value={seriesStart} onChange={e => setSeriesStart(e.target.value)} style={inputStyle} />
                  <select value={seriesDuration} onChange={e => setSeriesDuration(Number(e.target.value))} style={{ ...inputStyle, width: 120 }}>
                    <option value={15}>15 min</option>
                    <option value={20}>20 min</option>
                    <option value={30}>30 min</option>
                    <option value={45}>45 min</option>
                    <option value={60}>1 heure</option>
                    <option value={90}>1h30</option>
                  </select>
                </div>

                <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                  Fréquence
                </label>
                <select value={seriesFrequency} onChange={e => setSeriesFrequency(e.target.value)} style={{ ...inputStyle, marginBottom: 10 }}>
                  <option value="weekly">Toutes les semaines</option>
                  <option value="biweekly">Toutes les deux semaines</option>
                  <option value="monthly">Tous les mois</option>
                </select>

                <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                  Fin de la série
                </label>
                <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                  <button onClick={() => setSeriesEndMode("count")} style={{
                    flex: 1, padding: "0.4rem", borderRadius: 8, fontSize: 12, fontWeight: 700,
                    border: `1px solid ${seriesEndMode === "count" ? T.teal : T.border}`,
                    background: seriesEndMode === "count" ? T.tealLt : T.white, color: T.navy, cursor: "pointer",
                  }}>
                    Nombre de séances
                  </button>
                  <button onClick={() => setSeriesEndMode("until")} style={{
                    flex: 1, padding: "0.4rem", borderRadius: 8, fontSize: 12, fontWeight: 700,
                    border: `1px solid ${seriesEndMode === "until" ? T.teal : T.border}`,
                    background: seriesEndMode === "until" ? T.tealLt : T.white, color: T.navy, cursor: "pointer",
                  }}>
                    Jusqu'à une date
                  </button>
                </div>
                {seriesEndMode === "count" ? (
                  <input type="number" min={1} max={52} value={seriesOccurrences}
                    onChange={e => setSeriesOccurrences(e.target.value)} style={inputStyle} placeholder="Nombre de séances" />
                ) : (
                  <input type="date" value={seriesUntil} onChange={e => setSeriesUntil(e.target.value)} style={inputStyle} />
                )}
              </div>
            ) : (
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                  Créneau
                </label>
                {Object.keys(slotsByDay).length === 0 && (
                  <p style={{ fontSize: 12.5, color: T.slate }}>Aucun créneau disponible.</p>
                )}
                <div style={{ maxHeight: 160, overflowY: "auto", border: `1px solid ${T.border}`, borderRadius: 8, padding: 8 }}>
                  {Object.entries(slotsByDay).map(([day, daySlots]) => (
                    <div key={day} style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: T.navy, marginBottom: 4, textTransform: "capitalize" }}>{day}</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {daySlots.map(s => (
                          <button key={s.id} onClick={() => setSelectedSlotId(s.id)} style={{
                            padding: "0.35rem 0.6rem", borderRadius: 7, fontSize: 12,
                            border: `1px solid ${selectedSlotId === s.id ? T.teal : T.border}`,
                            background: selectedSlotId === s.id ? T.teal : T.white,
                            color: selectedSlotId === s.id ? T.white : T.navy,
                            cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", lineHeight: 1.3,
                          }}>
                            <span>{fmt(s.start_time)}</span>
                            {s.practitioner_name && (
                              <span style={{ fontSize: 9.5, opacity: 0.75 }}>{s.practitioner_name}</span>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                Patient
              </label>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <button onClick={() => setMode("existing")} style={{
                  flex: 1, padding: "0.4rem", borderRadius: 8, fontSize: 12, fontWeight: 700,
                  border: `1px solid ${mode === "existing" ? T.teal : T.border}`,
                  background: mode === "existing" ? T.tealLt : T.white, color: T.navy, cursor: "pointer",
                }}>
                  Patient existant
                </button>
                <button onClick={() => setMode("new")} style={{
                  flex: 1, padding: "0.4rem", borderRadius: 8, fontSize: 12, fontWeight: 700,
                  border: `1px solid ${mode === "new" ? T.teal : T.border}`,
                  background: mode === "new" ? T.tealLt : T.white, color: T.navy, cursor: "pointer",
                }}>
                  Nouveau patient
                </button>
              </div>

              {mode === "existing" ? (
                <>
                  {!effectivePractitionerId && (
                    <p style={{ fontSize: 11.5, color: T.slate, marginBottom: 8, fontStyle: "italic" }}>
                      {apptType === "series"
                        ? "Choisissez d'abord un praticien pour voir les patients correspondants."
                        : "Choisissez d'abord un créneau pour voir les patients du praticien correspondant."}
                    </p>
                  )}
                  <input type="text" placeholder="Rechercher un patient…" value={patientSearch}
                    onChange={e => setPatientSearch(e.target.value)} style={{ ...inputStyle, marginBottom: 6 }} />
                  <div style={{ maxHeight: 140, overflowY: "auto" }}>
                    {filteredPatients.map(p => (
                      <div key={p.id} onClick={() => setSelectedPatientId(p.id)} style={{
                        padding: "0.5rem 0.6rem", borderRadius: 7, cursor: "pointer", fontSize: 13,
                        background: selectedPatientId === p.id ? T.tealLt : "transparent",
                        border: `1px solid ${selectedPatientId === p.id ? T.teal : "transparent"}`,
                      }}>
                        {p.first_name} {p.last_name} <span style={{ color: T.slate, fontSize: 11 }}>· {p.email}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input type="text" placeholder="Prénom" value={newFirstName} onChange={e => setNewFirstName(e.target.value)} style={inputStyle} />
                    <input type="text" placeholder="Nom" value={newLastName} onChange={e => setNewLastName(e.target.value)} style={inputStyle} />
                  </div>
                  <input type="email" placeholder="Email" value={newEmail} onChange={e => setNewEmail(e.target.value)} style={inputStyle} />
                  <input type="tel" placeholder="Téléphone (optionnel)" value={newPhone} onChange={e => setNewPhone(e.target.value)} style={inputStyle} />
                </div>
              )}
            </div>

            {rooms.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                  Salle (optionnel)
                </label>
                <select value={selectedRoomId} onChange={e => setSelectedRoomId(e.target.value)} style={inputStyle}>
                  <option value="">Aucune salle assignée</option>
                  {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
            )}

            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 6 }}>
                Motif (optionnel)
              </label>
              <textarea value={reason} onChange={e => setReason(e.target.value)} rows={2}
                style={{ ...inputStyle, resize: "vertical", width: "100%" }} />
            </div>

            <button onClick={submit} disabled={submitting} style={{
              width: "100%", background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.75rem", fontSize: 14, fontWeight: 700, cursor: "pointer",
              opacity: submitting ? 0.7 : 1,
            }}>
              {submitting
                ? "Création…"
                : (apptType === "series" ? "Créer la série" : "Créer le rendez-vous")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Import de patients via CSV ────────────────────────────
function ImportPatientsCsvModal({ apiFetch, defaultPractitioner, onClose, onImported }) {
  const [practitioners, setPractitioners] = useState([]);
  const [practitionerId, setPractitionerId] = useState(defaultPractitioner || "");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    apiFetch("/api/accounts/practitioners/")
      .then(list => {
        setPractitioners(list || []);
        if (!defaultPractitioner && list && list.length > 0) setPractitionerId(list[0].id);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!file || !practitionerId) return;
    setError("");
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("practitioner", practitionerId);
      formData.append("file", file);
      const data = await apiFetch("/api/accounts/patients/import_csv/", {
        method: "POST", body: formData,
      });
      setResult(data);
    } catch (err) {
      setError(err.message || "Import impossible.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15,27,45,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div style={{ background: T.white, borderRadius: 14, padding: "1.75rem", width: 460, maxHeight: "85vh", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ fontFamily: "Georgia, serif", fontSize: 18, color: T.navy }}>Importer des patients (CSV)</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, color: T.slate, cursor: "pointer" }}>✕</button>
        </div>

        {result ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p style={{ fontSize: 13.5, color: T.navy }}>
              <strong style={{ color: T.teal }}>{result.created}</strong> patient(s) importé(s),{" "}
              <strong>{result.skipped}</strong> ignoré(s).
            </p>
            {result.errors && result.errors.length > 0 && (
              <div style={{ background: T.cream, borderRadius: 8, padding: "0.75rem", maxHeight: 160, overflowY: "auto" }}>
                {result.errors.map((e, i) => (
                  <div key={i} style={{ fontSize: 11.5, color: T.slate }}>{e}</div>
                ))}
              </div>
            )}
            <button onClick={onImported} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.7rem", fontSize: 13.5, fontWeight: 700, cursor: "pointer",
            }}>
              Terminé
            </button>
          </div>
        ) : (
          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p style={{ fontSize: 12.5, color: T.slate, lineHeight: 1.5 }}>
              Fichier CSV avec colonnes <strong>prénom</strong> et <strong>nom</strong> (requis),
              email et téléphone (optionnels). Les doublons (même email) sont ignorés automatiquement.
            </p>

            {practitioners.length > 1 && (
              <select value={practitionerId} onChange={e => setPractitionerId(e.target.value)} style={inputStyle}>
                {practitioners.map(p => (
                  <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                ))}
              </select>
            )}

            <input type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files[0] || null)} style={inputStyle} />

            {error && (
              <div style={{ color: T.red, fontSize: 12, background: T.redLt, padding: "0.5rem 0.75rem", borderRadius: 8 }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading || !file} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.7rem", fontSize: 13.5, fontWeight: 700, cursor: (loading || !file) ? "default" : "pointer",
              opacity: (loading || !file) ? 0.6 : 1,
            }}>
              {loading ? "Import en cours…" : "Importer"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function PatientDetailModal({ apiFetch, patient, role, onClose, onUpdated, onNewAppointment, onDeactivated }) {
  const [notes, setNotes] = useState(patient.notes || "");
  const [carteVitale, setCarteVitale] = useState(patient.carte_vitale_number || "");
  const [phone, setPhone] = useState(patient.phone || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  const [appointments, setAppointments] = useState([]);
  const [loadingAppts, setLoadingAppts] = useState(true);
  const [expandedApptId, setExpandedApptId] = useState(null);

  useEffect(() => {
    let active = true;
    apiFetch(`/api/appointments/?patient=${patient.id}&ordering=-start_time`)
      .then(data => { if (active) setAppointments(data || []); })
      .catch(() => {})
      .finally(() => { if (active) setLoadingAppts(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch, patient.id]);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const updated = await apiFetch(`/api/accounts/patients/${patient.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ notes, carte_vitale_number: carteVitale, phone }),
      });
      onUpdated(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      setError(err.message || "Erreur lors de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async () => {
    const ok = window.confirm(
      `Etes-vous sur de vouloir supprimer ${patient.first_name} ${patient.last_name} ? ` +
      `Le patient sera retire de votre liste, mais l'historique de ses rendez-vous sera conserve.`
    );
    if (!ok) return;
    setDeleting(true);
    setError("");
    try {
      await apiFetch(`/api/accounts/patients/${patient.id}/deactivate/`, { method: "POST" });
      onDeactivated(patient.id);
    } catch (err) {
      setError(err.message || "Erreur lors de la suppression.");
      setDeleting(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15,27,45,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div style={{
        background: T.white, borderRadius: 14, padding: "1.75rem", width: 520,
        maxHeight: "85vh", overflowY: "auto",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h2 style={{ fontFamily: "Georgia, serif", fontSize: 18, color: T.navy }}>
              {patient.first_name} {patient.last_name}
            </h2>
            <p style={{ fontSize: 12, color: T.slate }}>{patient.email}</p>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, color: T.slate, cursor: "pointer" }}>✕</button>
        </div>

        <button onClick={() => onNewAppointment(patient)} style={{
          width: "100%", background: T.teal, color: T.white, border: "none", borderRadius: 10,
          padding: "0.65rem", fontSize: 13, fontWeight: 700, cursor: "pointer", marginBottom: 16,
        }}>
          + Nouveau rendez-vous pour ce patient
        </button>

        <div style={{ background: T.cream, borderRadius: 12, padding: "1rem", marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: T.navy, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Informations
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div>
              <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 3 }}>Téléphone</label>
              <input type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                style={{ ...inputStyle, background: T.white, width: "100%" }} />
            </div>
            <div>
              <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 3 }}>
                Numéro de carte Vitale
              </label>
              <input type="text" value={carteVitale} onChange={e => setCarteVitale(e.target.value)}
                placeholder="1 XX XX XX XXX XXX XX" maxLength={15}
                style={{ ...inputStyle, background: T.white, width: "100%" }} />
            </div>
            <div>
              <label style={{ fontSize: 10.5, color: T.slate, display: "block", marginBottom: 3 }}>Notes</label>
              <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
                style={{ ...inputStyle, background: T.white, width: "100%", resize: "vertical" }} />
            </div>
          </div>
          {error && <div style={{ color: T.red, fontSize: 12, marginTop: 8 }}>{error}</div>}
          <button onClick={save} disabled={saving} style={{
            marginTop: 10, background: saved ? T.teal : T.navy, color: T.white, border: "none",
            borderRadius: 8, padding: "0.5rem 1rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
          }}>
            {saving ? "Enregistrement…" : saved ? "✓ Enregistré" : "Enregistrer les modifications"}
          </button>
        </div>

        <button onClick={handleDeactivate} disabled={deleting} style={{
          width: "100%", background: "transparent", color: T.red, border: `1px solid ${T.red}`,
          borderRadius: 10, padding: "0.55rem", fontSize: 12.5, fontWeight: 700, cursor: "pointer",
          marginBottom: 16,
        }}>
          {deleting ? "Suppression…" : "Supprimer ce patient"}
        </button>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: T.navy, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Historique des rendez-vous
          </div>
          {loadingAppts ? (
            <LoadingState label="Chargement…" />
          ) : appointments.length === 0 ? (
            <p style={{ fontSize: 12.5, color: T.slate }}>Aucun rendez-vous pour ce patient.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 340, overflowY: "auto" }}>
              {appointments.map(a => (
                <div key={a.id} style={{ border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden" }}>
                  <div onClick={() => setExpandedApptId(id => id === a.id ? null : a.id)} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "0.5rem 0.75rem", fontSize: 12.5, cursor: "pointer",
                  }}>
                    <span>
                      {fmtD(a.start_time)} · {fmt(a.start_time)}
                      {a.has_note && <span title="Note de séance enregistrée" style={{ marginLeft: 6 }}>📝</span>}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <StatusBadge status={a.status} />
                      <span style={{ color: T.slate, fontSize: 11 }}>{expandedApptId === a.id ? "▲" : "▼"}</span>
                    </div>
                  </div>
                  {expandedApptId === a.id && (
                    <AppointmentHistoryDetail apiFetch={apiFetch} appointment={a} role={role}
                      onNoteSaved={() => setAppointments(prev => prev.map(x => x.id === a.id ? { ...x, has_note: true } : x))} />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AppointmentHistoryDetail({ apiFetch, appointment, role, onNoteSaved }) {
  const canSeeNote = role !== "secretary";
  const [noteContent, setNoteContent] = useState("");
  const [loadingNote, setLoadingNote] = useState(true);
  const [savingNote, setSavingNote] = useState(false);
  const [noteSaved, setNoteSaved] = useState(false);

  const [invoice, setInvoice] = useState(null);
  const [loadingInvoice, setLoadingInvoice] = useState(true);
  const [invoiceAmount, setInvoiceAmount] = useState("");
  const [invoiceBusy, setInvoiceBusy] = useState(false);
  const [invoiceError, setInvoiceError] = useState("");
  const [editingAmount, setEditingAmount] = useState(false);
  const [editAmountValue, setEditAmountValue] = useState("");

  useEffect(() => {
    let active = true;
    if (canSeeNote) {
      apiFetch(`/api/appointments/${appointment.id}/note/`)
        .then(data => { if (active) setNoteContent(data?.content || ""); })
        .catch(() => {})
        .finally(() => { if (active) setLoadingNote(false); });
    }
    apiFetch(`/api/billing/invoices/?appointment=${appointment.id}`)
      .then(data => { if (active) setInvoice((data && data[0]) || null); })
      .catch(() => {})
      .finally(() => { if (active) setLoadingInvoice(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiFetch, appointment.id]);

  const saveNote = async () => {
    setSavingNote(true);
    try {
      await apiFetch(`/api/appointments/${appointment.id}/note/`, {
        method: "POST", body: JSON.stringify({ content: noteContent }),
      });
      setNoteSaved(true);
      onNoteSaved && onNoteSaved();
      setTimeout(() => setNoteSaved(false), 1500);
    } catch (err) {
      // silencieux : l'utilisateur peut retenter
    } finally {
      setSavingNote(false);
    }
  };

  const generateInvoice = async () => {
    const cents = Math.round(parseFloat(invoiceAmount.replace(",", ".")) * 100);
    if (!cents || cents <= 0) { setInvoiceError("Indiquez un montant valide."); return; }
    setInvoiceBusy(true);
    setInvoiceError("");
    try {
      const created = await apiFetch("/api/billing/invoices/", {
        method: "POST", body: JSON.stringify({ appointment: appointment.id, amount_cents: cents }),
      });
      setInvoice(created);
    } catch (err) {
      setInvoiceError(err.message || "Impossible de générer la facture.");
    } finally {
      setInvoiceBusy(false);
    }
  };

  const markPaid = async () => {
    setInvoiceBusy(true);
    try {
      const updated = await apiFetch(`/api/billing/invoices/${invoice.id}/mark_paid/`, { method: "POST" });
      setInvoice(updated);
    } catch (err) {
      setInvoiceError(err.message || "Action impossible.");
    } finally {
      setInvoiceBusy(false);
    }
  };

  const startEditAmount = () => {
    setEditAmountValue((invoice.amount_cents / 100).toFixed(2));
    setInvoiceError("");
    setEditingAmount(true);
  };

  const saveAmount = async () => {
    const cents = Math.round(parseFloat(editAmountValue.replace(",", ".")) * 100);
    if (!cents || cents <= 0) { setInvoiceError("Indiquez un montant valide."); return; }
    setInvoiceBusy(true);
    setInvoiceError("");
    try {
      const updated = await apiFetch(`/api/billing/invoices/${invoice.id}/`, {
        method: "PATCH", body: JSON.stringify({ amount_cents: cents }),
      });
      setInvoice(updated);
      setEditingAmount(false);
    } catch (err) {
      setInvoiceError(err.message || "Impossible de modifier le montant.");
    } finally {
      setInvoiceBusy(false);
    }
  };

  const sendPaymentLink = async () => {
    setInvoiceBusy(true);
    setInvoiceError("");
    try {
      const { checkout_url } = await apiFetch(`/api/billing/invoices/${invoice.id}/create_payment_link/`, { method: "POST" });
      await navigator.clipboard.writeText(checkout_url).catch(() => {});
      window.open(checkout_url, "_blank", "noopener");
    } catch (err) {
      setInvoiceError(err.message || "Impossible de créer le lien de paiement.");
    } finally {
      setInvoiceBusy(false);
    }
  };

  const refundInvoice = async () => {
    if (!window.confirm("Rembourser cette facture ? Si elle a été payée par carte, le remboursement Stripe est immédiat et irréversible.")) return;
    setInvoiceBusy(true);
    setInvoiceError("");
    try {
      const updated = await apiFetch(`/api/billing/invoices/${invoice.id}/refund/`, { method: "POST" });
      setInvoice(updated);
    } catch (err) {
      setInvoiceError(err.message || "Impossible de rembourser cette facture.");
    } finally {
      setInvoiceBusy(false);
    }
  };

  return (
    <div style={{ borderTop: `1px solid ${T.border}`, padding: "0.75rem", background: T.cream, display: "flex", flexDirection: "column", gap: 12 }}>
      {canSeeNote && (
        <div>
          <label style={{ fontSize: 10.5, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 4 }}>
            Note de séance
          </label>
          {loadingNote ? (
            <p style={{ fontSize: 11.5, color: T.slate }}>Chargement…</p>
          ) : (
            <>
              <textarea value={noteContent} onChange={e => setNoteContent(e.target.value)} rows={3}
                placeholder="Bilan, observations, évolution…"
                style={{ ...inputStyle, background: T.white, width: "100%", resize: "vertical", fontSize: 12.5 }} />
              <button onClick={saveNote} disabled={savingNote} style={{
                marginTop: 6, background: noteSaved ? T.teal : T.navy, color: T.white, border: "none",
                borderRadius: 7, padding: "0.4rem 0.8rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
              }}>
                {savingNote ? "Enregistrement…" : noteSaved ? "✓ Enregistré" : "Enregistrer la note"}
              </button>
            </>
          )}
        </div>
      )}

      <div>
        <label style={{ fontSize: 10.5, fontWeight: 700, color: T.slate, textTransform: "uppercase", display: "block", marginBottom: 4 }}>
          Facturation
        </label>
        {loadingInvoice ? (
          <p style={{ fontSize: 11.5, color: T.slate }}>Chargement…</p>
        ) : invoiceError ? (
          <p style={{ fontSize: 11.5, color: T.red, marginBottom: 6 }}>{invoiceError}</p>
        ) : null}
        {!loadingInvoice && !invoice && (
          <div style={{ display: "flex", gap: 6 }}>
            <input type="text" inputMode="decimal" placeholder="Montant (€)" value={invoiceAmount}
              onChange={e => setInvoiceAmount(e.target.value)}
              style={{ ...inputStyle, background: T.white, width: 110, fontSize: 12.5 }} />
            <button onClick={generateInvoice} disabled={invoiceBusy} style={{
              background: T.navy, color: T.white, border: "none", borderRadius: 7,
              padding: "0.4rem 0.8rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
            }}>
              {invoiceBusy ? "…" : "Générer une facture"}
            </button>
          </div>
        )}
        {invoice && editingAmount ? (
          <div style={{ display: "flex", gap: 6 }}>
            <input type="text" inputMode="decimal" placeholder="Montant (€)" value={editAmountValue}
              onChange={e => setEditAmountValue(e.target.value)}
              style={{ ...inputStyle, background: T.white, width: 110, fontSize: 12.5 }} />
            <button onClick={saveAmount} disabled={invoiceBusy} style={{
              background: T.navy, color: T.white, border: "none", borderRadius: 7,
              padding: "0.4rem 0.8rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
            }}>
              {invoiceBusy ? "…" : "Enregistrer"}
            </button>
            <button onClick={() => setEditingAmount(false)} disabled={invoiceBusy} style={{
              background: "transparent", color: T.slate, border: `1px solid ${T.border}`, borderRadius: 7,
              padding: "0.4rem 0.8rem", fontSize: 11.5, fontWeight: 700, cursor: "pointer",
            }}>Annuler</button>
          </div>
        ) : invoice && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>
              {(invoice.amount_cents / 100).toFixed(2)} €
            </span>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "0.15rem 0.5rem", borderRadius: 6,
              background: invoice.status === "paid" ? T.tealLt : invoice.status === "refunded" ? "#F0F0F0" : T.amberLt,
              color: invoice.status === "paid" ? T.teal : invoice.status === "refunded" ? T.slate : T.amber,
            }}>
              {invoice.status_display}
            </span>
            {invoice.status === "unpaid" && (
              <>
                <button onClick={startEditAmount} disabled={invoiceBusy} style={{
                  background: "transparent", color: T.navy, border: `1px solid ${T.border}`, borderRadius: 7,
                  padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
                }}>Modifier le montant</button>
                <button onClick={markPaid} disabled={invoiceBusy} style={{
                  background: T.teal, color: T.white, border: "none", borderRadius: 7,
                  padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
                }}>Marquer payée</button>
                <button onClick={sendPaymentLink} disabled={invoiceBusy} style={{
                  background: "transparent", color: T.navy, border: `1px solid ${T.border}`, borderRadius: 7,
                  padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
                }}>Lien de paiement en ligne</button>
              </>
            )}
            {invoice.status === "paid" && (
              <button onClick={refundInvoice} disabled={invoiceBusy} style={{
                background: "transparent", color: T.red, border: `1px solid ${T.red}`, borderRadius: 7,
                padding: "0.35rem 0.7rem", fontSize: 11, fontWeight: 700, cursor: "pointer",
              }}>{invoiceBusy ? "…" : "Rembourser"}</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ForgotPasswordScreen({ onGoToLogin }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/accounts/password-reset/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error("Une erreur est survenue.");
      setSent(true);
    } catch (err) {
      setError(err.message || "Impossible d'envoyer la demande.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif",
    }}>
      <div style={{
        background: T.white, border: `1px solid ${T.border}`, borderRadius: 14,
        padding: "2rem", width: 340, display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ fontFamily: "Georgia, serif", fontSize: "1.4rem", color: T.navy, textAlign: "center", marginBottom: 4 }}>
          Cabin<span style={{ color: T.teal }}>Book</span>
        </div>
        {sent ? (
          <>
            <p style={{ fontSize: 13, color: T.slate, textAlign: "center", lineHeight: 1.6 }}>
              Si un compte existe avec cet email, un lien de réinitialisation vient de vous être envoyé.
              Vérifiez votre boîte de réception (et vos spams).
            </p>
            <button onClick={onGoToLogin} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.7rem", fontSize: 13.5, fontWeight: 700, cursor: "pointer",
            }}>
              Retour à la connexion
            </button>
          </>
        ) : (
          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p style={{ fontSize: 12.5, color: T.slate, marginTop: -6 }}>
              Indiquez votre email, nous vous enverrons un lien pour choisir un nouveau mot de passe.
            </p>
            <input type="email" placeholder="Email" value={email}
              onChange={e => setEmail(e.target.value)} required style={inputStyle} />
            {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
            <button type="submit" disabled={loading} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.7rem", fontSize: 13.5, fontWeight: 700, cursor: "pointer",
              opacity: loading ? 0.7 : 1,
            }}>
              {loading ? "Envoi…" : "Envoyer le lien"}
            </button>
            <button type="button" onClick={onGoToLogin} style={{
              background: "transparent", border: "none", color: T.slate,
              fontSize: 12, cursor: "pointer", textDecoration: "underline",
            }}>
              Retour à la connexion
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function ResetPasswordScreen({ uid, token, onDone }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/accounts/password-reset-confirm/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid, token, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Lien invalide ou expiré.");
      setSuccess(true);
    } catch (err) {
      setError(err.message || "Impossible de réinitialiser le mot de passe.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif",
    }}>
      <div style={{
        background: T.white, border: `1px solid ${T.border}`, borderRadius: 14,
        padding: "2rem", width: 340, display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ fontFamily: "Georgia, serif", fontSize: "1.4rem", color: T.navy, textAlign: "center", marginBottom: 4 }}>
          Cabin<span style={{ color: T.teal }}>Book</span>
        </div>
        {success ? (
          <>
            <p style={{ fontSize: 13, color: T.slate, textAlign: "center" }}>
              Votre mot de passe a été réinitialisé avec succès.
            </p>
            <button onClick={onDone} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.7rem", fontSize: 13.5, fontWeight: 700, cursor: "pointer",
            }}>
              Se connecter
            </button>
          </>
        ) : (
          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p style={{ fontSize: 12.5, color: T.slate, marginTop: -6 }}>
              Choisissez votre nouveau mot de passe.
            </p>
            <input type="password" placeholder="Nouveau mot de passe (8 caractères min.)" value={password}
              onChange={e => setPassword(e.target.value)} required minLength={8} style={inputStyle} />
            <input type="password" placeholder="Confirmer le mot de passe" value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)} required style={inputStyle} />
            {error && <div style={{ color: T.red, fontSize: 12 }}>{error}</div>}
            <button type="submit" disabled={loading} style={{
              background: T.teal, color: T.white, border: "none", borderRadius: 10,
              padding: "0.7rem", fontSize: 13.5, fontWeight: 700, cursor: "pointer",
              opacity: loading ? 0.7 : 1,
            }}>
              {loading ? "Enregistrement…" : "Réinitialiser le mot de passe"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

// ── App root ─────────────────────────────────────────────
export default function App() {
  const urlParams = new URLSearchParams(window.location.search);
  const path = window.location.pathname;
  const isResetPasswordPath = path.startsWith("/reset-password");
  const resetUid = urlParams.get("uid");
  const resetToken = urlParams.get("token");
  const initialScreen = isResetPasswordPath ? "reset-password" : (urlParams.get("signup") === "1" ? "register" : "login");
  const initialPlan = urlParams.get("plan");
  const [billingReturn, setBillingReturn] = useState(
    path.startsWith("/billing/success") ? "success"
    : path.startsWith("/billing/cancel") ? "cancel"
    : null
  );
  const [calendarReturn, setCalendarReturn] = useState(urlParams.get("calendar"));

  const [nav, setNav] = useState(calendarReturn ? "settings" : "dashboard");
  const [authScreen, setAuthScreen] = useState(initialScreen);
  const [pendingPlan, setPendingPlan] = useState(initialPlan);
  const [isAuthenticated, setIsAuthenticated] = useState(null); // null = verification en cours
  const [me, setMe] = useState(null);
  const [hasPractitioner, setHasPractitioner] = useState(null); // null = pas encore vérifié, true/false ensuite
  const [allPractitioners, setAllPractitioners] = useState([]);
  const [practitionerFilter, setPractitionerFilter] = useState(null);

  useEffect(() => {
    if (isAuthenticated && (window.location.search || window.location.pathname !== "/")) {
      window.history.replaceState({}, "", "/");
    }
  }, [isAuthenticated]);

  const logout = useCallback(() => {
    fetch(`${API_BASE}/api/auth/logout/`, { method: "POST", credentials: "include" }).catch(() => {});
    setIsAuthenticated(false);
    setMe(null);
  }, []);

  // Helper d'appel API : ajoute le token, rafraîchit si expiré (401)
  const apiFetch = useCallback(async (path, options = {}) => {
    const isFormData = options.body instanceof FormData;
    const doFetch = () => fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(options.headers || {}),
      },
    });
    let res;
    try {
      res = await doFetch();
    } catch (err) {
      throw new Error("Impossible de joindre l'API. Vérifiez que le backend tourne sur " + API_BASE + " et que CORS est configuré.");
    }
    if (res.status === 401) {
      const refreshRes = await fetch(`${API_BASE}/api/auth/token/refresh/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (refreshRes.ok) {
        res = await doFetch();
      } else {
        logout();
        throw new Error("Session expirée, reconnectez-vous.");
      }
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.error || `Erreur API (${res.status})`);
    }
    if (options.raw) return res;
    return res.status === 204 ? null : res.json();
  }, [logout]);


  // Charge le profil utilisateur (plan, nom...) et marque la session comme authentifiée.
  const loadMe = useCallback(() => {
    return apiFetch("/api/accounts/me/")
      .then(data => { setMe(data); setIsAuthenticated(true); })
      .catch(() => setIsAuthenticated(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Verification de la session au demarrage (le cookie httpOnly est envoye automatiquement)
  useEffect(() => {
    loadMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Verifier si l'utilisateur a deja un profil praticien configure
  const checkPractitioner = useCallback(() => {
    if (!isAuthenticated) return;
    apiFetch("/api/accounts/practitioners/")
      .then(list => {
        setHasPractitioner(Array.isArray(list) && list.length > 0);
        setAllPractitioners(list || []);
        if (list && list.length > 0) setPractitionerFilter(prev => (prev && prev !== "all" && list.some(p => p.id === prev)) ? prev : list[0].id);
      })
      .catch(() => setHasPractitioner(false));
  }, [isAuthenticated, apiFetch]);

  useEffect(() => {
    checkPractitioner();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  if (billingReturn) {
    return <BillingReturnScreen status={billingReturn} onContinue={() => { setBillingReturn(null); window.history.replaceState({}, "", "/"); }} />;
  }

  if (authScreen === "reset-password") {
    return (
      <ResetPasswordScreen
        uid={resetUid}
        token={resetToken}
        onDone={() => {
          window.history.replaceState({}, "", "/");
          setAuthScreen("login");
        }}
      />
    );
  }

  if (isAuthenticated === null) {
    return <LoadingState label="Chargement…" />;
  }

  if (!isAuthenticated) {
    if (authScreen === "register") {
      return (
        <RegisterScreen
          onRegistered={loadMe}
          onGoToLogin={() => setAuthScreen("login")}
        />
      );
    }
    if (authScreen === "forgot-password") {
      return <ForgotPasswordScreen onGoToLogin={() => setAuthScreen("login")} />;
    }
    return (
      <LoginScreen
        onLogin={loadMe}
        onGoToRegister={() => setAuthScreen("register")}
        onGoToForgotPassword={() => setAuthScreen("forgot-password")}
      />
    );
  }

  const userLabel = me ? `${me.first_name || ""} ${me.last_name || ""}`.trim() || me.email : "…";

  // Vérification du profil praticien en cours
  if (hasPractitioner === null) {
    return <LoadingState label="Chargement de votre espace…" />;
  }

  // Aucun profil praticien : afficher l'onboarding avant tout le reste
  if (hasPractitioner === false) {
    const handleOnboardingDone = async () => {
      checkPractitioner();
      if (pendingPlan) {
        try {
          const data = await apiFetch("/api/billing/checkout/", {
            method: "POST",
            body: JSON.stringify({ plan: pendingPlan }),
          });
          setPendingPlan(null);
          if (data && data.checkout_url) {
            window.location.href = data.checkout_url;
          }
        } catch (err) {
          // Si le checkout echoue, on laisse simplement le praticien
          // choisir un plan manuellement depuis Parametres.
          setPendingPlan(null);
        }
      }
    };
    return (
      <OnboardingScreen
        apiFetch={apiFetch}
        userLabel={userLabel}
        onDone={handleOnboardingDone}
      />
    );
  }

  const filterSuffix = (practitionerFilter && practitionerFilter !== "all") ? `&practitioner=${practitionerFilter}` : "";

  const views = {
    dashboard: <DashboardView apiFetch={apiFetch} userLabel={userLabel} filterSuffix={filterSuffix} plan={me?.plan} practitionerFilter={practitionerFilter} />,
    agenda:    <AgendaView apiFetch={apiFetch} filterSuffix={filterSuffix} />,
    patients:  <PatientsView apiFetch={apiFetch} practitionerFilter={practitionerFilter} plan={me?.plan} role={me?.role} />,
    waitlist:  <WaitlistView apiFetch={apiFetch} practitionerFilter={practitionerFilter} />,
    settings:  <SettingsView apiFetch={apiFetch} plan={me?.plan} isSubscriptionActive={me?.is_subscription_active} practitionerFilter={practitionerFilter} role={me?.role} ownerName={me?.owner_name} otpEnabled={me?.otp_enabled} onMeUpdated={loadMe} calendarReturn={calendarReturn} onCalendarReturnHandled={() => setCalendarReturn(null)} />,
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: T.cream, fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <Sidebar
        active={nav} onNav={setNav} onLogout={logout} userLabel={userLabel}
        allPractitioners={allPractitioners}
        practitionerFilter={practitionerFilter}
        onPractitionerChange={setPractitionerFilter}
      />
      <main style={{ flex: 1, padding: "2rem 2.5rem", overflow: "auto" }}>
        {views[nav]}
      </main>
    </div>
  );
}
