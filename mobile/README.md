# CryptoTrader — Mobile & Web App (Expo)

A single Expo / React Native codebase that runs on **iOS, Android, and the web**
(`react-native-web`). It talks to the FastAPI backend in [`../backend`](../backend).

## Prerequisites

- Node.js 18+
- The backend running (see `../backend/README.md`) — default `http://localhost:8000`

## Setup

```bash
cd mobile
npm install
cp .env.example .env      # set EXPO_PUBLIC_API_URL if the backend isn't on localhost
```

## Run

```bash
npm run web       # open in a browser
npm run ios       # iOS simulator (macOS)
npm run android   # Android emulator
npm start         # Expo dev server + QR code for Expo Go on a physical device
```

> On a physical device, set `EXPO_PUBLIC_API_URL` to your computer's LAN IP
> (e.g. `http://192.168.1.20:8000`) so the phone can reach the backend.

## Structure

```
app/                     # Expo Router (file-based routing)
  _layout.tsx            # root layout + auth gate
  login.tsx              # login / register
  (tabs)/
    index.tsx            # dashboard (portfolio summary)
    agents.tsx           # agent list
    accounts.tsx         # linked exchange accounts
  agent/
    new.tsx              # create-agent form
    [id].tsx             # agent detail: position, controls, signals, trades
src/
  api.ts                 # typed REST client
  auth.tsx               # auth context (JWT persisted via AsyncStorage)
  components.tsx         # shared UI primitives
  theme.ts               # colors / spacing tokens
```

## Notes

- Auth token is stored with `AsyncStorage` and sent as a Bearer token.
- Exchange API secrets are entered here but only ever stored **encrypted on the
  backend**; the API never returns them.
- Start with **paper** agents (no API keys required). Live mode requires a linked,
  keyed account for a live-capable exchange.
