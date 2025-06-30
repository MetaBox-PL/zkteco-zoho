# ZKTeco ↔ Zoho People Integration

This project integrates attendance data from a ZKTeco biometric device with Zoho People using Python.

## 🚀 Features

- Syncs employee data from Zoho People into a local MySQL database.
- Matches biometric device users with Zoho employees.
- Sends real-time check-in/check-out logs to Zoho.
- Hybrid mode: real-time + periodic syncing.
- Docker-ready for deployment via Portainer.

## 📁 Project Structure

| Folder/File      | Purpose |
|------------------|---------|
| `src/`           | All Python source code (`final.py`, `sync_db.py`, etc.) |
| `data/`          | All generated state or cache JSON files |
| `tests/`         | Scripts used for testing |
| `e.env`          | Your environment variables (OAuth, DB, IP) — **do not commit** |
| `Dockerfile.*`   | Docker images for syncing and attendance |

## 🔧 Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/MetaBox-PL/zkteco-zoho.git
cd zkteco-zoho
