import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

WAGO_URL = "https://wago.tools"
USER_AGENT = "TalentScribe (+https://github.com/Snakybo/TalentScribe)"

HEADER = """-- MIT License
--
-- Copyright (c) 2026 Kevin Krol
--
-- Permission is hereby granted, free of charge, to any person obtaining a copy
-- of this software and associated documentation files (the "Software"), to deal
-- in the Software without restriction, including without limitation the rights
-- to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
-- copies of the Software, and to permit persons to whom the Software is
-- furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included in all
-- copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
-- IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
-- AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
-- OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
-- SOFTWARE.

local LibTalentTome = LibStub and LibStub("LibTalentTome", true)
local _, _, _, interfaceVersion = GetBuildInfo()
"""

class TalentSystem(Enum):
	TALENT_TABS = "tabs"
	SPECIALIZATIONS = "specializations"
	TRAITS = "traits"

@dataclass(frozen=True)
class GameVersion:
	product: str
	min_interface_version: int
	max_interface_version: int
	talent_system: TalentSystem

VERSIONS: dict[str, GameVersion] = {
	"Vanilla": GameVersion("wow_classic_era", 11300, 16000, TalentSystem.TALENT_TABS),
	"Forever": GameVersion("wowf", 16000, 20000, TalentSystem.TRAITS),
	"TBC": GameVersion("wow_anniversary", 20505, 30000, TalentSystem.TALENT_TABS),
	"Mists": GameVersion("wow_classic", 50500, 60000, TalentSystem.SPECIALIZATIONS),
	"Standard": GameVersion("wow", 120000, 130000, TalentSystem.TRAITS),
}

# Placeholder talent that occupies unused slots in the Mists talent grid
DUMMY_TALENT_SPELL_ID = 102052

Row = dict[str, str]

@dataclass
class Specialization:
	index: int
	id: int
	icon: int | None

@dataclass
class Talent:
	id: int
	spell_id: int
	icon: int | None

@dataclass
class Provider:
	version: GameVersion
	build: int
	classes: dict[str, int] = field(default_factory=dict[str, int])
	specializations: dict[int, list[Specialization]] = field(default_factory=dict[int, list[Specialization]])
	talents: dict[int, list[Talent]] = field(default_factory=dict[int, list[Talent]])
	pvp_talents: dict[int, list[Talent]] = field(default_factory=dict[int, list[Talent]])

class Wago:
	def __init__(self, product: str, build: str | None, cache_dir: Path | None):
		self.product = product
		self.build = build or self.latest_build(product)
		self.cache_dir = cache_dir / product / self.build if cache_dir else None

	@staticmethod
	def fetch(url: str) -> bytes:
		request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
		with urllib.request.urlopen(request, timeout=300) as response:
			return response.read()

	@staticmethod
	def latest_build(product: str) -> str:
		builds: dict[str, list[dict[str, Any]]] = json.loads(Wago.fetch(f"{WAGO_URL}/api/builds"))
		versions = [entry["version"] for entry in builds.get(product, [])]
		if not versions:
			raise LookupError(f'no builds found for product "{product}"')
		return max(versions, key=lambda version: int(version.split(".")[-1]))

	def table(self, name: str) -> list[Row]:
		path = self.cache_dir / f"{name}.csv" if self.cache_dir else None
		if path and path.exists():
			data = path.read_bytes()
		else:
			try:
				data = self.fetch(f"{WAGO_URL}/db2/{name}/csv?branch={self.product}&build={self.build}")
			except urllib.error.HTTPError as err:
				if err.code in (400, 404) and b"not found" in err.read().lower():
					return []
				raise
			if path:
				path.parent.mkdir(parents=True, exist_ok=True)
				path.write_bytes(data)
		return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))

def to_int(value: str | None) -> int:
	return int(value) if value else 0

def to_lua(value: Any) -> str:
	if value is None:
		return "nil"
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, str):
		escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
		return f'"{escaped}"'
	return str(value)

def lua_table(entries: list[str], level: int) -> str:
	inner = "\t" * (level + 1)
	return "{\n" + "".join(f"{inner}{entry},\n" for entry in entries) + "\t" * level + "}"

def spell_icons(wago: Wago) -> dict[int, int]:
	icons: dict[int, int] = {}
	for row in wago.table("SpellMisc"):
		spell_id = to_int(row["SpellID"])
		if spell_id not in icons or to_int(row["DifficultyID"]) == 0:
			icons[spell_id] = to_int(row["SpellIconFileDataID"])
	return icons

def make_talent(talent_id: int, spell_id: int, icons: dict[int, int]) -> Talent:
	return Talent(talent_id, spell_id, icons.get(spell_id) or None)

def load_classes(wago: Wago) -> dict[int, str]:
	# Non-playable classes (e.g. Adventurer in Retail) have no roles
	return {to_int(row["ID"]): row["Filename"].upper() for row in wago.table("ChrClasses") if to_int(row["RolesMask"]) != 0}

def load_talent_tabs(wago: Wago, provider: Provider, classes: dict[int, str], icons: dict[int, int]):
	tabs = [row for row in wago.table("TalentTab") if to_int(row["ClassMask"]) != 0]
	tab_classes: dict[int, int] = {}

	for class_id in classes:
		class_tabs = [tab for tab in tabs if to_int(tab["ClassMask"]) & (1 << (class_id - 1))]
		if not class_tabs:
			continue

		provider.specializations[class_id] = [
			Specialization(to_int(tab["OrderIndex"]) + 1, to_int(tab["ID"]), to_int(tab["SpellIconID"]) or None)
			for tab in class_tabs
		]
		for tab in class_tabs:
			tab_classes[to_int(tab["ID"])] = class_id

	for tab_id in tab_classes:
		provider.talents[tab_id] = []

	for row in wago.table("Talent"):
		tab_id = to_int(row["TabID"])
		if tab_id in tab_classes:
			provider.talents[tab_id].append(make_talent(to_int(row["ID"]), to_int(row["SpellRank_0"]), icons))

def load_specializations(wago: Wago, provider: Provider, classes: dict[int, str]):
	for row in wago.table("ChrSpecialization"):
		class_id = to_int(row["ClassID"])
		if class_id in classes:
			provider.specializations.setdefault(class_id, []).append(
				Specialization(to_int(row["OrderIndex"]) + 1, to_int(row["ID"]), to_int(row["SpellIconFileID"]) or None)
			)

def load_tiered_talents(wago: Wago, provider: Provider, icons: dict[int, int]):
	class_talents: defaultdict[int, list[Row]] = defaultdict(list)
	for row in wago.table("Talent"):
		if to_int(row["SpellID"]) != DUMMY_TALENT_SPELL_ID:
			class_talents[to_int(row["ClassID"])].append(row)

	for class_id, specializations in provider.specializations.items():
		for specialization in specializations:
			provider.talents[specialization.id] = [
				make_talent(to_int(row["ID"]), to_int(row["SpellID"]), icons)
				for row in class_talents[class_id]
				if to_int(row["SpecID"]) in (0, specialization.id)
			]

def load_pvp_talents(wago: Wago, provider: Provider, icons: dict[int, int]):
	pvp_talents: defaultdict[int, list[Row]] = defaultdict(list)
	for row in wago.table("PvpTalent"):
		pvp_talents[to_int(row["SpecID"])].append(row)

	for specializations in provider.specializations.values():
		for specialization in specializations:
			if specialization.id in pvp_talents:
				provider.pvp_talents[specialization.id] = [
					make_talent(to_int(row["ID"]), to_int(row["SpellID"]), icons) for row in pvp_talents[specialization.id]
				]

def build_provider(version: GameVersion, build: str | None, cache_dir: Path | None) -> Provider:
	wago = Wago(version.product, build, cache_dir)
	provider = Provider(version, int(wago.build.split(".")[-1]))
	classes = load_classes(wago)
	icons = spell_icons(wago)

	if version.talent_system == TalentSystem.TALENT_TABS:
		load_talent_tabs(wago, provider, classes, icons)
	else:
		load_specializations(wago, provider, classes)
		if version.talent_system == TalentSystem.SPECIALIZATIONS:
			load_tiered_talents(wago, provider, icons)

	provider.classes = {classes[class_id]: class_id for class_id in provider.specializations}

	load_pvp_talents(wago, provider, icons)
	return provider

def talents_to_lua(talents: dict[int, list[Talent]]) -> str:
	return lua_table([
		f"[{spec_id}] = " + lua_table([
			f"{{ id = {t.id}, spellId = {t.spell_id}, icon = {to_lua(t.icon)} }}"
			# Sorted by ID, which matches the in-game talent index order
			for t in sorted(talents[spec_id], key=lambda t: t.id)
		], 2)
		for spec_id in sorted(talents)
	], 1)

def provider_to_lua(provider: Provider) -> str:
	version = provider.version

	classes = lua_table([
		f"[{to_lua(name)}] = {class_id}"
		for name, class_id in sorted(provider.classes.items(), key=lambda c: c[1])
	], 1)

	specializations = lua_table([
		f"[{class_id}] = " + lua_table([
			f"[{s.index}] = {{ id = {s.id}, icon = {to_lua(s.icon)} }}"
			for s in sorted(provider.specializations[class_id], key=lambda s: s.index)
		], 2)
		for class_id in sorted(provider.specializations)
	], 1)

	return f"""{HEADER}
if LibTalentTome == nil or interfaceVersion < {version.min_interface_version} or interfaceVersion >= {version.max_interface_version} then
	return
end

--- @type LibTalentTome.Provider
LibTalentTome:SetProvider({{
	build = {provider.build},
	classes = {classes},
	specializations = {specializations},
	talents = {talents_to_lua(provider.talents)},
	pvpTalents = {talents_to_lua(provider.pvp_talents)}
}})
"""

def main():
	parser = argparse.ArgumentParser(description="Generate LibTalentTome providers from wago.tools DB2 data")
	parser.add_argument("versions", nargs="*", choices=list(VERSIONS), metavar="version", help=f"the game version(s) to generate, defaults to all ({', '.join(VERSIONS)})")
	parser.add_argument("-o", "--output-dir", type=Path, default=Path("."), help="the directory to write Provider<version>.lua files to")
	parser.add_argument("-b", "--build", help="a specific build to use (e.g. 1.15.9.70003), only valid when generating a single version")
	parser.add_argument("--cache-dir", type=Path, default=Path(".cache"), help="the directory to cache downloaded tables in")
	parser.add_argument("--no-cache", action="store_true", help="don't cache downloaded tables")
	args = parser.parse_args()

	versions: list[str] = args.versions or list(VERSIONS)
	if args.build and len(versions) != 1:
		parser.error("--build requires exactly one version")

	for name in versions:
		version = VERSIONS[name]
		try:
			provider = build_provider(version, args.build, None if args.no_cache else args.cache_dir)
		except (OSError, LookupError) as err:
			sys.exit(f'failed to generate "{name}" from {version.product}: {err}')

		output = args.output_dir / f"Provider{name}.lua"
		try:
			output.parent.mkdir(parents=True, exist_ok=True)
			output.write_text(provider_to_lua(provider), encoding="utf-8")
		except OSError as err:
			sys.exit(f'failed to write file "{output}": {err}')

		print(f"{name}: wrote {output} (build {provider.build})")

if __name__ == "__main__":
	main()
