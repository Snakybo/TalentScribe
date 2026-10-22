# TalentScribe

A Python script that fetches WoW race, class, spec, talent, and pvp talent data from [wago.tools](https://wago.tools), and formats it neatly in a library structure.

This is the data gathering and formatting tool for the [LibTalentTome](https://github.com/Snakybo/LibTalentTome) WoW library.

## Installation

You can either directly install [Python 3](https://www.python.org/), or run this repository within a [container](https://containers.dev/), when using VS Code simply install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension and it will automatically prompt you to re-open it in a container (Docker or Podman required).

## Usage

Run `scribe.py` with the game version(s) to generate. Each version produces a `Provider<version>.lua` file, based on the latest build of its wago.tools product:

Version | wago.tools product | Interface range | Talent system
------- | ------------------ | --------------- | -------------
`Vanilla` | `wow_classic_era` | 11300 - 16000 | Talent tabs
`Forever` | `wowf` | 16000 - 20000 | Traits (`C_Traits`)
`TBC` | `wow_anniversary` | 20505 - 30000 | Talent tabs
`Mists` | `wow_classic` | 50500 - 60000 | Specializations
`Standard` | `wow` | 120000 - 130000 | Traits (`C_Traits`)

For game versions using the trait system, only PvP talents are populated.

Downloaded tables are cached in `.cache/<product>/<build>/`, so subsequent runs for the same build don't need to download them again.

### Within VS Code

This repo ships with VS Code launch configurations for every WoW version, so you can run the script directly from the editor. Simply select the appropriate version (or all of them) and run the configuration.

## scribe.py

The available command-line arguments are:

Argument | Required | Description
-------- | -------- | -----------
(positional) | No | The game version(s) to generate, defaults to all
`-o`, `--output-dir` | No | The directory to write the `Provider<version>.lua` files to, defaults to the current directory
`-b`, `--build` | No | A specific build to use (e.g. `1.15.9.70003`) instead of the latest, only valid when generating a single version
`--cache-dir` | No | The directory to cache downloaded tables in, defaults to `.cache`
`--no-cache` | No | Don't cache downloaded tables

### Example

```sh
python ./scribe.py Mists Standard
python ./scribe.py Vanilla --build 1.15.9.70003
```
