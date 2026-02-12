# CheckTick

![GitHub License](https://img.shields.io/github/license/eatyourpeas/checktick?style=for-the-badge&color=5fcfdd)
![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-5fcfdd?style=for-the-badge&logo=openapiinitiative&logoColor=white)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/eatyourpeas/checktick?style=for-the-badge&color=5fcfdd)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-5fcfdd?style=for-the-badge&logo=docker&logoColor=white)](https://github.com/eatyourpeas/checktick/pkgs/container/checktick)

CheckTick is an open source survey platform for medical audit and research. It supports OIDC (Google and Microsoft 365) and data is secure with encrypted identifiers only visible to users entering the data. Although built for the UK, it is fully i18n compliant and supports a range of languages. Survey creators build questions from a library of question types, or they can import them written in markdown. There is a growing library of lists to populate dropdowns for which contributions are welcome. There is also an API which supports user, survey and question management.

Try it out [here](https://checktick.uk)
>[!NOTE]
>This is in a sandbox dev environment and is for demo purposes only. Do not store patient or sensitive information here.

## 🐳 Self-Hosting

CheckTick can be self-hosted using Docker. Pre-built multi-architecture images are available on GitHub Container Registry.

### Quick Start

```bash
# Download docker-compose file
wget https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.registry.yml

# Configure environment
cp .env.selfhost .env
# Edit .env with your settings

# Start CheckTick
docker compose -f docker-compose.registry.yml up -d
```

**📦 Docker Images:** [ghcr.io/eatyourpeas/checktick](https://github.com/eatyourpeas/checktick/pkgs/container/checktick)

**📚 Full Documentation:** See [Self-Hosting Guides](https://checktick.eatyourpeas.dev/docs/self-hosting-quickstart/)

## Documentation

Documentation can be found [here](https://checktick.eatyourpeas.dev/docs/)

## Getting Help & Contributing

### 💬 Community & Support

- **[Discussions](https://github.com/eatyourpeas/checktick/discussions)** - For questions, ideas, and community support
- **[Issues](https://github.com/eatyourpeas/checktick/issues)** - For bug reports and specific feature requests
- **[Documentation](https://checktick.eatyourpeas.dev/docs/)** - Complete guides and API documentation

### When to use what?

**Use Discussions for:**

- General questions about using CheckTick
- Seeking advice on healthcare survey design
- Sharing your CheckTick use cases
- Community announcements and updates
- Brainstorming new ideas before formal feature requests
- Getting help with deployment or configuration
- Asking "How do I...?" questions

**Use Issues for:**

- Reporting bugs or unexpected behavior
- Requesting specific features with detailed requirements
- Documentation corrections or improvements
- Security concerns (non-sensitive)

### Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on contributing code, documentation, and reporting issues.

## Issues

Please raise [issues](https://github.com/eatyourpeas/checktick/issues) for bugs and specific feature requests. For general questions and community support, use [Discussions](https://github.com/eatyourpeas/checktick/discussions).

## Technologies

CheckTick is open source and customisable - admin users can change styles and icons.

The project is built on Django with Postgres 16, DaisyUI. It is dockerized and easy to deploy. It is a security-first project and follows OWASP principles. Sensitive data is encrypted.

## Quickstart

Local with Docker (recommended):

1. Copy environment file and edit as needed

   ```bash
   cp .env.example .env
   ```

2. Build and start services - a convenience `s` folder of bash scripts supports build of the containers. The dev set up includes the creation of a Hashicorp Vault and volume. To set this up there are two scripts:

   ```bash
   s/dev --init-vault
   ```

   and then:

   ```bash
   s/dev
   ```

   The initialisation step will print the keys to the console and an explainer with easy to follow steps for local dev.

3. Open <https://localhost:8000>

Without Docker (Python + Node):

- Install Poetry and Node 18+
- poetry install
- npm install && npm run build:css
- python manage.py migrate
- python manage.py createsuperuser
- python manage.py runserver

Container deployments:

- Run `python manage.py collectstatic --noinput` once the environment variables (including `DATABASE_URL`) are available.
- Start the app with `python manage.py migrate --noinput && gunicorn checktick_app.wsgi:application --bind 0.0.0.0:${PORT:-8000}`.

API endpoints:

- GET /api/health
- POST /api/token (JWT obtain)
- POST /api/token/refresh (JWT refresh)
- /api/surveys/ (CRUD for authenticated owners)
- /api/users/ (admin read-only)

API permissions mirror SSR rules: you can list and retrieve surveys you own, and any survey in organisations where you are an ADMIN. Updates/deletes require ownership or org ADMIN.
See docs/api.md for endpoint-level protections and error semantics.

Security posture:

- Server-side rendering, CSRF protection, session cookies (HttpOnly, Secure)
- Strict password validators, lockout on brute force (django-axes)
- Rate limiting on form posts (django-ratelimit)
- CSP headers (django-csp) and static via WhiteNoise
- Sensitive demographics encrypted per-survey using AES-GCM with derived keys
- API uses JWT (Bearer) auth; include Authorization header in requests
- Per-survey encryption keys with zero-knowledge architecture
- See [Patient Data Encryption](docs/patient-data-encryption.md) for detailed security documentation

## Tests

There are tests for all the endpoints, and in particular for all the functions relating to user and organisation management and permissions. There are also tests for survey creation and update, and relating to hashing and decryption of key identifiers.
