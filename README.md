# 🌾 AI KrushiMitra - Smart Farming Companion

AI-powered agricultural platform helping farmers make smarter decisions with intelligent crop guidance, disease detection, weather insights, market information and government scheme recommendations.

---

## ✨ Features

- **Multilingual Support** - English, Marathi (मराठी), Hindi (हिंदी), Malayalam (മലയാളം)
- **Farmer Registration & Profile Management**
- **Real-time Weather + 7-Day Forecast** via Open-Meteo API
- **Crop-Specific Weather Advisory** - dynamic advice based on crop + stage + weather
- **Crop Disease Detection** - Gemini image analysis with the bundled MobileNetV2 classifier used only as an advisory hint
- **AI Farming Assistant** - chatbot with personalized agricultural guidance
- **Smart Market Module** - current APMC mandi prices for farmer's crop
- **Farmer–Buyer Marketplace** - MongoDB-backed produce listings, buyer profiles and requirements, farmer offers, accepted orders, and protected participant contact details
- **Premium Glassmorphism UI** - dark agriculture theme, purple/blue gradients, green accents

---

## 🏗️ Project Structure

```
AI-KrushiMitra/
├── frontend/                 # React + Vite Frontend
│   ├── src/
│   │   ├── components/       # Reusable UI (GlassCard, Navbar, Buttons, Forms)
│   │   ├── pages/            # Welcome, onboarding, and farmer dashboard modules
│   │   ├── context/          # LanguageContext + AuthContext
│   │   ├── translations/     # en.js, mr.js, hi.js, ml.js — full i18n dictionaries
│   │   ├── services/api.js   # Axios services (auth/farmer/weather/assistant/market)
│   │   ├── App.jsx           # Routing + Protected routes
│   │   ├── main.jsx          # React entry
│   │   └── index.css         # Global glassmorphism theme (1100+ lines)
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
└── backend/                  # FastAPI + MongoDB Backend
    ├── main.py               # FastAPI app
    ├── database.py           # Async Motor MongoDB client and collection indexes
    ├── auth_utils.py         # JWT + bcrypt utilities
    ├── models/farmer.py      # Farmer profile and authentication schemas
    ├── models/marketplace.py # Buyer profile, requirements, offers, and produce validation
    ├── routes/               # REST endpoints
    │   ├── auth.py           # register/login/me
    │   ├── farmer.py         # profile CRUD
    │   ├── weather.py        # Open-Meteo + crop advisory
    │   ├── assistant.py      # Gemini chat and streaming endpoints
    │   ├── market.py         # APMC market prices
    │   └── buyer_marketplace.py # Buyer profiles, produce, requirements, offers, and orders
    ├── services/             # Business logic
    │   ├── weather_service.py
    │   ├── ai_service.py
    │   └── market_service.py
    ├── requirements.txt
    └── .env.example
```

---

## 🚀 Quick Start

### Prerequisites
- **Node.js 18+** (for frontend)
- **Python 3.10+** (for backend)
- **MongoDB** (local or Atlas - required for full functionality)

---

### 1️⃣ Run the Frontend

```bash
cd AI-KrushiMitra/frontend
npm install
npm run dev
```

🌐 Open: **http://localhost:5173**

### 2️⃣ Run the Backend

```bash
cd AI-KrushiMitra/backend

# 1. Create environment file
cp .env.example .env
# (Edit .env with your MongoDB URI, secret key, etc.)

# 2. On first setup, create the backend virtual environment; install dependencies
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Start the backend using that same interpreter (Windows)
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

📚 API Docs (Swagger UI): **http://localhost:8000/docs**

Crop disease detection and the AI Farmer Assistant share the backend `GEMINI_API_KEY` and `GEMINI_MODEL` configuration. The shared image-capable model is used for disease-image analysis and text chat. The bundled MobileNetV2 model can provide a local reference result where supported; Gemini is used for image analysis when the local model cannot provide a supported result. If Gemini is unavailable or cannot support a diagnosis, the endpoint returns a safe error or uncertainty result rather than presenting an unconfirmed prediction. Assistant chat uses Gemini only; provider failures remain explicit errors and are not converted into fallback chat answers.

To check which Gemini models are available to the configured API key, run this from `backend`:

```powershell
.\.venv\Scripts\python.exe .\check_gemini_models.py
```

This uses Google's `models.list` API and reports model names only; it never prints the API key. Model listing does not prove access to the Interactions API or image-input support. Check Google's [image understanding documentation](https://ai.google.dev/gemini-api/docs/image-understanding), then verify access with an actual image request. The default is `gemini-3.8-flash`.

---

## 🔧 Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Example |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `DATABASE_NAME` | Database name | `ai_krushimitra` |
| `SECRET_KEY` | JWT signing secret | `change-me-to-a-long-random-string` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL (default: 7 days) | `10080` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `http://localhost:5173` |
| `GEMINI_API_KEY` | **Optional** - for crop disease image analysis, Gemini AI answers, and generated translations | configure in `backend/.env` |
| `GEMINI_MODEL` | Shared Gemini model for crop disease image analysis and assistant chat | `gemini-3.8-flash` |
| `OPENAI_API_KEY` | **Optional** - for auxiliary AI-backed generation/translation; not used for assistant chat | configure in `backend/.env` |
| `GOOGLE_CLIENT_ID` | Google Identity Services Web OAuth client ID; must match the frontend | `your-client-id.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Web client secret used by the backend authorization-code exchange | configure in `backend/.env` |
| `GOOGLE_REDIRECT_URI` | Frontend origin used by the OAuth authorization-code flow | `http://localhost:5173` |

> 💡 Configure a supported AI provider key for generated assistant answers and reliable translation of generated advisories. When the AI service is unavailable, the application shows a localized unavailable message rather than presenting fabricated advice.

### Frontend (`frontend/.env`)

| Variable | Description | Local development value |
|---|---|---|
| `VITE_GOOGLE_CLIENT_ID` | Same Google Identity Services Web OAuth client ID as the backend | `your-client-id.apps.googleusercontent.com` |
| `VITE_API_BASE_URL` | FastAPI origin, without the `/api` suffix | `http://127.0.0.1:8000` |

Google login uses the Google Identity Services popup authorization-code flow and sends the authorization code and frontend origin to `POST /api/auth/google`. The backend exchanges the code using `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`, then verifies the returned ID token. Existing password accounts are never auto-linked based only on email. Sign in with the existing account and connect Google from the farmer profile or Buyer Profile screen.

Google sign-in failures are logged by stage (configuration, origin validation, code exchange, or ID-token verification) with safe error categories only; credentials, authorization codes, and tokens are not logged. The API returns a safe diagnostic code and user-facing message to the frontend.

In Google Cloud Console, create a **Web application** OAuth client and authorize the frontend address under **Authorized JavaScript origins** and the configured `GOOGLE_REDIRECT_URI` under **Authorized redirect URIs**. The original local redirect URI is `http://localhost:5173`; configure the matching deployed values for production. Set the same client ID in `frontend/.env` (`VITE_GOOGLE_CLIENT_ID`) and `backend/.env` (`GOOGLE_CLIENT_ID`), set `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI` in `backend/.env`, and allow the frontend origin in backend `CORS_ORIGINS`. The client ID is public configuration; never put the OAuth client secret in frontend code. For production, set `VITE_API_BASE_URL` to the backend's HTTPS origin.

---

## 🧭 User Flow

```
Welcome Page
    ↓ Get Started
Language Selection (English / मराठी / हिंदी / മലയാളം)
    ↓ Select language (saved to localStorage)
Register / Login
    ├─ Buyer → Marketplace Buyer Profile → Marketplace Dashboard
    └─ Farmer → Create Farmer Profile
  ├─ Section A: Personal + Location (geolocation 📍 or manual)
  └─ Section B: Farming info (Crop / Stage / Soil / Irrigation / Land)
    ↓
Profile Created Successfully
    ↓
────────── Dashboard ──────────
├── AI Assistant 🤖
├── Weather + Crop Advisory 🌤️
├── Smart Market (APMC Prices) 🏪
├── My Profile (View / Edit ✏️)
└── Logout
```

---

## 🎨 Design System

**Theme:** Premium dark-agriculture SaaS dashboard

| Element | Style |
|---|---|
| Background | Deep navy gradient `#0a1628 → #0d1f3c` + agricultural grid pattern |
| Cards | Glassmorphism: `backdrop-blur`, `rgba(255,255,255,0.06)`, 20px radius, 1px light border |
| Buttons (Primary) | Purple→Blue gradient + subtle glow shadow |
| Accents | Agriculture green `#10b981` / `#22c55e` |
| Typography | Inter + Poppins from Google Fonts |
| Effects | Hover scale, fade/slide animations, pulse glows, floating elements |
| Responsive | Mobile-first, breakpoints at 480px / 768px / 1024px |

---

## 🔌 API Endpoints Summary

### Authentication (`/api/auth`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/register` | Create user account |
| POST | `/login` | Authenticate + return JWT |
| POST | `/google` | Verify a Google ID token and return the same JWT response |
| GET | `/me` | Current user profile |

Registration requires a backend-validated `role` value (`buyer` or `farmer`). Roles are stored on the MongoDB user record and returned by login and `/me`; changing profile or browser data cannot change the account role. Older accounts without a valid role are assigned on first authenticated use based on their existing marketplace profile, with farmer as the legacy default.

### Farmer (`/api/farmer`)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/profile` | Get farmer profile |
| POST | `/profile` | Create farmer profile |
| PUT | `/profile` | Update farmer profile |

### Weather (`/api/weather`)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/current?lat=&lon=` | Current + 24h hourly + 7-day forecast |
| GET | `/advisory?lat=&lon=&crop=&stage=` | Crop-specific weather advisory |

### AI Assistant (`/api/assistant`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat` | `{ message, context }` + `X-Language` header → AI response |

### Market (`/api/market`)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/prices?crop=&district=` | APMC mandi prices |

### Farmer–Buyer Marketplace (`/api/marketplace`)
| Method | Endpoint | Description |
|---|---|---|
| GET / PUT | `/profile` | View or create/update the signed-in buyer profile |
| GET | `/dashboard` | Database-backed buyer and farmer marketplace counts |
| GET / POST | `/produce` | Browse or publish farmer produce listings |
| GET | `/produce/mine` | List the signed-in farmer's produce |
| GET / POST | `/requirements` | Browse open requests or create a buyer requirement |
| PUT | `/requirements/{id}` | Edit an open requirement owned by the buyer |
| POST | `/requirements/{id}/cancel` | Cancel an open requirement owned by the buyer |
| POST | `/requirements/{id}/offers` | Submit a farmer offer |
| GET | `/requirements/{id}/offers` | View offers for the buyer's requirement |
| POST | `/requirements/{id}/offers/{offer_id}/{accept\|reject}` | Decide on an offer |
| GET | `/orders` | List orders where the signed-in user is a participant |
| GET | `/orders/{id}` | View participant-only order details and contact methods |
| POST | `/orders/{id}/status?next_status=in_progress\|completed` | Advance an authorized order through valid states |

---

## 📱 Pages Implemented

1. **Welcome** - Hero landing with Get Started CTA
2. **Language Selection** - 3 clickable language cards
3. **Register** - Signup form with validation
4. **Login** - Authentication form
5. **Create Farmer Profile** - 2-section form + geolocation
6. **Profile Created** - Success screen with farmer illustration
7. **Dashboard** - Farmer profile summary and agricultural modules
8. **My Profile** - View / Edit all farmer info
9. **Weather** - Current stats + 7-day forecast + crop advisory
10. **AI Assistant** - Chatbot UI with farmer context
11. **Smart Market** - APMC price table for farmer's crop
12. **Marketplace** - produce catalog, buyer profile and requirements, farmer offers, dashboards, orders, and protected contact details
Marketplace data uses separate `marketplace_v2_*` MongoDB collections and indexes so historical marketplace records are left untouched. Existing users and farmer profiles are preserved; no database or collection reset is performed.

---

## 🌍 Multilingual System

Language selection happens **only once** on the Language Selection page. The choice is stored in `localStorage` and every page uses it automatically.

Buyer accounts open the buyer dashboard after signing in. Farmers keep the existing farmer dashboard and profile, and can also browse buyer requirements and manage listings, offers, and orders from Marketplace. Frontend routes and backend buyer/farmer actions enforce the account role. The Messages / Chat navigation currently displays an explicit empty state because this project has no persisted messaging API.

Run backend role and marketplace tests from `backend` with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_buyer_marketplace.py
```

All translations live in:
- [frontend/src/translations/en.js](frontend/src/translations/en.js)
- [frontend/src/translations/mr.js](frontend/src/translations/mr.js)
- [frontend/src/translations/hi.js](frontend/src/translations/hi.js)

The backend AI Assistant reads the `X-Language` header (en/mr/hi) to match the response language.

---

## 🛠️ Technology Stack

### Frontend
- **React 18** + **Vite 5**
- **React Router 6** (protected route wrappers)
- **Axios** (API services with demo-data fallbacks)
- **date-fns** (date formatting)
- Hand-rolled CSS with glassmorphism + responsive grid

### Backend
- **FastAPI** (async, modern Python web framework)
- **Motor** (async MongoDB driver)
- **Pydantic v2** (data validation)
- **HTTPX** (async external API calls)
- **Passlib + bcrypt** — password hashing
- **python-jose** — JWT token authentication

### External Integrations
- **Open-Meteo** — free weather forecast API (no key required)
- **OpenAI API** (optional) — premium AI chatbot (falls back to rule-based)
- **Agmarknet / data.gov.in style API** — mandi prices with demo fallback
