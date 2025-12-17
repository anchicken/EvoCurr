from openai import OpenAI
from LLM.call_llm_api.call_llm import TextChatbot
import random
import os
import re
import json
from configs.rollout_config import wining_rate


class Curriculum:

    def __init__(self):

        self.designer_bot = TextChatbot('designer')

        # self.map_desc = 'The map is pvt of 32*32 sized square map.\nYour units are around (5, 25) point and The enemy units are around (25, 5) point initially.'
        
        self.map_desc = 'The map is pvt of 32*32 sized square map.\nYour units are around (7, 7) point and The enemy units are around (27, 27) point initially.'

        self.unit_ability = json.load(open('configs/unit_ability.json', 'r', encoding='utf-8'))

        self.upgrade_research_list = json.load(open('configs/upgrade_research_list.json', 'r', encoding='utf-8'))

        # self.units = {'Ghost': 8,
        #             'Liberator': 4,
        #             'Marauder': 12,
        #             'Marine': 20,
        #             'Medivac': 4,
        #             'SiegeTank': 6,
        #             'VikingFighter': 8,
        #             'Cyclone': 8,
        #             'WidowMine': 8,
        #             'Thor': 2}

        self.units = {'Ghost': 8,
                    'Liberator': 4,
                    'Marauder': 12,
                    'Marine': 20,
                    'Medivac': 4,
                    'SiegeTank': 6,
                    'VikingFighter': 8,
                    'Cyclone': 8,
                    'WidowMine': 8,
                    'Raven': 3}
        
       
        # self.enemies = {"Zergling" : 60,
        #                 "Baneling" : 24,
        #                 "Roach" : 15,
        #                 "Hydralisk" : 10,
        #                 "Lurker" : 6,
        #                 "Corruptor" : 10,
        #                 "Infestor" : 3,
        #                 "Viper" : 4,
        #                 "Overseer" : 3,
        #                 "Queen" : 4,
        #                 "BroodLord" : 4}

        
        self.enemies = {'Colossus': 4,
                    'Disruptor': 4,
                    'HighTemplar': 9,
                    'Stalker': 15,
                    'Zealot': 15,
                    'Tempest': 5,
                    'Carrier': 4,
                    'Sentry': 10,}
                    
        self.final_task = '''
        the fianl task is:
        "AGENTS": {},
         "ENEMIES": {}
        '''.format(self.units, self.enemies)

        self.upgrade_level = 1

        self.format = '''
        please provide me with the designed curriculum. You should describe the curriculum in this format:

        ###
        AGENTS:
        agent1_type, number, position, ability1
        agent2_type, number, position, ability1, ability2
        ...
        ENEMIES:
        enemy1_type, number, position, ability1
        enemy2_type, number, position, ability1, ability2
        ...
        ###

        You must start with ### and end with ###.
        Do not provide other explanations or descriptions.
        '''

        self.unit_desc = 'You have '
        self.enemy_desc = 'The enemy has '
        for name, num in self.units.items():
            self.unit_desc += '{} {}, '.format(num, name)
        for name, num in self.enemies.items():
            self.enemy_desc += '{} {}, '.format(num, name)
        self.unit_value = '''
        The vaule of units is belowing:
Marine: 50,
Marauder: 100,
Ghost: 150,
Medivac: 120,
SiegeTank: 175,
VIKINGFIGHTER: 125,
VikingFighter: 170,
Cyclone: 125,
WidowMine: 75,
Raven: 200,


Zealot: 75,
Stalker: 125,
Colossus: 300,
HighTemplar: 150,
Disruptor: 250,
Sentry: 75,
DarkTemplar: 175,
Tempest: 300,
Carrier: 400,
        '''

        self.system_prompt = '''You are playing StarCraft II and are a professional Python programmer. You are facing a complex and difficult control task. 
{}
{}
{}
the upgrade_research_list is:
{}
However, this combat is too complex and difficult. You should design a set of curricula to help players win.
You can control the number of each unit type and its ability.
Now, please provide me with the designed curriculum. You should describe the curriculum in this format:

###
AGENTS:
agent1_type, number, position, ability1
agent2_type, number, position, ability1, ability2
...
ENEMIES:
enemy1_type, number, position, ability1
enemy2_type, number, position, ability1, ability2
...
###

You must start with ### and end with ###.

Do not provide other explanations or descriptions.
'''.format(self.map_desc, self.unit_desc, self.enemy_desc, self.upgrade_research_list)


    def generate_curriculum(self, results=None, curr=None):


        if results == "fail":
            curr = None
            with open(r".\task.json", "r", encoding="utf-8", errors='ignore') as f:
                curr = f.read()
            prompt = '''
Last curriculum is {}.
Please generate the curriculum base on the last curriculum and improve the difficult.

You should describe the curriculum in this format:
###
AGENTS:
agent1_type, number, position, ability1
agent2_type, number, position, ability1, ability2
...
ENEMIES:
enemy1_type, number, position, ability1
enemy2_type, number, position, ability1, ability2
...
###
            '''.format(curr)

            # prompt += self.final_task + self.format + 'You need to gradually improve or reduce the difficulty of curriculum.'
            prompt += self.final_task + self.format

        if not results and not curr:
            prompt = 'Generate a basic and easy but complex and reasonabel initial task.(Our combat power can be slightly higher than the enemies and you would better control three or four type of units.), but one that can provide valuable experience for achieving the ultimate task.\n'
            # prompt = 'You must directly generate the final task.'
        else:
            # 添加类型检查，确保results是字典类型且包含必要的键
            if isinstance(results, dict) and 'win' in results and 'times' in results and results['times'] > 0:
                if (results['win'] / results['times']) >= wining_rate:
                    prompt = 'The player successfully completes this curriculum. ' + 'The result is {} times victory, {} times tie, and {} times defeat.\nNow you need to design a more difficult and complex curriculum.'.format(results['win'], results['tie'], results['lose'])
                else:
                    prompt = 'The player fails to complete this curriculum. ' + 'The result is {} times victory, {} times tie, and {} times defeat. The current curriculum might be too difficult for the current player. \nNow you need to design a little simpler curriculum.'.format(results['win'], results['tie'], results['lose'])
            else:
                # 如果results不是期望的格式，则处理为失败情况
                if isinstance(results, str):
                    prompt = f'The player encountered an error: {results}. The current curriculum might be too difficult or there might be implementation issues.\nNow you need to design a little simpler curriculum.'
                else:
                    prompt = 'The player failed to complete this curriculum due to unexpected results. The current curriculum might need adjustment.\nNow you need to design a little simpler curriculum.'

            # prompt += 'The current curriculum design is: ' + str(curr) + '\nNow you may design curriculum based on the current curriculum.' + self.final_task + self.format + 'You need to gradually improve or reduce the difficulty of curriculum.'
            prompt += 'The current curriculum design is: ' + str(curr) + '\nNow you should design curriculum based on the current curriculum, let the curriculum become more close to the final task. But you must make sure this task is banlance.' + self.final_task + self.format
        response = self.designer_bot.query(self.system_prompt, prompt, maintain_history=True)
        try:
            unit_content = re.search(r'AGENTS:(.*?)ENEMIES', response, re.DOTALL).group(1)
            enemy_content = re.search(r'ENEMIES:(.*?)###', response, re.DOTALL).group(1)
            curr = unit_content + enemy_content
            resuslt_json = self.change_curriculum_json(unit_content.strip(), enemy_content.strip()) 
            return curr, resuslt_json
        except:
            print("curriculum is wrong. Regenerating !!!")
            results = 'fail'
            return self.generate_curriculum(results, curr)

        

    def change_curriculum_json(self, unit_info, enemy_info):
        infos = {'agent': {}}
        idx = 1
        for line in unit_info.split('\n'):
            if line.strip() == '':
                continue
            infos['agent']['agent_{}'.format(idx)] = {}
            cells = line.split(',')
            infos['agent']['agent_{}'.format(idx)]['type'] = cells[0]
            infos['agent']['agent_{}'.format(idx)]['num'] = cells[1]
            infos['agent']['agent_{}'.format(idx)]['pos'] = cells[2] + ',' + cells[3]
            infos['agent']['agent_{}'.format(idx)]['unit_abi'] = cells[4]
            for i in range(len(cells) - 5):
                infos['agent']['agent_{}'.format(idx)]['unit_abi'] += ',' + cells[i + 5]

            idx += 1

        infos['enemy'] = {}
        idx = 1
        for line in enemy_info.split('\n'):
            if line.strip() == '':
                continue
            infos['enemy']['enemy_{}'.format(idx)] = {}
            cells = line.split(',')
            infos['enemy']['enemy_{}'.format(idx)]['type'] = cells[0]
            infos['enemy']['enemy_{}'.format(idx)]['num'] = cells[1]
            infos['enemy']['enemy_{}'.format(idx)]['pos'] = cells[2] + ',' + cells[3]
            infos['enemy']['enemy_{}'.format(idx)]['unit_abi'] = cells[4]
            for i in range(len(cells) - 5):
                infos['enemy']['enemy_{}'.format(idx)]['unit_abi'] += ',' + cells[i + 5]

            idx += 1

        return json.dumps(infos)


if __name__ == '__main__':
    pvt = PVT()
    curr = None
    results = None
    curr, result_json = pvt.generate_curriculum(results, curr)
    with open(r".\task.json", "w", encoding="utf-8") as f:
        f.write(result_json)
    # for i in range(10):
        

        
    #     win = random.randint(0,1)
    #     if win == 0:
    #         results = {'win': 0, 'tie': 0, 'lose': 10}
    #     else:
    #         results = {'win': 10, 'tie': 0, 'lose': 0}

    