# Self-host Planning Poker

A hassle-free Planning Poker application to deploy on your NAS.

> **Fork notice:** this is a maintained fork of [axeleroy/self-host-planning-poker](https://github.com/axeleroy/self-host-planning-poker), which has been archived.
> It updates the dependencies to their latest versions (Angular 22, Flask 3, Python 3.13) and adds a dark theme and a
> per-estimate story counter. Many thanks to [Axel Leroy](https://github.com/axeleroy) for the original project (MIT license).

[![GitHub last commit](https://img.shields.io/github/last-commit/JustRixter/self-host-planning-poker?logo=github&logoColor=959DA5)](https://github.com/JustRixter/self-host-planning-poker/commits/main)
[![License](https://img.shields.io/github/license/JustRixter/self-host-planning-poker?logo=github&logoColor=959DA5)](https://github.com/JustRixter/self-host-planning-poker/blob/main/LICENSE)
[![Tests](https://github.com/JustRixter/self-host-planning-poker/actions/workflows/tests.yml/badge.svg)](https://github.com/JustRixter/self-host-planning-poker/actions/workflows/tests.yml)
[![Docker build](https://github.com/JustRixter/self-host-planning-poker/actions/workflows/publish.yml/badge.svg)](https://github.com/JustRixter/self-host-planning-poker/actions/workflows/publish.yml)

## What is it?

This application is intended as a simplified and self-hostable alternative to
[Planning Poker Online](https://planningpokeronline.com/).

It features:

  * Multiple deck types: Fibonacci, modified Fibonacci, T-Shirt sizes, powers of 2 and trust vote (0 to 5)
  * Spectator mode
  * Responsive layout
  * Vote summary
  * Dark theme (follows your system by default, switchable from the navigation bar)
  * Story names: give the story being estimated a name, shared with all the players
  * Estimated stories: each time you finish a round with "New turn", the story's estimate is recorded. The list of the
    estimated stories with their estimates, and the total points (except for T-shirt sizes), is one click away in the
    navigation bar. By default the most-picked card is recorded (the highest one on a tie), but once the cards are
    revealed anyone can pick another value or choose not to record the round. The history is kept in memory: it is reset
    when the deck is changed or the server restarts.
  * Translations _(inherited from the original project; new strings of this fork are English only and fall back to English)_
 
It does not have fancy features like issues management, Jira integration or timers.

## Screenshots
<a href="assets/screenshot.png"><img alt="Application screenshot with cards face down" src="assets/screenshot.png" width="412px"></a>
<a href="assets/screenshot-revealed.png"><img alt="Application screenshot with cards revealed" src="assets/screenshot-revealed.png" width="412px"></a>
<a href="assets/screenshot-dark.png"><img alt="Application screenshot with the dark theme and the list of estimated stories" src="assets/screenshot-dark.png" width="412px"></a>

## Deployment

Deploying the application is easy as it's self-contained in a single container. Images are published to the
GitHub Container Registry by this repository's [workflow](.github/workflows/publish.yml) on each push to `main` and on `vX.Y.Z` tags.
If the package is private, run `docker login ghcr.io` first.
All you need is to create a volume to persist the games settings (ID, name and deck).

### Docker
```bash
docker run \
  -v planning-poker-data:/data \
  -p 8000:8000 \
  ghcr.io/justrixter/self-host-planning-poker:latest
```

### docker-compose
```yml
version: "3"
services:
  planning-poker:
    image: ghcr.io/justrixter/self-host-planning-poker:latest
    ports:
      - 8000:8000
    volumes:
      - planning-poker-data:/data
volumes:
  planning-poker-data: {}
```

### Environment variables

| Variable              | Meaning                                                                                                                                                                                                                                          | Example            |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|
| `APP_ROOT` (optional) | Allows you to deploy to another path than `/`.<br>See [Configuration examples for deploying on sub‐paths](https://github.com/axeleroy/self-host-planning-poker/wiki/Configuration-examples-for-deploying-on-sub%E2%80%90paths) for more details. | `APP_ROOT=/poker/` |
| `SECRET_KEY` (optional) | Secret used to sign the session cookies. A random one is generated at startup if it is not set, which is fine for a single instance. | `SECRET_KEY=change-me` |

### Running behind a reverse-proxy

Refer to [Socket.IO's documentation](https://socket.io/docs/v4/reverse-proxy/)  for setting up your reverse-proxy to work correctly with Socket.IO.

### Customization

See [Customizing the application's style and icon](https://github.com/axeleroy/self-host-planning-poker/wiki/Customizing-the-application's-style-and-icon).

## Getting involved

[Open an issue](https://github.com/JustRixter/self-host-planning-poker/issues/new) or a Pull Request on this fork. The original project's issues are
closed since it is archived.

## Development

The app consists of two parts:

* a [back-end](flask/) written in Python with [Flask](https://flask.palletsprojects.com/), [Flask-SocketIO](https://flask-socketio.readthedocs.io/en/latest/index.html) and [peewee](http://docs.peewee-orm.com/en/latest/).
* a [front-end](angular/) written with [Angular](https://angular.io) and [Socket.IO](https://socket.io/).

### Back-end development

You must first initialise a virtual environment and install the dependencies

```sh
# Run the following commands in the flask/ folder
python3 -m venv env
source env/bin/activate
pip3 install -r requirements.txt
```

Then launching the development server is as easy as that:
```bash
FLASK_DEBUG=1 python app.py
```

#### Run unit tests

After initializing the virtual environment, run this command in the `flask/` directory:
```sh
python -m unittest
```

### Front-end development

> <details>
> <summary>
> <b>Note:</b> You might want to test the front-end against a back-end. You can either follow the instructions in the
> previous section to install and run it locally or use the following command to run it in a Docker container:
> </summary>
>
> ```bash
> docker run --rm -it \
>   -v $(pwd)/flask:/app \
>   -p 5000:5000 \
>   python:3.13-slim \
>   bash -c "cd /app; pip install -r requirements.txt; FLASK_DEBUG=1 gunicorn --worker-class gevent -w 1 app:app --bind 0.0.0.0:5000"
> ```
> </details>

First make sure that [Node.js](https://nodejs.org/en/) 24.15 or newer (required by Angular 22; see `angular/.nvmrc`) is installed.
Then, install dependencies and launch the development server

```sh
# Run the following commands in the angular/ folder
npm install
npm start
```

### Building Docker image

```sh
# After checking out the project
docker build . -t self-host-planning-poker:custom
# Alternatively, if you don't want to checkout the project
docker build https://github.com/JustRixter/self-host-planning-poker.git -t self-host-planning-poker:custom
```
