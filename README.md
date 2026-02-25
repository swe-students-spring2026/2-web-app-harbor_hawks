# Web Application Exercise

A little exercise to build a web application following an agile development process. See the [instructions](instructions.md) for more detail.

## Product vision statement

To create a structured, academic digital space where students can ask questions, create posts, and collaborate within their major and specific classes to make learning more efficient, contextual, and community-driven.

## User stories

[Issues Page](https://github.com/swe-students-spring2026/2-web-app-harbor_hawks/issues)

## Steps necessary to run the software
#### (run all commands from the repo root)

### Database setup (MongoDB)

1. Install MongoDB Community Edition and `mongosh` on your machine.
2. Start the MongoDB server.
   macOS (Homebrew): `brew services start mongodb-community`
   Linux (systemd): `sudo systemctl start mongod`
   Windows: start the `MongoDB Server` service in Services.

### Backend (in a separate terminal window):
1. Install Pipenv (one-time): `python3 -m pip install --user pipenv`
2. Install dependencies: `pipenv install`
3. Create and fill in your local env file: `cp env.example .env` (then edit `.env` with the correct values)
4. Ensure MongoDB is running locally (matching `MONGO_URI` in `.env`)
5. Run the Flask API: `pipenv run python -m backend.flask.app`

### Frontend (in a separate terminal window):
1. In your browser, open: http://127.0.0.1:5000/


## Task boards

[Sprint 1](https://github.com/orgs/swe-students-spring2026/projects/38/views/1?filterQuery=)
[Sprint 2](https://github.com/orgs/swe-students-spring2026/projects/45/views/1?filterQuery=)
