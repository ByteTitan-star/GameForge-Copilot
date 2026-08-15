"""游戏构建链（docs/build-pipeline.md）。"""

from app.forge.build.catalog import CATALOG_VERSION, DEPENDENCY_CATALOG, validate_catalog_packages
from app.forge.build.code_output import ParsedCodeOutput, parse_code_output
from app.forge.build.dependency_preparer import DependencyPreparer, PrepareResult
from app.forge.build.integration import parse_llm_code_output, run_project_pipeline
from app.forge.build.manifest import generate_manifest_files, merge_workspace
from app.forge.build.pipeline import BuildPipeline, BuildPipelineResult
from app.forge.build.profile import BuildProfile, default_build_profile
from app.forge.build.routing import (
    BuildRouting,
    coerce_build_routing,
    resolve_package_versions,
    routing_from_design_doc,
    should_use_vite_pipeline,
    validate_routing,
)
from app.forge.build.template import load_vite_ts_template_files, vite_ts_template_dir

__all__ = [
    "BuildPipeline",
    "BuildPipelineResult",
    "BuildProfile",
    "BuildRouting",
    "CATALOG_VERSION",
    "DEPENDENCY_CATALOG",
    "DependencyPreparer",
    "ParsedCodeOutput",
    "PrepareResult",
    "coerce_build_routing",
    "default_build_profile",
    "generate_manifest_files",
    "load_vite_ts_template_files",
    "merge_workspace",
    "parse_code_output",
    "parse_llm_code_output",
    "resolve_package_versions",
    "routing_from_design_doc",
    "run_project_pipeline",
    "should_use_vite_pipeline",
    "validate_catalog_packages",
    "validate_routing",
    "vite_ts_template_dir",
]
