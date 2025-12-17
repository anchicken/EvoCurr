#!/usr/bin/env python3
"""
usage:
from tech_modify import TechController
editor = TechController()

test_tech_table = [["Stimpack", True, False], ["ShieldWall", True, False]]
# 执行修改
editor = TechController()
success = editor.modify_map(
    input_map_path=test_map,
    output_map_path=output_map,
    tech_table= test_tech_table
)
"""
import os
import shutil
import xml.etree.ElementTree as ET
import re
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("StimpackController")

from ability_editer import StormLibAbilityEditor


class TechController:
    def __init__(self):
        self.editor = StormLibAbilityEditor()

    def _extract_galaxy_script(self):
        """提取地图中的 Galaxy 脚本"""
        return self.editor._extract_file_from_map(self.map_path, "MapScript.galaxy")

    def modify_map(
        self, input_map_path, output_map_path, tech_table
    ):
        """
        修改地图的科技状态
        :param input_map_path: 输入地图路径
        :param output_map_path: 输出地图路径
        :param player1_enable: 是否启用玩家1的科技
        :param player2_enable: 是否启用玩家2的科技
        :param tech:科技名称列表
        :return: 修改是否成功
        """
        try:
            # 1. 复制原始地图
            Path(output_map_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_map_path, output_map_path)
            logger.info(f"地图复制完成: {output_map_path}")

            # 2. 提取并修改 Galaxy 脚本
            galaxy_content = self._extract_galaxy_script(output_map_path)
            if not galaxy_content:
                raise ValueError("无法提取 MapScript.galaxy 内容")

            modified_content = self._inject_tech_logic(
                galaxy_content, tech_table
            )
            if not modified_content:
                raise ValueError("脚本修改失败，返回为空")
            # 3. 保存修改后的脚本到临时文件
            temp_dir = "temp_galaxy_edit"
            os.makedirs(temp_dir, exist_ok=True)
            temp_script_path = os.path.join(temp_dir, "MapScript.galaxy")

            with open(temp_script_path, "w", encoding="utf-8") as f:
                f.write(modified_content)

            # 4. 替换地图中的脚本文件
            self.editor._replace_files_in_map(
                output_map_path, [("MapScript.galaxy", temp_script_path)]
            )

            return True

        except Exception as e:
            logger.error(f"地图修改失败: {e}", exc_info=True)
            return False

    def _extract_galaxy_script(self, map_path):
        """从地图中提取 Galaxy 脚本内容"""
        try:
            script_data = self.editor._extract_file_from_map(
                map_path, "MapScript.galaxy"
            )
            if not script_data:
                logger.warning("地图中未找到 MapScript.galaxy 文件")
                return None
            return script_data.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"提取脚本失败: {e}")
            return None

    def _inject_tech_logic(self, script_content, tech_table):
        init_trigger_pattern = r"(void\s+InitTriggers\s*\(\)\s*{)([\s\S]*?})"
        tech_calls = []
        for tech_data in tech_table:
            level1 = 1 if tech_data[1] else 0
            level2 = 1 if tech_data[2] else 0
            # 创建初始化调用代码
            tech_calls.extend(
                [
                    f"    // 为玩家解锁{tech_data[0]}",
                    f'    libNtve_gf_SetUpgradeLevelForPlayer(1, "{tech_data[0]}", {level1});',
                    f'    libNtve_gf_SetUpgradeLevelForPlayer(2, "{tech_data[0]}", {level2});',
                    ""
                ]
            )
            logger.info(
                f"成功初始化{tech_data[0]}状态触发器: P1={tech_data[1]}, P2={tech_data[2]}"
            )
        init_calls = "\n".join(tech_calls)
        # 查找InitTriggers函数
        match = re.search(init_trigger_pattern, script_content, re.DOTALL)
        if match:
            func_header = match.group(1)
            func_body = match.group(2)
            # 在函数体内添加初始化调用（在已有调用之后）
            # 查找最后一个初始化调用的位置
            last_call_match = re.search(r"gt_\w+_Init\(\);", func_body)
            if last_call_match:
                last_call_end = last_call_match.end()
                before_calls = func_body[:last_call_end]
                after_calls = func_body[last_call_end:]
                new_func_body = before_calls + "\n" + init_calls + after_calls
            else:
                # 如果没有找到现有调用，添加到函数体开头
                new_func_body = func_body.replace("{", "{\n" + init_calls, 1)

            new_func = func_header + new_func_body
            script_content = script_content.replace(match.group(0), new_func)
            logger.info("已在InitTriggers中添加触发器初始化调用")
        else:
            logger.warning("未找到InitTriggers函数，将创建新的")
            new_init_trigger = f"""
//--------------------------------------------------------------------------------------------------
// Trigger Initialization
//--------------------------------------------------------------------------------------------------
void InitTriggers () {{
{init_calls}
}}
"""
            script_content += new_init_trigger

        return script_content


if __name__ == "__main__":
    test_map = r"E:\StarCraft II\Maps\test.SC2Map"
    output_map = r"E:\StarCraft II\Maps\terrain_maps\curriculum.SC2Map"

    # 设置科技状态 (True=启用, False=禁用)
    test_tech_table = [["Stimpack", True, False], ["ShieldWall", True, False]]
    # 执行修改
    editor = TechController()
    success = editor.modify_map(
        input_map_path=test_map,
        output_map_path=output_map,
        tech_table= test_tech_table
    )

    if success:
        print(f"✅ 地图修改成功: {output_map}")
    else:
        print("❌ 地图修改失败，请检查日志")
