from openai import OpenAI
from LLM.call_llm_api.call_llm import TextChatbot
from LLM.call_llm_api.call_llm import main_logger
import config
import os
import re
import subprocess
from multiprocessing import Process, Queue
from configs.rollout_config import run_times

class LLMCoder:

    def __init__(self, abilities):
        
        import config

        self.coder_bot = TextChatbot("coder")

        with open('res-temp.py', 'r', encoding='utf-8', errors='ignore') as file:
            self.pre_code = file.read()

        self.task_config = config.reload_config()

        with open(r".\configs\terrain_ability.json", "r", encoding="utf-8", errors='ignore') as f:
            self.abilities_name = f.read()

        self.abilities = abilities

        self.base_task_content =  "The basic task information is: " + self.task_config

        self.prefix_code = config.prefix_code
        self.post_code = config.post_code

        self.system_content = '''
You are a StarCraft II coder. You need to generate code to control bot and win the complex and difficult task.
I will describe the units on the map. You should not build any new buildings or new units or expand your base. 
You must implement the strategy in python with burnysc2/python_sc2 package.
You must create class BattleBot(BotAI).
You should make use of all your units.
You could only define main founction once.
The result should be surrounded in the '```python' and '``` end' structure. 
You need to generate run_game founction below the if __name__ == '__main__': and do not define main founction
Don't use BuffId or has_buff function.
Don't use self.do() function
Don't define global variables
Don't use is_alive or is_sieged.
Don't define run_game() function.
You should change the initial_position base on the start position and the structure of map.
Don't use is_sieged attribute
{}

The basic task content is:
{}

'''.format(self.abilities_name, self.base_task_content)

        
        

    def generate_code(self, promotion='', retry = 0):

        if retry == 10:
            return
         
        if not promotion == '':
            prompt = self.base_task_content + 'The promotion advise for the code is: ' + promotion + '\n the previous code is: ' + self.pre_code + "\nBase on the previous code, generate better code to win the task." + "\nDo not use attribute is_sieged and is_alive." + "\nUse UTF-8 encoding format." + "\nMake sure the output content is less than 350 lines." + "\nDon't use EffectId.FORCEFIELD" + "\nDon't use BuffId or has_buff function." 
        else:
            prompt = self.base_task_content + '\nThe previous code is: ' + self.pre_code + "\nBase on the previous code, generate better code to win the task." + "\nDo not use attribute is_sieged and is_alive." + "\nUse UTF-8 encoding format." + "\nMake sure the output content is less than 350 lines." + "\nDon't use EffectId.FORCEFIELD" + "\nDon't use BuffId or has_buff function." 


        response = self.coder_bot.query(self.system_content, prompt, maintain_history=False)
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
                    return self.generate_code(promotion, retry + 1)

            total_code = self.prefix_code + code + self.post_code

            with open('res-temp.py', 'w') as writer:
                writer.write(total_code)

            return total_code
        except:
            # print("somewhere fault\n")
            return self.generate_code(promotion, retry + 1)
        
    def clean_ansi_codes(self, text):
        """移除ANSI转义序列（颜色代码）"""
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        return ansi_escape.sub('', text)

    def extract_numeric_values(self, result_text):
        """从输出中提取数值，忽略日志信息"""
        lines = result_text.split('\n')
        numeric_values = []

        for line in lines:
            # 清理ANSI代码
            clean_line = self.clean_ansi_codes(line).strip()

            # 跳过空行和明显的日志行
            if not clean_line or 'INFO' in clean_line or 'DEBUG' in clean_line or 'WARNING' in clean_line:
                continue

            # 尝试提取数值
            try:
                # 检查是否为纯数字行
                if clean_line.replace('.', '').replace('-', '').isdigit():
                    numeric_values.append(float(clean_line))
                # 或者尝试从行中提取数字
                elif re.search(r'[-+]?\d*\.?\d+', clean_line):
                    numbers = re.findall(r'[-+]?\d*\.?\d+', clean_line)
                    if numbers:
                        numeric_values.append(float(numbers[0]))
            except ValueError:
                continue

        return numeric_values

    def test_code(self, restart_idx, iter_idx):

        main_logger.debug('Start Testing')
        print('Start Testing')
        running = subprocess.Popen('python res-temp.py', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        invoke_result = running.stdout.read().decode('utf-8', errors='ignore')

        units_num = 0
        enemy_num = 0
        v = 0
        d = 0
        t = 0

        score = 0
        damage_dealt = 0
        damage_taken = 0
        damage_shield = 0

        times = run_times

        if 'Traceback' in invoke_result or 'Error' in invoke_result:
            # BUG
            print('-------------------BUG!!!--------------------')
            print(invoke_result)
            os.popen('mv res-temp.py res-{}-{}-temp{}-{}.py'.format('X', times, restart_idx, iter_idx))
            return {'type': 'bug', 'message': invoke_result}

        elif invoke_result == '':

            os.popen('mv res-temp.py res-{}-{}-temp{}-{}.py'.format('X', times, restart_idx, iter_idx))
            return {'type': 'bug', 'message': 'code incomplete'}

        else:

            q = Queue()

            process_list = []

            for _ in range(times):
                p = Process(target=run_game, args=(q,))
                p.start()
                process_list.append(p)

            for i in range(times):
                process_list[i].join()

            for _ in range(times):
                data = q.get()
                code_result = data['result']
                if code_result == 'bug':
                    os.popen('mv res-temp.py res-{}-{}-temp{}-{}.py'.format('X', times, restart_idx, iter_idx))
                    return {'type': 'bug', 'message': data['content']}
                u, eu, r, s, dd, dt, ds = data['content']
                if r == 'v':
                    v += 1
                elif r == 'd':
                    d += 1
                else:
                    t += 1
                score += s
                damage_dealt += dd
                damage_taken += dt
                damage_shield += ds

                units_num += u
                enemy_num += eu

            score /= times
            damage_dealt /= times
            damage_taken /= times
            damage_shield /= times

            units_num /= times
            enemy_num /= times

            print(
                'You Win {}, Tie {}, and Lose {} out of {} times. There are {} units and {} enemy units left.'.format(v,
                                                                                                                      t,
                                                                                                                      d,
                                                                                                                      times,
                                                                                                                      units_num,
                                                                                                                      enemy_num))
            print(
                'You achieve {} scores, give {} damages to the enemy, take {} damage on health, and take {} damage on shield on average.'.format(
                    score, damage_dealt, damage_taken, damage_shield))
            main_logger.info(
                'You Win {}, Tie {}, and Lose {} out of {} times. There are {} units and {} enemy units left.'.format(v,
                                                                                                                      t,
                                                                                                                      d,
                                                                                                                      times,
                                                                                                                      units_num,
                                                                                                                      enemy_num) +
                'You achieve {} scores, give {} damages to the enemy, take {} damage on health, and take {} damage on shield on average.'.format(
                    score, damage_dealt, damage_taken, damage_shield)
                )

            os.popen('mv res-temp.py res-{}-{}-temp{}-{}.py'.format(v, times, restart_idx, iter_idx))

            for p in process_list:
                p.close()

            return {'type': 'result',
                    'message': {"win": v, "tie": t, "lose": d, "times": times, "score": score, "damage": damage_dealt,
                                "damage_taken": damage_taken, "damage_shield": damage_shield, "units_num": units_num,
                                "enemy_num": enemy_num}}


def run_game(q):
    r = ''

    running = subprocess.Popen('python res-temp.py', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result = running.stdout.read().decode('utf-8', errors='ignore')
    if '<Result' in result:
        startpoint = re.search("<Result", result, re.DOTALL).start()
    else:
        q.put({'result': 'bug', 'content':"result disappear !!!"})
        return
    result = result[startpoint:]
    if 'Traceback' in result or 'Error' in result:
        q.put({'result': 'bug', 'content':result})
        return
    try:
        cells = result.split('\n')
        print('-----------------------------------')
        print(result)
        print(cells)
        score = float(cells[1])
        damage_dealt = float(cells[2])
        damage_taken = float(cells[3])
        damage_shield = float(cells[4])
        unit_num = float(cells[5])
        enemy_unit_num = float(cells[6])

        if "Result.Victory" in cells[0].split(',')[0]:
            r = 'v'
            enemy_unit_num = 0
        elif 'Result.Defeat' in cells[0].split(',')[0]:
            r = 'd'
            unit_num = 0
        else: 
            r = 't'
        q.put({'result': 'data', 'content':(unit_num, enemy_unit_num, r, score, damage_dealt, damage_taken, damage_shield)})
    except:
        q.put({'result': 'bug', 'content':result})