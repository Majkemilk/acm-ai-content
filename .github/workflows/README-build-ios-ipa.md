# Workflow: Build iOS .ipa

Workflow **Build iOS .ipa** buduje aplikację Expo/React Native dla iOS na runnerze `macos-latest` i udostępnia plik `.ipa` jako artifact do pobrania.

## Uruchomienie

1. W repozytorium: **Actions** → **Build iOS .ipa** → **Run workflow** → **Run workflow**.
2. Po zakończeniu: w uruchomieniu workflow → **Summary** → sekcja **Artifacts** → pobierz **app-ios-ipa**.

## Wymagania

- Projekt musi być aplikacją Expo/React Native z poprawnym `app.json` / `app.config.js` i `eas.json` (np. `eas build:configure`).
- W **Settings** → **Secrets and variables** → **Actions** dodaj secret:
  - **`EXPO_TOKEN`** — token z [Expo Dashboard](https://expo.dev/accounts/[account]/settings/access-tokens) (Create token). Używany do uwierzytelnienia EAS i (opcjonalnie) do pobrania credentials z EAS (np. tymczasowe certyfikaty developerskie).

## Certyfikaty i instalacja bez Apple Developer (płatnego)

- EAS przy buildzie lokalnym może użyć **development signing** z darmowym kontem Apple (certyfikaty ~7 dni). Wymaga to wcześniejszego powiązania projektu z EAS (`eas credentials`) lub skonfigurowania w `eas.json` profilu z typem development.
- Aby .ipa nadawał się do instalacji przez **AltStore** / **LiveContainer**: build musi być podpisany (development lub ad-hoc). Z darmowym kontem Apple zwykle otrzymujesz development provisioning; urządzenie musi być zarejestrowane w Apple Developer (Free). Po pobraniu artifactu możesz zainstalować .ipa przez AltStore/LiveContainer, o ile profil jest kompatybilny.

## Opcjonalne zmienne / secrety

- **`APPLE_ID`**, **`APPLE_APP_SPECIFIC_PASSWORD`** — jeśli używasz własnych credentials Apple w EAS (np. distribution), możesz je ustawić w secretach i dodać do `env` w kroku „Build iOS .ipa (local)” w workflow.
- W `eas.json` możesz zdefiniować profil (np. `development`) z `distribution: "internal"` lub odpowiednim typem dla AltStore.

## Uwagi

- Runner: **macos-latest** (darmowy dla public repos; dla private zależnie od planu).
- Artifact jest przechowywany **30 dni** (można zmienić `retention-days` w workflow).
- Przy pierwszym uruchomieniu EAS może poprosić o konfigurację projektu (`eas.json`); upewnij się, że projekt ma skonfigurowany EAS przed uruchomieniem workflow.
