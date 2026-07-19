# Firefly III Assistant

A budgeting-first companion app for Firefly III. The first module is a fast monthly budget cockpit with a dashboard, sticky spreadsheet-style budget grid, inline editing, keyboard navigation, quick adjustments, and copy actions.

## Firefly III connection

The app runs with demo data when Firefly credentials are not configured. To connect it to Firefly III, copy `.env.example` to `.env.local` and set:

```bash
FIREFLY_BASE_URL=https://firefly.example.com
FIREFLY_ACCESS_TOKEN=your-personal-access-token
```

Budget data is loaded through the server route at `/api/budgets/overview`. Planned budget edits are saved through `/api/budgets/limits`, which writes budget limits back to Firefly III.

## Local analysis with Ollama

The budget cockpit can send aggregated monthly budget totals to a local Ollama model. Raw Firefly credentials are never sent to Ollama, and model output is treated as a draft that must be reviewed before an existing budget amount is changed. New category ideas are displayed but are not created automatically.

Install Ollama, pull the default model, and make sure the Ollama service is running:

```bash
ollama pull gemma3:4b
ollama serve
```

The defaults work when Next.js runs directly on the host:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT_MS=120000
```

Open the **Local economy analyst** panel to run a full review, request budget drafts, or focus on savings ideas. The server uses Ollama structured outputs and validates the response before returning it to the browser.

## Docker

Run the app as a single container with Docker Compose:

```bash
docker compose up --build
```

Set the Firefly III connection in `docker-compose.yml`:

```yaml
environment:
  FIREFLY_BASE_URL: "${FIREFLY_BASE_URL:-}"
  FIREFLY_ACCESS_TOKEN: "${FIREFLY_ACCESS_TOKEN:-}"
```

You can either export those values before starting Compose or replace the values directly in `docker-compose.yml`. When both are empty, the container starts with demo data.

The app is exposed on `http://localhost:3000`.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
