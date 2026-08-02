# 📡 CabinBook — Routes API

## Auth
| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/token/` | Login → access + refresh token |
| POST | `/api/auth/token/refresh/` | Rafraîchir le token |

## Compte
| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/api/accounts/register/` | Inscription |
| GET/PATCH | `/api/accounts/me/` | Profil utilisateur |

## Praticiens
| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/api/accounts/practitioners/` | Liste praticiens |
| POST | `/api/accounts/practitioners/` | Créer praticien |
| GET/PUT/PATCH | `/api/accounts/practitioners/{id}/` | Détail/modifier |
| POST | `/api/accounts/practitioners/{id}/deactivate/` | Désactiver |

## Patients
| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/api/accounts/patients/` | Liste patients |
| POST | `/api/accounts/patients/` | Créer patient |
| GET/PUT/PATCH/DELETE | `/api/accounts/patients/{id}/` | Détail/modifier |
| GET | `/api/accounts/patients/?practitioner=1` | Filtrer par praticien |

## Rendez-vous
| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/api/appointments/` | Liste RDV (filtrables) |
| POST | `/api/appointments/` | Créer RDV |
| GET/PUT/PATCH | `/api/appointments/{id}/` | Détail/modifier |
| POST | `/api/appointments/{id}/confirm/` | Confirmer |
| POST | `/api/appointments/{id}/cancel/` | Annuler |
| POST | `/api/appointments/{id}/no_show/` | Marquer absent |
| POST | `/api/appointments/{id}/complete/` | Terminer |
| GET | `/api/appointments/today/` | RDV du jour |
| GET | `/api/appointments/stats/` | Stats dashboard |

### Filtres disponibles sur /api/appointments/
- `?practitioner=1` — par praticien
- `?status=confirmed` — par statut
- `?date_from=2026-07-01&date_to=2026-07-31` — par plage de dates
- `?search=martin` — recherche patient

## Créneaux
| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/api/appointments/timeslots/` | Liste créneaux |
| POST | `/api/appointments/timeslots/` | Créer créneau |
| GET/PUT/PATCH/DELETE | `/api/appointments/timeslots/{id}/` | Détail/modifier |
| GET | `/api/appointments/timeslots/?is_available=true` | Créneaux libres |

## Facturation
| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/api/billing/checkout/` | Créer session Stripe |
| POST | `/api/billing/webhook/` | Webhook Stripe (public) |

## Page publique (réservation patient)
| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/book/{slug}/` | Page de résa du praticien |
| POST | `/book/{slug}/book/` | Prendre un RDV (sans auth) |
| GET | `/book/confirm/{token}/` | Confirmer présence |
| GET | `/book/cancel/{token}/` | Annuler via lien email |
