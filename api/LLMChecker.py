import ast
from nt import error
import re
import json
import os
from typing import Dict, List, Tuple, Any
from LLM.call_llm_api.call_llm import TextChatbot
from LLM.call_llm_api.call_llm import main_logger


class LLMChecker:
    
    def __init__(self, abilities):
        self.checker_bot = TextChatbot("checker")

        import config
        self.task_config = config.reload_config()
        
        # 加载单位能力配置
        self.unit_ability = json.load(open('configs/unit_ability.json', 'r', encoding='utf-8'))
        
        # python-sc2 API 规范
        self.valid_imports = {
            'sc2', 'sc2.bot_ai', 'sc2.data', 'sc2.ids', 'sc2.position', 'sc2.unit', 'sc2.units',
            'sc2.ids.unit_typeid', 'sc2.ids.ability_id', 'sc2.ids.upgrade_id', 'sc2.ids.buff_id',
            'sc2.position.Point2', 'sc2.position.Point3', 'sc2.position.Pointlike'
        }
        
        # 有效的 BotAI 方法
        self.valid_bot_methods = {
            'units', 'enemy_units', 'structures', 'enemy_structures', 'workers', 'townhalls',
            'mineral_field', 'vespene_geyser', 'expansion_locations', 'start_location',
            'enemy_start_locations', 'game_loop', 'time', 'supply_used', 'supply_cap',
            'supply_left', 'minerals', 'vespene', 'can_afford', 'select_build_worker',
            'find_placement', 'build', 'train', 'research', 'upgrade', 'warp_in',
            'already_pending', 'do', 'can_cast', 'get_random_enemy_start_location'
        }
        
        # 有效的 Unit 属性和方法
        self.valid_unit_attributes = {
            'position', 'tag', 'type_id', 'health', 'health_max', 'shield', 'shield_max',
            'energy', 'energy_max', 'mineral_contents', 'vespene_contents', 'is_structure',
            'is_light', 'is_armored', 'is_biological', 'is_mechanical', 'is_massive',
            'is_psionic', 'is_detector', 'is_flying', 'is_burrowed', 'is_cloaked',
            'is_selected', 'is_idle', 'is_carrying_minerals', 'is_carrying_vespene',
            'is_carrying_resource', 'is_gathering', 'is_returning', 'is_patrolling',
            'is_attacking', 'is_moving', 'distance_to', 'closest_to', 'furthest_to',
            'in_range_of', 'move', 'attack', 'hold_position', 'stop', 'patrol',
            'build', 'train', 'research', 'upgrade', 'warp_in', 'gather', 'return_resource'
        }
        
        # 有效的 Units 集合方法
        self.valid_units_methods = {
            'ready', 'not_ready', 'idle', 'of_type', 'exclude_type', 'tags_in', 'tags_not_in',
            'closer_than', 'further_than', 'in_range_of', 'sorted_by_distance_to',
            'closest_to', 'furthest_to', 'filter', 'random', 'amount', 'exists',
            'empty', 'take', 'subgroup', 'prefer_idle', 'owned'
        }
        
        # 常见的错误模式
        self.error_patterns = [
            r'\.build\([^)]*\)(?!\s*\.)',  # build方法没有正确使用
            r'self\.units\.(?!(?:' + '|'.join(self.valid_units_methods) + r'))',  # 无效的units方法
            r'\.(?!(?:' + '|'.join(self.valid_unit_attributes) + r'))\w+',  # 无效的unit属性
        ]
        

        self.prefix_code = config.prefix_code
        self.post_code = config.post_code

        self.rule ='''
You must implement the rules below:
You must implement the rule in python with burnysc2/python_sc2 package.
You must create class BattleBot(BotAI).
You must generate code less than 300 lines.
You could only define main founction once.
The result should be surrounded in the '```python' and '``` end' structure. 
You need to generate run_game founction below the if __name__ == '__main__': and do not define main founction
Don't use self.do() function.
'''

        # 系统提示
        self.system_content = '''
You are a code reviewer specialized in StarCraft II python-sc2 API. 
Your task is to check if the generated code follows the python-sc2 API specifications.
You should identify potential issues including:
1. Invalid API calls
2. Incorrect method usage
3. Missing error handling
4. Logic errors
5. Performance issues

The result should be surrounded in the '```python' and '``` end' structure. 
'''
        self.abilities = abilities

        self.basic_task = 'The basic task is:' + self.task_config

        self.correct_usage = '''
The unit abilities are:
{}

The valid bot methods are:
{}

The valid unit attributes are:
{}

The valid units methods are:
{}
'''.format(self.unit_ability, self.valid_bot_methods, self.valid_unit_attributes, self.valid_units_methods)


    def check_code(self, code, retry = 0):

        if retry == 10:
            return
         
        
        prompt = 'The basic task content is: ' + self.basic_task + '\nYou need to check where the code confrom to the correct norms.' + '\nThe code is:' + code + '\nThe correct usage are\n' + self.correct_usage + self.rule

        response = self.checker_bot.query(self.system_content, prompt, maintain_history=False)
        try:
            
            startpoint = re.search(r'class\s+(\w+)\s*\(BotAI\):', response, re.DOTALL).end()

            code = response[startpoint:]


            if 'if __name__' in code: 
                endpoint = re.search(r'if __name__', code, re.DOTALL).start()

            else:
                if '```' in code:
                    endpoint = re.search('```', code, re.DOTALL).start()
                else:
                    endpoint = -1

            code = code[:endpoint]
            if 'async def on_step(self, iteration' not in code:
                if 'def on_step(self, iteration' in code:
                    code = code.replace(
                        'def on_step(self, iteration',
                        'async def on_step(self, iteration',
                        1
                    )
                else:
                    return self.check_code(code, retry + 1)

            total_code = self.prefix_code + code + self.post_code

            with open('res-temp.py', 'w') as writer:
                writer.write(total_code)

            return total_code
        except:
            # print("somewhere fault\n")
            return self.check_code(code, retry + 1)

    