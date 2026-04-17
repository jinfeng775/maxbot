"""
技能管理工具

提供技能的查询、安装、卸载等功能
"""

from maxbot.tools._registry import registry


@registry.tool(
    name="list_skills",
    description="列出所有可用的技能"
)
def list_skills() -> str:
    """列出所有技能"""
    from maxbot.skills import SkillManager
    import json

    try:
        sm = SkillManager()
        skills = sm.list_skills()

        if not skills:
            return json.dumps({
                "message": "没有找到任何技能",
                "skills": []
            }, ensure_ascii=False)

        skill_list = []
        for skill in skills:
            skill_list.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "triggers": skill.triggers,
                "tools_needed": skill.tools_needed,
            })

        return json.dumps({
            "message": f"找到 {len(skills)} 个技能",
            "skills": skill_list
        }, ensure_ascii=False)
    except Exception as e:
        import json
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@registry.tool(
    name="get_skill",
    description="获取指定技能的详细信息"
)
def get_skill(name: str) -> str:
    """获取技能详情"""
    from maxbot.skills import SkillManager
    import json

    try:
        sm = SkillManager()
        skill = sm.get_skill(name)

        if not skill:
            return json.dumps({
                "error": f"未找到技能: {name}"
            }, ensure_ascii=False)

        return json.dumps({
            "name": skill.name,
            "description": skill.description,
            "content": skill.content,
            "category": skill.category,
            "triggers": skill.triggers,
            "tools_needed": skill.tools_needed,
            "path": str(skill.path)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@registry.tool(
    name="install_skill",
    description="安装一个新的技能"
)
def install_skill(name: str, content: str, description: str = "") -> str:
    """安装技能"""
    from maxbot.skills import SkillManager
    import json

    try:
        sm = SkillManager()

        # 构建技能内容
        skill_content = content
        if description:
            skill_content = f"---\ntriggers: []\ntools: []\ncategory: general\ndescription: {description}\n---\n\n{content}"

        skill = sm.install_skill(name, skill_content)

        return json.dumps({
            "message": f"技能 {name} 安装成功",
            "skill": {
                "name": skill.name,
                "description": skill.description,
                "category": skill.category
            }
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@registry.tool(
    name="match_skills",
    description="根据用户消息匹配相关技能"
)
def match_skills(user_message: str) -> str:
    """匹配技能"""
    from maxbot.skills import SkillManager
    import json

    try:
        sm = SkillManager()
        matched = sm.match_skills(user_message)

        if not matched:
            return json.dumps({
                "message": "没有匹配的技能",
                "matched": []
            }, ensure_ascii=False)

        matched_list = []
        for skill in matched:
            matched_list.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "triggers": skill.triggers
            })

        return json.dumps({
            "message": f"找到 {len(matched)} 个匹配的技能",
            "matched": matched_list
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
