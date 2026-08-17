from app.forge.messages import append_hitl_trace, completion_message_content


def test_append_hitl_trace_keeps_modify_and_art_choice() -> None:
    text = append_hitl_trace("", decision="modify", note="暂停要更明显")
    text = append_hitl_trace(text, decision="approve")
    text = append_hitl_trace(text, decision="select_a")
    assert "暂停要更明显" in text
    assert "已确认策划稿" in text
    assert "选定美术方案 A" in text


def test_completion_message_includes_controls_and_user_basis() -> None:
    text = completion_message_content(
        title="Neon Dodge: 霓虹躲避",
        version=2,
        design_doc={
            "controls": ["WASD 移动", "P 暂停"],
            "core_loop": ["躲避敌人", "累加存活时间"],
        },
        requirement="做一个霓虹躲避游戏，难度随时间上升",
        art_name="赛博网格流光",
        user_notes="暂停要更明显",
    )
    assert "任务执行已完成" in text
    assert "WASD 移动" in text
    assert "霓虹躲避" in text
    assert "你的需求" in text
    assert "选定美术" in text
    assert "你的修改意见" in text
    assert "v2" in text
    assert "躲避敌人" not in text
