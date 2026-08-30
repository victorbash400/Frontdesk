"""Deploy only the standalone ADK runtime, never the backend's local records."""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def stage_runtime(destination: Path) -> list[str]:
    package = destination / "agent_runtime"
    package.mkdir(parents=True)
    for source in sorted((ROOT / "agent_runtime").glob("*.py")):
        if source.is_symlink():
            raise RuntimeError(f"Deployment source must not be a symlink: {source.name}")
        shutil.copy2(source, package / source.name)
    shutil.copy2(ROOT / "agent_runtime/requirements.txt", destination / "requirements.txt")
    return ["agent_runtime"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--relay-url", required=True)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--resource", help="Update this exact existing Agent Engine instead of creating one.")
    args = parser.parse_args()
    if urlparse(args.relay_url).scheme != "https":
        parser.error("--relay-url must use HTTPS")

    os.environ.setdefault("GRPC_DNS_RESOLVER", "native")
    import vertexai
    from google.cloud.aiplatform_v1.types.env_var import SecretRef
    from vertexai import agent_engines

    os.environ["FRONT_DESK_CLOUD_PROJECT"] = args.project
    sys.path.insert(0, str(ROOT))
    from agent_runtime.agent import create_agent

    vertexai.init(project=args.project, location=args.region, staging_bucket=f"gs://{args.bucket}", api_transport="grpc")
    existing = list(agent_engines.list(filter='display_name="Front Desk Agent"'))
    if args.resource and args.resource not in {item.resource_name for item in existing}:
        raise RuntimeError("The requested Front Desk Agent does not exist in this project and region.")
    if not args.resource and existing:
        raise RuntimeError("Front Desk Agent already exists. Pass its exact --resource to update it.")
    application = agent_engines.AdkApp(agent=create_agent(), app_name="front_desk_runtime", enable_tracing=True)
    with tempfile.TemporaryDirectory(prefix="front-desk-agent-engine-") as directory:
        package_root = Path(directory)
        packages = stage_runtime(package_root)
        original_directory = Path.cwd()
        try:
            os.chdir(package_root)
            settings = {
                "display_name": "Front Desk Agent",
                "description": "Front Desk ADK agents with account-scoped cloud tools and durable sessions",
                "requirements": str(package_root / "requirements.txt"),
                "extra_packages": packages,
                "service_account": args.service_account,
                "env_vars": {
                    "FRONT_DESK_CLOUD_PROJECT": args.project,
                    "FRONT_DESK_TOOL_RELAY_URL": args.relay_url.rstrip("/"),
                    "FRONT_DESK_INTERNAL_SECRET": SecretRef(secret=args.secret, version="latest"),
                },
                "min_instances": 1,
                "max_instances": 2,
                "container_concurrency": 4,
                "resource_limits": {"cpu": "2", "memory": "4Gi"},
            }
            if args.resource:
                remote = agent_engines.update(args.resource, agent_engine=application, **settings)
            else:
                remote = agent_engines.create(application, **settings)
            print(remote.resource_name)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
