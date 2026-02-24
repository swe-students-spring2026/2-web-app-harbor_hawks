# Web Application Exercise

A little exercise to build a web application following an agile development process. See the [instructions](instructions.md) for more detail.

## Product vision statement

To create a structured, academic digital space where students can ask questions, create posts, and collaborate within their major and specific classes to make learning more efficient, contextual, and community-driven.

## User stories

### Christopher Cajamarca User Stories

1. As a student, I want to make an account so that I can access the application
2. As a student, I want to make a profile that contains my likes and interests so that I can connect with other students
3. As a studesnt, I want to follow others so that I can connect with other students with similar interests
4. As a student, I want to have others follow me so that I can have a community in which I can share my ideas with
5. As a student, I want to post threads so that I can communicate my thoughts with other students
6. As a student, I want to post pictures so that I can share meaningful moments in my life
7. As a student, I want to be able to comment on threads and pictures so that I can engage with the content from others
8. As a student, I want to message people on the application so that I can have conversations with people I may not have been able to in person
9. As a student, I want to be able to protect my account with a password so that my personal information isn't compromised
10. As a student, I want to like content posted by others so that I can show support
11. As a student, I want to be able to make group chats with multiple people so that we can have multiperson collaboration



## Steps necessary to run the software

Backend (run all commands from the repo root):
- Install dependencies: `python3 -m pip install -r requirements.txt`
- Create and fill in your local env file: `cp env.example .env` (then edit `.env` with the correct values)
- Ensure MongoDB is running locally (matching `MONGO_URI` in `.env`)
- Run the Flask API: `python3 -m backend.flask.app`

## Task boards

[Sprint 1](https://github.com/orgs/swe-students-spring2026/projects/38/views/1)
