# CabinBook 🏥

> Logiciel de gestion de rendez-vous avec rappels automatiques pour kinés, ostéos et psychologues libéraux.

---

## 🚀 Lancer en local (5 minutes)

### Prérequis
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et démarré
- Git

### 1. Cloner et configurer

```bash
git clone https://github.com/TON_USER/cabinbook.git
cd cabinbook

# Copier le fichier d'environnement local
cp .env.local .env.local
```

> **Note :** Pour un démarrage rapide, les clés Stripe/Twilio/SendGrid peuvent rester en `REMPLACER` — le projet démarre quand même, seuls les emails/SMS/paiements ne fonctionneront pas.

### 2. Lancer Docker

```bash
docker compose -f docker-compose.dev.yml up --build
```

La première fois, Docker télécharge les images (~2 min). Les fois suivantes c'est instantané.

### 3. Initialiser la base de données

Dans un **nouveau terminal** :

```bash
# Migrations
docker compose -f docker-compose.dev.yml exec web python manage.py migrate

# Créer un compte admin
docker compose -f docker-compose.dev.yml exec web python manage.py createsuperuser
```

### 4. C'est prêt ! 🎉

| URL | Description |
|-----|-------------|
| http://localhost:8000/admin/ | Interface admin Django |
| http://localhost:8000/api/ | API REST (DRF browsable) |
| http://localhost:8000/book/jean-dupont/ | Page de réservation publique (après avoir créé un praticien) |
| http://localhost:8000/api/auth/token/ | Obtenir un JWT |

---

## 📡 Tester l'API

### Obtenir un token JWT

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "ton@email.com", "password": "tonmotdepasse"}'
```

### Créer un praticien

```bash
curl -X POST http://localhost:8000/api/accounts/practitioners/ \
  -H "Authorization: Bearer TON_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jean",
    "last_name": "Dupont",
    "specialty": "kine",
    "booking_page_slug": "jean-dupont"
  }'
```

### Créer un créneau

```bash
curl -X POST http://localhost:8000/api/appointments/timeslots/ \
  -H "Authorization: Bearer TON_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "practitioner": 1,
    "start_time": "2026-07-15T09:00:00+02:00",
    "end_time": "2026-07-15T09:45:00+02:00"
  }'
```

### Voir la page de réservation publique

```
http://localhost:8000/book/jean-dupont/
```

---

## 🗂 Structure du projet

```
cabinbook/
├── apps/
│   ├── accounts/          → User, Practitioner, Patient
│   ├── appointments/      → Appointment, TimeSlot + page publique
│   ├── billing/           → Stripe checkout + webhook
│   └── notifications/     → Email (SendGrid) + SMS (Twilio)
├── cabinbook/
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── tests/
├── docker-compose.dev.yml  ← DEV local
├── docker-compose.yml      ← PROD (VPS)
├── Dockerfile
├── .env.local              ← Variables locales (ne pas committer)
└── manage.py
```

---

## ⚙️ Commandes utiles

```bash
# Voir les logs
docker compose -f docker-compose.dev.yml logs -f web

# Lancer les tests
docker compose -f docker-compose.dev.yml exec web pytest

# Ouvrir un shell Django
docker compose -f docker-compose.dev.yml exec web python manage.py shell

# Nouvelle migration après modif de models
docker compose -f docker-compose.dev.yml exec web python manage.py makemigrations
docker compose -f docker-compose.dev.yml exec web python manage.py migrate

# Arrêter tout
docker compose -f docker-compose.dev.yml down

# Arrêter et supprimer les données
docker compose -f docker-compose.dev.yml down -v
```

---

## 🔑 Services tiers (optionnels en local)

| Service | Usage | Plan gratuit |
|---------|-------|-------------|
| [Stripe](https://dashboard.stripe.com) | Paiements | Oui (mode test) |
| [Twilio](https://twilio.com) | SMS rappels | Oui (15€ crédit) |
| [SendGrid](https://sendgrid.com) | Emails | Oui (100/jour) |

Pour les tester en local, remplace les valeurs `REMPLACER` dans `.env.local`.

---

## 📋 Routes API complètes

Voir `API_ROUTES.md`

---

## 🏗 Stack technique

- **Backend** : Django 5.1 + DRF + JWT
- **Base de données** : PostgreSQL 16
- **Cache / Queue** : Redis + Celery
- **Paiements** : Stripe
- **Email** : SendGrid
- **SMS** : Twilio
- **Infra** : Docker Compose + Nginx
- **CI/CD** : GitHub Actions
