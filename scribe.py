import argparse
import sys
import luadata  # type: ignore[import-untyped]
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, cast

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

@dataclass
class Specialization:
	index: int
	id: int
	icon: int | None

@dataclass
class Talent:
	id: int
	icon: int

@dataclass
class Cache:
	min_interface_version: int
	max_interface_version: int
	has_trait_system: bool
	build_id: int = 0
	class_ids: dict[str, int] = field(default_factory=dict[str, int])
	specializations: defaultdict[str, list[Specialization]] = field(default_factory=lambda: defaultdict(list))
	talents: dict[Any, list[Talent]] = field(default_factory=dict[Any, list[Talent]])
	pvp_talents: dict[Any, list[Talent]] = field(default_factory=dict[Any, list[Talent]])

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

def talents_to_lua(talents: dict[Any, list[Talent]], class_ids: dict[str, int]) -> str:
	def sort_key(key: Any) -> tuple[Any, ...]:
		if isinstance(key, str):
			return (0, class_ids.get(key, 0), key)
		return (1, key)

	return lua_table([
		f"[{to_lua(key)}] = " + lua_table([
			f"{{ id = {t.id}, icon = {t.icon} }}"
			for t in sorted(talents[key], key=lambda t: t.id)
		], 2)
		for key in sorted(talents, key=sort_key)
	], 1)

def cache_to_lua(cache: Cache) -> str:
	classes = sorted(cache.class_ids, key=lambda clazz: cache.class_ids[clazz])

	specializations = lua_table([
		f"[{to_lua(clazz)}] = " + lua_table([
			f"[{s.index}] = {{ id = {s.id}, icon = {to_lua(s.icon)} }}"
			for s in sorted(cache.specializations[clazz], key=lambda s: s.id)
		], 2)
		for clazz in classes
	], 1)

	return f"""{HEADER}
if LibTalentTome == nil or interfaceVersion < {cache.min_interface_version} or interfaceVersion >= {cache.max_interface_version} then
	return
end

--- @type LibTalentTome.Provider
LibTalentTome:SetProvider({{
	build = {cache.build_id},
	hasTraitSystem = {to_lua(cache.has_trait_system)},
	classes = {lua_table([f"[{to_lua(clazz)}] = {class_id}" for clazz, class_id in sorted(cache.class_ids.items(), key=lambda c: c[1])], 1)},
	specializations = {specializations},
	talents = {talents_to_lua(cache.talents, cache.class_ids)},
	pvpTalents = {talents_to_lua(cache.pvp_talents, cache.class_ids)}
}})
"""

def parse_talents(entries: list[dict[str, Any]]) -> list[Talent]:
	return [Talent(entry["id"], entry["icon"]) for entry in entries]

def parse_lua(lua: dict[str, Any]) -> Cache:
	cache = Cache(
		min_interface_version=lua["minInterfaceVersion"],
		max_interface_version=lua["maxInterfaceVersion"],
		has_trait_system=lua["hasTraitSystem"],
	)

	for key, data in lua["data"].items():
		cache.build_id = max(cache.build_id, data["lastUpdateBuild"])
		cache.class_ids[data["classFileName"]] = data["classId"]
		specializations = cache.specializations[data["classFileName"]]

		if "specIndex" in data:
			specializations.append(Specialization(data["specIndex"], data["specId"], data.get("specIcon")))

		cache.talents[key] = parse_talents(data.get("talents", []))
		cache.pvp_talents[key] = parse_talents(data.get("pvpTalents", []))

	return cache

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("input", help="the input Lua file")
	parser.add_argument("-o", "--output", help="the output Lua file", default="Talents.lua")
	args = parser.parse_args()

	lua = cast(dict[str, Any], luadata.read(args.input, encoding="utf-8"))  # type: ignore[reportUnknownMemberType]
	result = cache_to_lua(parse_lua(lua))

	try:
		with open(args.output, "w", encoding="utf-8") as fs:
			fs.write(result)
	except OSError as err:
		sys.exit(f'failed to write file "{args.output}": {err}')

if __name__ == "__main__":
	main()
