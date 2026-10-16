#!/usr/bin/env python3
"""Attribute retained GNU linker-map sections without building firmware."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


def classify(obj):
    if "/src/MicroPython/" in obj:
        relative = obj.split("/src/MicroPython/", 1)[1]
        parts = relative.split("/")
        return "/".join(parts[:2]) if parts[0] == "PicoCalc" else parts[0]
    if "liblvgl.a(" in obj:
        return "PicoCalc/picoware_lvgl"
    for fragment, group in (
        ("frozen_content.c.o", "frozen Python"),
        ("cyw43", "CYW43"),
        ("btstack", "Bluetooth stack"),
        ("mbedtls", "TLS"),
        ("/lib/lwip/", "lwIP"),
        ("pico_lwip/", "lwIP"),
        ("/py/", "MicroPython core"),
    ):
        if fragment in obj:
            return group
    return "other"


def retained_sections(map_text, regions):
    # Ignore discarded input sections and the cross-reference symbol listing.
    linked = map_text.split("Linker script and memory map", 1)[1]
    linked = linked.split("Cross Reference Table", 1)[0]
    inline = re.compile(r"^\s+(\.\S+)\s+(0x[\da-f]+)\s+(0x[\da-f]+)\s+(.+\.o(?:\))?)$")
    continuation = re.compile(r"^\s+(0x[\da-f]+)\s+(0x[\da-f]+)\s+(.+\.o(?:\))?)$")
    name_only = re.compile(r"^\s+(\.\S+)\s*$")
    pending = None
    for line in linked.splitlines():
        match = inline.match(line)
        if match:
            section, address, size, obj = match.groups()
        else:
            match = continuation.match(line)
            if match and pending:
                section = pending
                address, size, obj = match.groups()
            else:
                name = name_only.match(line)
                pending = name.group(1) if name else None
                continue
        pending = None
        address, size = int(address, 16), int(size, 16)
        if not size:
            continue
        for region, (origin, length) in regions.items():
            if origin <= address and address + size <= origin + length:
                yield section, address, size, obj, region
                break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--build-log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    map_bytes = args.map.read_bytes()
    map_text = map_bytes.decode()
    memory = map_text.split("Memory Configuration", 1)[1].split("Linker script and memory map", 1)[0]
    regions = {}
    for name in ("FLASH", "RAM"):
        match = re.search(r"^" + name + r"\s+(0x[\da-f]+)\s+(0x[\da-f]+)", memory, re.M)
        if not match:
            raise ValueError("Missing memory region: " + name)
        regions[name] = tuple(int(value, 16) for value in match.groups())
    groups = defaultdict(lambda: {"flash_sections_bytes": 0, "ram_sections_bytes": 0})
    frozen = []
    spans = defaultdict(list)
    for section, address, size, obj, region in retained_sections(map_text, regions):
        group = classify(obj)
        groups[group]["flash_sections_bytes" if region == "FLASH" else "ram_sections_bytes"] += size
        spans[region].append((address, address + size))
        if group == "frozen Python" and region == "FLASH":
            frozen.append((section, size))
    # Overlaps usually indicate that output sections were counted as inputs.
    for region, intervals in spans.items():
        intervals.sort()
        if any(left[1] > right[0] for left, right in zip(intervals, intervals[1:])):
            raise ValueError("Overlapping retained section attribution in " + region)
    modules = {}
    for path in (project / "src/MicroPython/picoware").rglob("*.py"):
        relative = path.relative_to(project / "src/MicroPython")
        symbol = relative.with_suffix("").as_posix().replace("/", "_")
        modules[symbol] = relative.as_posix()
    ordered = sorted(modules, key=len, reverse=True)
    frozen_modules = defaultdict(int)
    for section, size in frozen:
        module = next((modules[name] for name in ordered if name in section), "shared/unattributed")
        frozen_modules[module] += size
    usage = {}
    if args.build_log:
        for name, used, available in re.findall(r"^\s*(FLASH|FLASH_FS|RAM):\s+(\d+) B\s+(\d+) KB", args.build_log.read_text(), re.M):
            usage[name] = {"used_bytes": int(used), "capacity_bytes": int(available) * 1024}
    report = {
        "map_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "reported_link_usage": usage,
        "regions": {name: {"origin": hex(origin), "length_bytes": length} for name, (origin, length) in regions.items()},
        "groups": dict(sorted(groups.items(), key=lambda item: item[1]["flash_sections_bytes"], reverse=True)),
        "frozen_module_sections": dict(sorted(frozen_modules.items(), key=lambda item: item[1], reverse=True)),
        "current_picoware_python_source_count": len(modules),
        "notes": [
            "Retained input sections attributed to object files, not predicted removal savings.",
            "Flash attribution excludes padding, shared overhead and flash load images for RAM sections.",
            "RAM attribution is linked static sections, not runtime heap use or free memory.",
            "Frozen module attribution matches symbol names against current source paths; shared constants remain unattributed.",
            "Source inventory is current; map measurements describe the previously linked firmware.",
        ],
    }
    result = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
        print("Firmware audit written:", args.output)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
