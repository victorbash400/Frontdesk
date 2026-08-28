#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/build"
mkdir -p "$build"

clang -std=c11 -Wall -Wextra -Werror \
  "$root/AgentEarsRingBuffer.c" \
  "$root/AgentEarsRingBufferTests.c" \
  -o "$build/agent-ears-ring-tests"
"$build/agent-ears-ring-tests"

xcodebuild \
  -project "$root/AgentEars.xcodeproj" \
  -scheme AgentEars \
  -configuration Release \
  -derivedDataPath "$build/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  build
