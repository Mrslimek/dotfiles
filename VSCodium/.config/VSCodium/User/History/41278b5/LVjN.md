# Entity service

## 1. Release info

#### Migrated from Flask framework to FastAPI
- Performance Improvement: Observed significant enhancements in asynchronous request handling and overall application performance; max asynchronous requests has been increased.
- Native support of websocketes.

#### Migrated from synchronous DB access to async DB access (asyncpg pool manager)
- Refactoring: Moved DB access patterns to async/await style and standardized pool usage via `AsyncpgConnectionManager` (from the ecosystem auth submodule).
- Operational impact: Centralized pool initialization/shutdown and safer connection acquisition patterns for high-frequency async workloads (including WebSockets).

#### Ypy dynamic documents support
- Functionality: Enables real-time collaborative document editing and synchronization across multiple users

#### Framework-side request data validation 
- Validation Mechanism: Implemented data validation directly at the framework level using Pydantic in FastAPI.
- Benefits: Provides robust security against invalid data inputs by enforcing data schemas

## 2. Features

- Real-time collaborative document support
- Native websockets support 

## 3. Requirements

- [Python](https://www.python.org)>=3.9
- [Python requirements list](requirements.txt)
- (For collaborative documents) [Ypy](requirements/y_py-0.6.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl)
- [PostgreSQL](https://www.postgresql.org)>=9.6
- [PostgreSQL uuid-ossp](https://www.postgresql.org/docs/9.6/uuid-ossp.html)
- [PostgreSQL ltree](https://www.postgresql.org/docs/9.6/ltree.html)
- [PostgreSQL pg_trgm](https://www.postgresql.org/docs/9.6/pgtrgm.html)

## 4. License

*In progress*

## 5. Acceptance tests

Acceptance tests for entity service located in the [WMS54 repository](https://git.54origins.com/ecosystem54/frontapps/07_pm_service)

## 6. Documentation

- [Flows](docs_and_tests/flows.md)
- [API calls](docs_and_tests/API%20specification.html)

## 7. Deployment instructions

- Base infrastructure [overview](deploy/README.md)
- Local deployment without docker [guide](deploy/deploy_local_manual.md)
- Local deployment with docker [guide](deploy/deploy_local_docker.md)
- Enterprise deployment(k8s) [guide](deploy/deploy_enterprise_k8s.md)


- [Collaborative documents server deployment](deploy/ypy_server_deployment.md)
- [Server deployment guide](deploy/server_deployment.md)
- [Server update guide](deploy/server_update.md)

## WebSocket testing note (read this if you touch WS)

WebSocket endpoints must be validated with **load tests**, not only functional checks.

Reason: a WS handler can accidentally introduce hidden IO coupling (DB/Redis/etc.). A common failure mode is **one WebSocket client consuming one DB connection from the pool**, which exhausts the pool quickly (e.g., ~10 clients) and can effectively take down the server. This can look like “works locally” but fails under concurrent WS connections.

When you change anything in WebSockets (engine/services/dependencies/listeners), make sure you run load tests that verify:
- **DB pool usage** under N concurrent WS clients (no per-client DB connection leaks / no long-held pool connections)
- **message delivery latency** under sustained publish rate

See `tests/locust_test/` for load testing scenarios.
- [Collaborative documents server deployment](deploy/ypy_server_deployment.md)

## 8. Other software config samples

- [Locust test](tests/locust_test/locust_test.md)
- [Ypy test](tests/ypy_test/ypy_test.md)
- [Local settings](deploy/config_samples/local_settings.py)
- [Nginx config](deploy/config_samples/entity.conf)
- [Uvicorn daemon](deploy/config_samples/entity.service)
- [Ypy daemon](deploy/config_samples/ypy.service)

## 9. Dependencies

- Git submodules: [Auth Submodule](https://git.54origins.com/ecosystem54_protected/agpl/01_submodules_authsubmodule54.git)

## 10. Git-policy

- [Git-policy](gitpolicy.md)
