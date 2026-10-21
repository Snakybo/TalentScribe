# TalentScribe

A Python script that parses raw WoW  class, spec, talent, and pvp talent data, and formats it neatly in a library structure.

It's part of a three-project suite:

1. [TalentScout](https://github.com/Snakybo/TalentScout) - the WoW addon that extracts raw class, spec, talent, and pvp data
2. **TalentScribe - the Python utility that converts the raw data into a library structure**
3. [LibTalentTome](https://github.com/Snakybo/LibTalentTome) - the WoW library that exposes all data via a simple API

> In the future, this might be simplified and fetch data directly from [wago.tools](wago.tools)

## Installation

You can either directly install [Python 3](https://www.python.org/), or run this repository within a [container](https://containers.dev/), when using VS Code simply install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension and it will automatically prompt you to re-open it in a container (Docker or Podman required).

## Usage

Run `scribe.py` (required arguments below).

### Within VS Code

This repo ships with VS Code launch configurations for every WoW expansion, so you can run the script directly from the editor. Simply select the appropriate expansion and run the configuration. You'll be prompted for the path to the your `TalentScout.lua` file, after that a new file will be created with the parsed data.

## scribe.py

The available command-line arguments are:

Argument | Required | Description
-------- | -------- | -----------
`-o`, `--output` | Yes | The output .lua file
(positional) | Yes | The input TalentScout.lua file

### Example

```python
py ./scribe.py --output "ProviderStandard.lua" TalentScout.lua
```
