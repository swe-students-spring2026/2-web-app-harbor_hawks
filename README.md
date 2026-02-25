# Web Application Exercise

A little exercise to build a web application following an agile development process. See the [instructions](instructions.md) for more detail.

## Product vision statement

To create a structured, academic digital space where students can ask questions, create posts, and collaborate within their major and specific classes to make learning more efficient, contextual, and community-driven.

## User stories

[Issues Page](https://github.com/swe-students-spring2026/2-web-app-harbor_hawks/issues)

## Steps necessary to run the software
#### (run all commands from the repo root)

Backend:
- Install Pipenv (one-time): `python3 -m pip install --user pipenv`
- Install dependencies: `pipenv install`
- Create and fill in your local env file: `cp env.example .env` (then edit `.env` with the correct values)
- Ensure MongoDB is running locally (matching `MONGO_URI` in `.env`)
- Run the Flask API: `pipenv run python -m backend.flask.app`

Frontend (in a separate terminal windwow):
- In your browser, open: http://127.0.0.1:5000/

## Task boards

[Sprint 1](https://github.com/orgs/swe-students-spring2026/projects/38/views/1?filterQuery=)
[Sprint 2](https://github.com/orgs/swe-students-spring2026/projects/45/views/1?filterQuery=)
