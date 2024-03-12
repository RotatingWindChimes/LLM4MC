import os
import pkg_resources
import llm4mc.utils as mc_utils


def load_basic_skills(skills_names=None):
    package_path = pkg_resources.resource_filename("llm4mc", "")

    if skills_names is None:
        skills_names = [skills[:-3] for skills in os.listdir(f"{package_path}/basic_skills") if skills.endswith(".js")]

    primitives = '\n\n'.join([
        mc_utils.load_text(f"{package_path}/basic_skills/{skill_name}.js") for skill_name in skills_names
    ])

    return primitives
