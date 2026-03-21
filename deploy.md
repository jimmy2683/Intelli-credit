# Deployment Guide: Credit Intel AI

This guide explains how to deploy the **Credit Intel** platform on **Render** and how to manage shared storage for PDF documents in a cloud environment.

---

## 🏗️ 1. Architecture for Cloud (Render)

In a local environment, the services share a common `data/` folder. On Render, services are isolated. To make them work together, we need to shift from local disk to **Object Storage**.

### Recommended Stack:
- **Frontend**: Vercel Static Site (Next.js)
- **Backend-Go**: Render Web Service
- **AI-Engine**: Render Web Service (Python)
- **Database**: Render PostgreSQL (or Supabase)
- **Shared Storage**: Cloudflare R2 or AWS S3 (Critical for shared PDFs)

---

## 📦 2. Shared Storage Strategy (The "Filesystem" Problem)

Since both `backend-go` and `ai-engine` need to read the same PDF files, you should use an **S3-Compatible Bucket**.

### Why?
Render disks cannot be shared between different services. S3 allows:
1.  **Backend-Go**: Uploads the user's PDF to the bucket.
2.  **AI-Engine**: Downloads the PDF using the same bucket credentials to process it.

### Implementation steps:
1.  Create a bucket on **Cloudflare R2** (Zero egress fees, very fast).
2.  Update `backend-go` to use an S3 client for uploads.
3.  Update `ai-engine` to download from S3 before processing.

---

## 🚀 3. Deploying to Render

### A. AI Engine (Python)
1.  **New -> Web Service**.
2.  Connect your repository and set the root directory to `ai-engine`.
3.  **Runtime**: Python 3.
4.  **Build Command**: `pip install -r requirements.txt`.
5.  **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6.  **Environment Variables**:
    - `MISTRAL_API_KEY`: your-key
    - `AWS_ACCESS_KEY_ID`: your-access-key
    - `AWS_SECRET_ACCESS_KEY`: your-secret-key
    - `AWS_REGION`: your-region (e.g., us-east-1)
    - `AWS_S3_BUCKET`: your-bucket-name
    - `DATA_ROOT`: `/tmp/data` (fallback for local files)

### B. Backend (Go)
1.  **New -> Web Service**.
2.  Set root directory to `backend-go`.
3.  **Runtime**: Go.
4.  **Build Command**: `go build -o app ./cmd/server`.
5.  **Start Command**: `./app`.
6.  **Environment Variables**:
    - `PORT`: `8080`
    - `DATABASE_URL`: (from your Render Postgres)
    - `AI_ENGINE_BASE_URL`: (the URL provided by Render for the AI Engine service)
    - `BACKEND_HTTP_TIMEOUT_SEC`: `180`
    - `AWS_ACCESS_KEY_ID`: your-access-key
    - `AWS_SECRET_ACCESS_KEY`: your-secret-key
    - `AWS_REGION`: your-region
    - `AWS_S3_BUCKET`: your-bucket-name

### C. Frontend (Vercel) — ✅ Already Hosted
1.  **Vercel Dashboard**: Go to Project Settings -> Environment Variables.
2.  Add `NEXT_PUBLIC_API_URL`: (the URL of your **Backend-Go** on Render).
3.  **Redeploy**: Ensure the frontend is built with the new API URL.

### ⚠️ IMPORTANT: CORS Settings
To allow the Vercel frontend to talk to the Render Go-Backend, you **must** update the Go backend's allowed origins:
1.  Set `CORS_ALLOWED_ORIGINS` environment variable on **Render** to your Vercel URL (e.g., `https://credit-intel.vercel.app`).
2.  Alternatively, use `*` for initial testing (already configured in `config.go` as a fallback).

---

## 🧪 4. Handling the Database

1.  Create a **PostgreSQL** instance on Render.
2.  Copy the External Database URL.
3.  Add it as `DATABASE_URL` to your **Backend-Go** environment variables.
4.  The Go backend will automatically handle the connection if configured with a driver like `pgx` or `gorm`.

---

## 📝 5. One-Command Setup (Local Docker)

For the hackathon demo, you can also use `docker-compose.yml` to run everything locally. Render also supports deploying via `docker-compose` if you use their "Blueprints" (render.yaml), but individual web services are simpler for a start.
