#!/usr/bin/env bash
# Builds the Lambda image from the current commit, pushes it to the environment's
# ECR repository, and plans or applies Terraform for that environment.
#   scripts/deploy.sh staging plan     build, push, and show the Terraform plan
#   scripts/deploy.sh staging apply    the same, then apply exactly the plan shown
# Every apply runs a saved plan that was printed first; nothing is auto-approved.
# The image tag is the git commit, so every deploy maps to exact code.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV="${1:?usage: deploy.sh <staging|prod> <plan|apply>}"
MODE="${2:?usage: deploy.sh <staging|prod> <plan|apply>}"
TF_DIR="terraform/envs/$ENV"
[ -d "$TF_DIR" ] || { echo "no Terraform environment at $TF_DIR"; exit 1; }

if [ -n "$(git status --porcelain -- image)" ]; then
  echo "image/ has uncommitted changes; commit first so the tag matches the code"; exit 1
fi
TAG="$(git rev-parse --short=12 HEAD)"

terraform -chdir="$TF_DIR" init -input=false >/dev/null

plan_and_maybe_apply() {  # $1 = image tag
  terraform -chdir="$TF_DIR" plan -input=false -var image_tag="$1" -out=tfplan
  if [ "$MODE" = "apply" ]; then
    terraform -chdir="$TF_DIR" apply -input=false tfplan
  fi
  rm -f "$TF_DIR/tfplan"
}

# First run: the repository (and role, logs) must exist before an image can be pushed.
if ! REPO="$(terraform -chdir="$TF_DIR" output -raw repository_url 2>/dev/null)" || [ -z "$REPO" ]; then
  echo "== $ENV has no image repository yet; plan for creating it:"
  plan_and_maybe_apply ""
  [ "$MODE" = "apply" ] || { echo "run with 'apply' to create it, then rerun"; exit 0; }
  REPO="$(terraform -chdir="$TF_DIR" output -raw repository_url)"
fi
REGISTRY="${REPO%%/*}"

if aws ecr describe-images --repository-name "${REPO##*/}" --image-ids imageTag="$TAG" >/dev/null 2>&1; then
  echo "== image $TAG already in $REPO"
else
  echo "== building and pushing $REPO:$TAG"
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
  # Single-platform image without attestations: Lambda rejects multi-manifest indexes.
  docker build --platform linux/arm64 --provenance=false -t "$REPO:$TAG" image
  docker push -q "$REPO:$TAG"
fi

plan_and_maybe_apply "$TAG"

if [ "$MODE" = "apply" ]; then
  API="$(terraform -chdir="$TF_DIR" output -raw api_url)"
  # The first start after a new image fetches it uncached and can take 10+ seconds;
  # take that hit here instead of on a visitor's request.
  echo "== warming up $API"
  curl -s -m 60 -o /dev/null -w "warm-up: HTTP %{http_code} in %{time_total}s\n" -X POST "$API" \
    -H 'Content-Type: application/json' -d '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"AAPL"}'
fi
