# tap-lastfm

`tap-lastfm` is a Singer tap for LastFM.

Built with the [Meltano Tap SDK](https://sdk.meltano.com) for Singer Taps.

## Installation
```bash
pipx install git+https://github.com/rabidaudio/tap-lastfm.git@v0.1.0
```

## Configuration

### Accepted Config Options

- `api_key` (required): The API key to authenticate against the API service.
- `usernames` (required): A list of usernames to fetch data for.
- `start_date`: The earliest record date to sync. Defaults to all data.
- `step_days`: The number of days to scan through before emitting state. Defaults to 30.

A full list of supported settings and capabilities for this
tap is available by running:

```bash
tap-lastfm --about
```

### Source Authentication and Authorization

Last.fm requires an API key even to read public data. [See directions on how to request an API key here.](https://www.last.fm/api/authentication). At this time, the tap does not access any non-public data, so signatures and session keys are not required.

## Usage

You can easily run `tap-lastfm` by itself or in a pipeline using [Meltano](https://meltano.com/).

### Executing the Tap Directly

```bash
tap-lastfm --version
tap-lastfm --help
tap-lastfm --config CONFIG --discover > ./catalog.json
```

## Developer Resources

- Last.FM API docs: https://www.last.fm/api

### Initialize your Development Environment

```bash
pipx install poetry
poetry install
```

### Create and Run Tests

Create tests within the `tap_lastfm/tests` subfolder and
  then run:

```bash
tox -e pytest
```

You can also test the `tap-lastfm` CLI interface directly using `poetry run`:

```bash
poetry run tap-lastfm --help
```

### Testing with [Meltano](https://www.meltano.com)

_**Note:** This tap will work in any Singer environment and does not require Meltano.
Examples here are for convenience and to streamline end-to-end orchestration scenarios._

Your project comes with a custom `meltano.yml` project file already created. Open the `meltano.yml` and follow any _"TODO"_ items listed in
the file.

Next, install Meltano (if you haven't already) and any needed plugins:

```bash
# Install meltano
pipx install meltano
# Initialize meltano within this directory
cd tap-lastfm
meltano install
```

Now you can test and orchestrate using Meltano:

```bash
# Test invocation:
meltano invoke tap-lastfm --version
# OR run a test `elt` pipeline:
meltano elt tap-lastfm target-jsonl
```

### SDK Dev Guide

See the [dev guide](https://sdk.meltano.com/en/latest/dev_guide.html) for more instructions on how to use the SDK to 
develop your own taps and targets.
