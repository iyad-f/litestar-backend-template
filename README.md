# Litestar Backend Template
This is a backend template application built with [Litestar](https://litestar.dev/) to get your next backend running quickly.

Its folder structure and some other [Litestar](https://litestar.dev/) related best practices are inspired from the [litestar-fullstack](https://github.com/litestar-org/litestar-fullstack) repository.

It contains most of the boilerplate required for a production API like:

- **Latest Litestar** configured with best practices.  
- **Well-structured and scalable project layout** for maintainability and growth.  
- **Docker support** for containerized development:  
  - Multi-stage Docker build using a minimal Python 3.13 runtime image.  
- **Pure SQL integration** with migration management.  
- **Rate limiting** to protect against abuse and ensure fair usage.  
- **Authentication** implemented with access tokens and refresh tokens.  
- **Authorization** using Role-Based Access Control (RBAC).  

...and much more

Take what you need and adapt it to your own projects.

## Quick Start

Before starting, configure the application using the `config/app.toml` file. 

### Local Development

To run the development environment locally do the following:

1. Make sure you have a running **PostgreSQL** and **Redis** instance. 

2. Initialize the database and apply all migrations

```bash
uv run app database init
```

3. Create all the roles required by the application

```bash
uv run app role init
```

4. Start the application

```bash
uv run app run
```

### Docker

To run the entire development environment containerized do the following:

1. Initialize the database and apply all migrations.  
  **Note:** Migrations are automatically applied the first time the container is initialized. Use `docker compose run --rm app database init` only if you need to manually re-run migrations later. 

```bash
docker compose run --rm app database init
```

2. Create all the roles required by the application

```bash
docker compose run --rm app role init
```

3. Start the application

```bash
docker compose up -d
```

## Future Goals
- Write documentation for the project.
- Write further and more complete doc strings.
- Write tests.
