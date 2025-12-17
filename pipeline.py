from creat_units import test_stormlib_unit_editor
from training import test_training
from curriculum import Curriculum
from tech_modify import TechController
import json
from configs.map_config import MapConfig
import os
from datetime import datetime
import shutil
from configs.llm_api_config import LLMAPIConfig
import config
from LLM.call_llm_api.call_llm import setup_logger
import logging
import re
from configs.rollout_config import map_name

def extract_unit_abilities(json_data):
    """
    从JSON数据中提取所有unit_abi并按照指定格式存储
    
    参数:
        json_data: JSON格式的字符串或字典
    
    返回:
        test_tech_table: 包含所有技能的列表，格式为[["unit_abi", player1_flag, player2_flag]]
    """
    # 如果输入是字符串，先解析为字典
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    test_tech_table = []
    units = []
    player1_units = []
    player2_units = []
    player1_pos = []
    player2_pos = []
    
    def process_unit_abi(unit_abi, is_player1):
        """处理可能为单个或多个ability的字段"""
        abilities = []
        if isinstance(unit_abi, str):
            # 可能是 "A,B,C"
            abilities = [abi.strip() for abi in unit_abi.split(",") if abi.strip()]
        elif isinstance(unit_abi, list):
            # 已经是列表
            abilities = [abi.strip() for abi in unit_abi if isinstance(abi, str) and abi.strip()]
        
        for abi in abilities:
            test_tech_table.append([abi, is_player1, not is_player1])

    # 提取player1的技能
    if "agent" in data:
        for agent_key, agent_info in data["agent"].items():
            if "unit_abi" in agent_info:
                process_unit_abi(agent_info["unit_abi"], is_player1=True)
            
            if "type" in agent_info:
                unit = agent_info["type"].strip()
                if unit:
                    units.append(unit)
                    if "num" in agent_info:
                        num = agent_info["num"].strip()
                        if num:
                            unit_current = num + " " + unit
                            player1_units.append(unit_current)
            if "pos" in agent_info:
                player1_pos = agent_info["pos"].strip()

    # 提取enemy的技能
    if "enemy" in data:
        for agent_key, agent_info in data["enemy"].items():
            if "unit_abi" in agent_info:
                process_unit_abi(agent_info["unit_abi"], is_player1=False)
            
            if "type" in agent_info:
                unit = agent_info["type"].strip()
                if unit:
                    units.append(unit)
                    if "num" in agent_info:
                        num = agent_info["num"].strip()
                        if num:
                            unit_current = num + " " + unit
                            player2_units.append(unit_current)
            if "pos" in agent_info:
                player2_pos = agent_info["pos"].strip()
    
    return test_tech_table, units, player1_units, player2_units, player1_pos, player2_pos


def modify_config_file(file_path, map_name, new_units=None, new_map_info=None):
    """
    修改配置文件中指定地图的units_info和map_info
    
    Args:
        file_path (str): 配置文件路径
        map_name (str): 地图名称
        new_units (list, optional): 新的单位列表
        new_map_info (str, optional): 新的地图信息
    """
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # 如果提供了新的units_info，则替换
    if new_units is not None:
        new_units_str = str(new_units)
        # 查找并替换units_info
        pattern = f"('{map_name}'.*?'units_info':\s*)\[.*?\]"
        replacement = f"\\1{new_units_str}"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        print(f"已更新配置文件中 {map_name} 的units_info")
    
    # 如果提供了新的map_info，则替换
    if new_map_info is not None:
        # 对字符串中的单引号进行转义，以免在Python字符串中出现问题
        escaped_map_info = new_map_info.replace("'", "\\'")
        
        # 查找并替换map_info
        # 匹配 'map_info':'任何内容（包括换行）直到遇到下一个键或结束'
        pattern = f"('{map_name}'.*?'map_info':\s*)'([^']*(?:\\'[^']*)*)'(?=.*?'units_info'|.*?}},)"
        replacement = f"\\1'{escaped_map_info}'"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        print(f"已更新配置文件中 {map_name} 的map_info")
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

    # 🔥 关键：修改文件后立即重新加载配置
        import config
        config.reload_config()  # 或者使用 config.reload_config_from_file()
    
def save_abilities_info(test_tech_table, filename="abilities_info.json"):
    """
    保存技能信息到JSON文件
    
    Args:
        test_tech_table: 技能表格
        filename: 输出文件名
    """
    abilities_info = {
        "player1_abilities": [],
        "player2_abilities": [],
        "all_abilities": []
    }
    
    for ability, player1_flag, player2_flag in test_tech_table:
        ability_info = {
            "ability": ability,
            "player1": player1_flag,
            "player2": player2_flag
        }
        abilities_info["all_abilities"].append(ability_info)
        
        if player1_flag:
            abilities_info["player1_abilities"].append(ability)
        if player2_flag:
            abilities_info["player2_abilities"].append(ability)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(abilities_info, f, ensure_ascii=False, indent=2)
    
    # print(f"技能信息已保存到 {filename}")

def all_files_exist(units):
    base_dir = 'knowledge_data/firecrawl_test/sc2_unit_info/'
    for unit in units:
        if os.path.exists('{}{}.json'.format(base_dir, unit)) == False:
            print(unit + "is none")
            return False
    return True



if __name__ == "__main__":
    curriculum = Curriculum()
    curr = None
    results = None
    curr_times = 10
    curr_now = 1

    with open('pre_code.py', 'r+', encoding='utf-8') as file:
            file.truncate(0)

    shutil.copy('example.py', 'res-temp.py')

    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # 构建log目录路径 - 使用绝对路径
    main_dir = os.path.abspath(os.path.join("log", time_str))
    # 创建目录（包括父目录log）
    os.makedirs(main_dir, exist_ok=True)
    print(f"📁 创建日志目录: {main_dir}")
    
    for i in range(curr_times):

        log_dir = os.path.join(main_dir, "task_{}".format(i))
        os.makedirs(log_dir, exist_ok=True)
        print(f"📁 创建文件目录: {log_dir}")

        # 修复输出路径构建
        test_map = os.path.join(log_dir, "test.SC2Map")
        print(f"📁 输出地图路径: {test_map}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(test_map), exist_ok=True)

        model_info = LLMAPIConfig.get_model_dict()
        
        # 将日志文件保存在基于时间戳的目录中
        log_filename = '{}#{}#{}#{}#{}.log'.format(
            model_info['planner'], 
            model_info['coder'], 
            model_info['checker'], 
            model_info['summarizer'], 
            config.map_name
        )
        log_path = os.path.join(log_dir, log_filename)  # 使用time_str目录
        
        main_logger = setup_logger('main_logger', log_path, level=logging.DEBUG)
        main_logger.info("Pipeline started.")
#         if curr_now == 1:
#             content = '''
# ###
# AGENTS:
# Marine, 20, (5,25), Stimpack
# Marauder, 12, (5,25), Stimpack
# Medivac, 4, (5,25), CaduceusReactor
# SiegeTank, 6, (5,25), SiegeTech
# Ghost, 8, (5,25), PersonalCloaking
# VikingFighter, 8, (5,25), JotunBoosters
# Cyclone, 8, (5,25), VehicleWeaponsLevel1
# WidowMine, 8, (5,25), Burrow
# Raven, 3, (5,25), CorvidReactor
# Liberator, 4, (5,25), ShipWeaponsLevel1
# ENEMIES:
# Zergling, 60, (25,5), zerglingmovementspeed
# Baneling, 24, (25,5), CentrificalHooks
# Roach, 15, (25,5), GlialReconstitution
# Hydralisk, 10, (25,5), hydraliskspeed
# Lurker, 6, (25,5), Burrow
# Corruptor, 10, (25,5), FlyerWeaponsLevel1
# Infestor, 3, (25,5), EnergyUpgrade
# Viper, 4, (25,5), FlyerArmorsLevel1
# Overseer, 3, (25,5), FlyerArmorsLevel1
# Queen, 4, (25,5), MissileWeaponsLevel1
# BroodLord, 4, (25,5), FlyerWeaponsLevel1
# ###
#             '''
#             prompt = 'The current curriculum design is: ' + str(content)


#             unit_content = re.search(r'AGENTS:(.*?)ENEMIES', prompt, re.DOTALL).group(1)
#             enemy_content = re.search(r'ENEMIES:(.*?)###', prompt, re.DOTALL).group(1)
#             curr = unit_content + enemy_content
#             result_json = curriculum.change_curriculum_json(unit_content.strip(), enemy_content.strip()) 
#         else:
#             curr, result_json = curriculum.generate_curriculum(results, curr)
        curr, result_json = curriculum.generate_curriculum(results, curr)
        data = json.loads(result_json)      
        try: 
            if 'agent' in data:
                for agent_key, agent_info in data['agent'].items():
                    int(agent_info['num'])
            if 'enemy' in data:
                for enemy_key, enemy_info in data['enemy'].items():
                    int(enemy_info['num'])
        except:
            results = 'fail'
            continue
        with open(r".\task.json", "w", encoding="utf-8") as f:
            f.write(result_json)
        test_tech_table, units, player1_units, player2_units, player1_pos, player2_pos = extract_unit_abilities(result_json)
        
        if all_files_exist(units) == False:
            continue

        test_stormlib_unit_editor(r".\task.json", map_name + ".SC2Map", test_map)
        output_map = os.path.join(log_dir, "test1.SC2Map")
        # 设置科技状态 (True=启用, False=禁用)
        
        save_abilities_info(test_tech_table, "abilities_info.json")

        map_info = MapConfig().get_map_config(map_name)['map_info'] + f"The enemy units are at {player2_pos} point and your units are at {player1_pos} point initially. You can control {player1_units} units.The enemy controls {player2_units} units."

        # 执行修改
        editor = TechController()
        success = editor.modify_map(
            input_map_path=test_map,
            output_map_path=output_map,
            tech_table= test_tech_table
        )

        modify_config_file(r"configs/map_config.py", "test1", units, map_info)

        dst = os.path.join("E:\StarCraft II", "maps", "test1.SC2Map")

        os.makedirs(os.path.dirname(dst), exist_ok=True)

        shutil.copy(output_map, dst)
        results = test_training(str(test_tech_table), str(log_dir))

        curr_now += 1