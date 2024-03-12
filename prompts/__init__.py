import pkg_resources
import llm4mc.utils as mc_utils


def load_prompt(prompt):
    package_path = pkg_resources.resource_filename("llm4mc", "")   # 获取 llm4mc 的路径
    return mc_utils.load_text(f"{package_path}/prompts/{prompt}.txt")
