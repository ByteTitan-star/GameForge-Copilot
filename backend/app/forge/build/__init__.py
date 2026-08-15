"""游戏构建链（docs/build-pipeline.md）。"""

from app.forge.build.dependency_preparer import DependencyPreparer, PrepareResult
from app.forge.build.pipeline import BuildPipeline, BuildPipelineResult
from app.forge.build.profile import BuildProfile, default_build_profile
from app.forge.build.template import load_vite_ts_template_files, vite_ts_template_dir

__all__ = [
    "BuildPipeline",
    "BuildPipelineResult",
    "BuildProfile",
    "DependencyPreparer",
    "PrepareResult",
    "default_build_profile",
    "load_vite_ts_template_files",
    "vite_ts_template_dir",
]
