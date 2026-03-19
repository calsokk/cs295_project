#!/bin/bash
# Doc: Natural_Language_Code/build/info_build.md
# Launch the Luau fuzzing Docker environment

set -e

# Create shared directories for fuzzer output on host
mkdir -p "${PWD}/shared/corpus"
mkdir -p "${PWD}/shared/crashes"
mkdir -p "${PWD}/shared/logs"

# Detect architecture and select Dockerfile
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    DOCKERFILE="Dockerfile_aarch64"
    IMAGE_TAG="cs295-luau-fuzz-arm64"
else
    DOCKERFILE="Dockerfile"
    IMAGE_TAG="cs295-luau-fuzz"
fi

echo "=== Luau Fuzzing Environment ==="
echo "Architecture: $ARCH"
echo "Dockerfile:   $DOCKERFILE"
echo "Image tag:    $IMAGE_TAG"
echo ""

# Build and run
docker build -t "$IMAGE_TAG" -f "$DOCKERFILE" . && \
    docker run -it \
        --entrypoint /bin/bash \
        -v "${PWD}/shared:/home/student/shared:z" \
        "$IMAGE_TAG"
