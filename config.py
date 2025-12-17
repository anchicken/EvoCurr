import json
from configs.map_config import MapConfig
import os
import importlib
import sys
from configs.rollout_config import agent_name

# 新增：导入sc2单位能力数据
try:
    import sys
    sys.path.append('.')
    from sc2.dicts.unit_abilities import UNIT_ABILITIES
    from sc2.ids.unit_typeid import UnitTypeId
    from sc2.ids.ability_id import AbilityId
    UNIT_ABILITIES_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: Could not import sc2.dicts.unit_abilities, unit abilities will not be included")
    UNIT_ABILITIES_AVAILABLE = False

base_dir = 'knowledge_data/firecrawl_test/sc2_unit_info/'

def process_info(unit_name):
    with open('{}{}.json'.format(base_dir, unit_name), 'r', encoding='utf-8') as reader:
        info_json = json.load(reader)

    info_needed = {}
    info_needed['Unit'] = unit_name
    #info_needed['Type'] = info_json['Type']
    #info_needed['Description'] = info_json['Description']
    info_needed['Attack'] = info_json['Attack']
    info_needed['Unit stats'] = info_json['Unit stats']
    #info_needed['Strong against'] = info_json['Strong against']
    #info_needed['Weak against'] = info_json['Weak against']
    #info_needed["Competitive Usage"] = info_json["Competitive Usage"]

    return str(info_needed)

def extract_python_sc2_api_info(unit_types_list):
    """
    动态提取当前任务涉及单位的python-sc2 API信息
    
    Args:
        unit_types_list: 当前任务中涉及的所有单位类型列表
        
    Returns:
        str: 格式化的API信息字符串，用于注入LLM提示词
    """
    # Unit类的核心属性信息
    unit_properties = {
        "position_attributes": [
            "position",  # Point2 - 单位的2D位置坐标
            "position3d",  # Point3 - 单位的3D位置坐标  
            "position_tuple"  # Tuple[float, float] - 位置的元组形式
        ],
        "health_attributes": [
            "health",  # float - 当前生命值（不包括护盾）
            "health_max",  # float - 最大生命值
            "health_percentage",  # float - 生命百分比
            "shield",  # float - 当前护盾值（神族单位）
            "shield_max",  # float - 最大护盾值
            "shield_percentage",  # float - 护盾百分比
            "energy",  # float - 当前能量值
            "energy_max",  # float - 最大能量值
            "energy_percentage"  # float - 能量百分比
        ],
        "identity_attributes": [
            "tag",  # int - 单位的唯一标识符
            "type_id",  # UnitTypeId - 单位类型ID
            "name",  # str - 单位名称
            "race"  # Race - 单位种族
        ],
        "status_attributes": [
            "is_structure",  # bool - 是否为建筑
            "is_light",  # bool - 是否为轻甲单位
            "is_armored",  # bool - 是否为重甲单位
            "is_biological",  # bool - 是否为生物单位
            "is_mechanical",  # bool - 是否为机械单位
            "is_massive",  # bool - 是否为巨型单位
            "is_psionic",  # bool - 是否为灵能单位
            "is_visible",  # bool - 是否可见
            "is_snapshot"  # bool - 是否为快照单位（战争迷雾中）
        ],
        "combat_attributes": [
            "can_attack",  # bool - 是否能攻击
            "can_attack_ground",  # bool - 是否能攻击地面
            "can_attack_air",  # bool - 是否能攻击空中
            "ground_dps",  # float - 对地面的DPS
            "air_dps",  # float - 对空中的DPS
            "ground_range",  # float - 对地攻击距离
            "air_range"  # float - 对空攻击距离
        ]
    }
    
    # Units类的核心方法信息
    units_methods = {
        "collection_methods": [
            "amount",  # int - 单位数量
            "empty",  # bool - 是否为空集合
            "exists",  # bool - 是否存在单位
            "first",  # Unit - 第一个单位
            "random",  # Unit - 随机单位
            "take(n)"  # Units - 取前n个单位
        ],
        "filter_methods": [
            "of_type(unit_types)",  # Units - 按类型筛选
            "filter(lambda_func)",  # Units - 按条件筛选
            "ready",  # Units - 已完成建造的单位
            "idle",  # Units - 空闲单位
            "closest_to(position)",  # Unit - 距离位置最近的单位
            "furthest_to(position)",  # Unit - 距离位置最远的单位
            "closer_than(distance, position)",  # Units - 距离小于指定值的单位
            "further_than(distance, position)"  # Units - 距离大于指定值的单位
        ],
        "distance_methods": [
            "closest_distance_to(position)",  # float - 到位置的最近距离
            "furthest_distance_to(position)",  # float - 到位置的最远距离
            "in_attack_range_of(unit)"  # Units - 在指定单位攻击范围内的单位
        ]
    }
    
    # BotAI类的核心属性信息
    botai_properties = {
        "unit_access": [
            "self.units",  # Units - 己方所有单位
            "self.enemy_units",  # Units - 敌方所有单位
            "self.structures",  # Units - 己方建筑
            "self.enemy_structures",  # Units - 敌方建筑
            "self.units(UnitTypeId.TYPE)",  # Units - 指定类型的己方单位
            "self.enemy_units(UnitTypeId.TYPE)"  # Units - 指定类型的敌方单位
        ],
        "position_info": [
            "self.start_location",  # Point2 - 己方起始位置
            "self.enemy_start_locations"  # List[Point2] - 敌方可能的起始位置
        ],
        "game_state": [
            "self.time",  # float - 游戏时间（秒）
            "self.state.game_loop",  # int - 游戏循环次数
            "iteration"  # int - on_step的迭代次数参数
        ]
    }
    
    # 根据当前任务的单位类型构建特定的API信息
    api_info = f"""
## Python-SC2 API Reference for Current Units

### Available Unit Types in This Task:
{', '.join(unit_types_list)}

### Unit Object Attributes (for any unit object):

**Position & Movement:**
"""
    
    for attr in unit_properties["position_attributes"]:
        api_info += f"- unit.{attr}  # Access unit position\n"
    
    api_info += "\n**Health & Resources:**\n"
    for attr in unit_properties["health_attributes"]:
        api_info += f"- unit.{attr}  # Access unit health/shield/energy\n"
    
    api_info += "\n**Unit Identity:**\n"
    for attr in unit_properties["identity_attributes"]:
        api_info += f"- unit.{attr}  # Access unit identity info\n"
    
    api_info += "\n**Unit Status Checks:**\n"
    for attr in unit_properties["status_attributes"]:
        api_info += f"- unit.{attr}  # Boolean status check\n"
    
    api_info += "\n**Combat Capabilities:**\n"
    for attr in unit_properties["combat_attributes"]:
        api_info += f"- unit.{attr}  # Combat-related attributes\n"
    
    api_info += "\n### Units Collection Methods (for self.units, self.enemy_units):\n\n"
    
    api_info += "**Collection Operations:**\n"
    for method in units_methods["collection_methods"]:
        api_info += f"- units.{method}  # Collection manipulation\n"
    
    api_info += "\n**Filtering Methods:**\n"
    for method in units_methods["filter_methods"]:
        api_info += f"- units.{method}  # Filter units by criteria\n"
    
    api_info += "\n**Distance Calculations:**\n"
    for method in units_methods["distance_methods"]:
        api_info += f"- units.{method}  # Distance calculations\n"
    
    api_info += "\n### BotAI Access Methods:\n\n"
    
    api_info += "**Unit Access:**\n"
    for prop in botai_properties["unit_access"]:
        api_info += f"- {prop}  # Access unit collections\n"
    
    api_info += "\n**Position Information:**\n"
    for prop in botai_properties["position_info"]:
        api_info += f"- {prop}  # Access position data\n"
    
    api_info += "\n**Game State:**\n"
    for prop in botai_properties["game_state"]:
        api_info += f"- {prop}  # Access game state info\n"
    
    api_info += """
### Common Usage Patterns:

**Safe Unit Access:**
```python
if self.units.exists:
    my_unit = self.units.first
    if my_unit.health_percentage < 0.5:
        # Move damaged unit to safety
        my_unit.move(self.start_location)
```

**Unit Filtering:**
```python
low_health_units = self.units.filter(lambda u: u.health_percentage < 0.3)
enemy_in_range = self.enemy_units.closer_than(10, self.units.center)
```

**Distance-based Operations:**
```python
closest_enemy = self.enemy_units.closest_to(my_unit.position)
if my_unit.distance_to(closest_enemy) < my_unit.ground_range:
    # Can attack
    my_unit.attack(closest_enemy)
```

### IMPORTANT: Always check if collections exist before accessing:
- Use `if self.units.exists:` before `self.units.first`
- Use `if enemy_units:` before accessing enemy_units[0]
- Use `units.amount > 0` to check collection size
"""
    
    return api_info

def extract_unit_abilities(unit_names):
    """
    动态提取指定单位的能力信息
    
    Args:
        unit_names: 单位名称列表，如['marine', 'marauder']
        
    Returns:
        dict: 单位能力信息字典
    """
    if not UNIT_ABILITIES_AVAILABLE:
        return {}
    
    unit_abilities_info = {}
    
    for unit_name in unit_names:
        try:
            # 将字符串转换为UnitTypeId枚举
            # 处理单位名称的大小写转换
            unit_name_formatted = unit_name.upper()
            
            # 特殊处理一些单位名称映射
            unit_name_mapping = {
                'MARINE': 'MARINE',
                'MARAUDER': 'MARAUDER', 
                'STALKER': 'STALKER',
                'ZEALOT': 'ZEALOT',
                'SIEGE_TANK': 'SIEGETANK',
                'SIEGETANK': 'SIEGETANK',
                'SPINE_CRAWLER': 'SPINECRAWLER',
                'SPORE_CRAWLER': 'SPORECRAWLER',
                'HIGH_TEMPLAR': 'HIGHTEMPLAR',
                'HIGHTEMPLAR': 'HIGHTEMPLAR',
                'VOID_RAY': 'VOIDRAY',
                'VOIDRAY': 'VOIDRAY'
            }
            
            # 使用映射或直接使用格式化后的名称
            mapped_name = unit_name_mapping.get(unit_name_formatted, unit_name_formatted)
            
            # 获取UnitTypeId
            if hasattr(UnitTypeId, mapped_name):
                unit_type_id = getattr(UnitTypeId, mapped_name)
                
                # 获取该单位的能力列表
                if unit_type_id in UNIT_ABILITIES:
                    abilities = UNIT_ABILITIES[unit_type_id]
                    
                    # 保留原始的AbilityId信息，不去除前缀
                    ability_names = []
                    for ability in abilities:
                        ability_name = str(ability)  # 保留完整的 AbilityId.XXX 格式
                        ability_names.append(ability_name)
                    
                    unit_abilities_info[unit_name] = {
                        'unit_type': mapped_name,
                        'abilities': sorted(ability_names),  # 排序便于阅读
                        'ability_count': len(ability_names)
                    }
                    
                else:
                    print(f"⚠️ No abilities found for unit: {mapped_name}")
                    
            else:
                print(f"⚠️ Unknown unit type: {mapped_name}")
                
        except Exception as e:
            print(f"❌ Error processing unit {unit_name}: {e}")
    
    return unit_abilities_info

def format_unit_abilities_info(unit_abilities_info):
    """
    格式化单位能力信息为字符串
    
    Args:
        unit_abilities_info: 单位能力信息字典
        
    Returns:
        str: 格式化后的单位能力信息字符串
    """
    if not unit_abilities_info:
        return "No unit abilities information available."
    
    formatted_text = "SC2 API Unit Abilities:\n"
    
    for unit_name, info in unit_abilities_info.items():
        formatted_text += f"{unit_name.upper()}: {', '.join(info['abilities'])}\n"
    
    return formatted_text

def load_abilities_info(filename="abilities_info.json"):
    """
    加载技能信息
    
    Args:
        filename: 技能信息文件名
        
    Returns:
        dict: 技能信息字典，如果文件不存在则返回空字典
    """
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"player1_abilities": [], "player2_abilities": [], "all_abilities": []}

def format_abilities_info(abilities_info):
    """
    格式化技能信息为字符串
    
    Args:
        abilities_info: 技能信息字典
        
    Returns:
        str: 格式化后的技能信息字符串
    """
    if not abilities_info["player1_abilities"]:
        return "Your units have no special abilities available."
    
    abilities_text = "Available abilities for your units:\n"
    for ability in abilities_info["player1_abilities"]:
        abilities_text += f"- {ability}\n"
    
    if abilities_info["player2_abilities"]:
        abilities_text += "\nEnemy units may have the following abilities:\n"
        for ability in abilities_info["player2_abilities"]:
            abilities_text += f"- {ability}\n"
    
    return abilities_text


map_name = 'test1'

# mc = MapConfig().get_map_config(map_name)

# map_config = mc['map_info']
# units = mc['units_info']

# units_info = ''
# for a in set(units):
#     units_info += process_info(a) + '\n'

# # # 🔥 新增：动态提取当前单位的SC2 API能力信息
# # unit_abilities_info = extract_unit_abilities(list(set(units)))
# # unit_abilities_text = format_unit_abilities_info(unit_abilities_info)

# # 加载技能信息
# abilities_info = load_abilities_info("abilities_info.json")
# abilities_text = format_abilities_info(abilities_info)

# # 🚀 新增：动态提取python-sc2 API信息
# # api_info = extract_python_sc2_api_info(list(set(units)))

# unit_config = '''
# The information of the units are:
# {}

# {}

# Remember to use the available abilities strategically during combat.
# When implementing code, you MUST follow the python-sc2 API patterns shown above to avoid runtime errors.
# Always check if unit collections exist before accessing them (use .exists or check length).
# '''.format(units_info,abilities_text)

def reload_config():
    """重新加载配置信息"""
    global map_config, units, units_info, abilities_info, abilities_text, unit_config, task_config
    
    # 重新加载 map_config 模块
    if 'configs.map_config' in sys.modules:
        importlib.reload(sys.modules['configs.map_config'])

    from configs.map_config import MapConfig
    
    # 重新获取地图配置
    mc = MapConfig().get_map_config(map_name)
    map_config = mc['map_info']
    units = mc['units_info']
    
    # 重新处理单位信息
    units_info = ''
    for a in set(units):
        units_info += process_info(a) + '\n'
    
    # 重新加载技能信息
    abilities_info = load_abilities_info("abilities_info.json")
    abilities_text = format_abilities_info(abilities_info)
    
    # 重新构建配置
    unit_config = '''
The information of the units are:
{}

{}

'''.format(units_info, abilities_text)
    
    task_config = map_config + unit_config
    
    return task_config

prefix_code = '''
from datetime import datetime
from sc2 import maps
import os
from sc2.bot_ai import BotAI
from sc2.data import Race, Difficulty
from sc2.ids.ability_id import AbilityId
from sc2.ids.effect_id import EffectId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.buff_id import BuffId
from python_sc2_test.run_pvt_map import ProtossBot
from python_sc2_test.run_zvt_3_map import EnhancedZergBot
import math
import random
import numpy as np
import numpy
from typing import List, Dict, Set, Optional, Union, Iterable
from math import atan2, pi, cos, sin


class BattleBot(BotAI):
'''

post_code = '''
if __name__ == '__main__':
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = time_str + "Example.SC2Replay"
    file_name = os.path.join("replay", file_name)
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    bot = BattleBot()
    result = run_game(maps.get('{}'), [Bot(Race.Random, bot), Bot(Race.Random, {}())], realtime=False, save_replay_as=file_name)
    print(result)
    print(bot.state.score.score)
    print(bot.state.score.total_damage_dealt_life)
    print(bot.state.score.total_damage_taken_life)
    print(bot.state.score.total_damage_taken_shields)
    print(len(bot.units))
    print(len(bot.enemy_units)+ len(bot.enemy_structures))
'''.format(map_name, agent_name)