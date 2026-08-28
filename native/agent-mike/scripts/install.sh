#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
product="$root/build/DerivedData/Build/Products/Release/AgentMike.driver"
destination=/Library/Audio/Plug-Ins/HAL/AgentMike.driver

"$root/scripts/test.sh"
test -d "$product"
sudo ditto "$product" "$destination"
sudo codesign --force --deep --sign - "$destination"
sudo killall coreaudiod

if ! system_profiler SPAudioDataType | grep -q "Agent Mike:"; then
  echo "Agent Mike did not appear after Core Audio restarted." >&2
  exit 1
fi

echo "Agent Mike is installed and visible to Core Audio."
