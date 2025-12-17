from openai import OpenAI
import config
from LLM.call_llm_api.call_llm import TextChatbot

class LLMSummarizer:

    def __init__(self, test_tech_table):

        import config

        self.summarizer_bot = TextChatbot("summarizer")
        
        self.task_content = config.reload_config()

        self.abilities = test_tech_table

        with open(r".\configs\terrain_ability.json", "r", encoding="utf-8", errors='ignore') as f:
            self.abilities_name = f.read()

        self.system_content = '''
You are a StarCraft II player and a helpful assistant.
You are now working as a critic.
I will describe the units and enviroment on the map. You should not build any new buildings or new units. 
I will also provide you the result of the code, which might be the bug stacktrace or the combat results.
You should analyse why the code leads to the result and tell me the potential method to improve the performance based on the code. 
You do not need to provide me the refinement code.
Don't suggest to use BuffId.
The initial_position is very important, you should put the important units to safer place( closer to start position ) and you need to ensure the unit's position to avoid any positional conflicts.
'''

    def summarize(self, code, result):
        
        if type(result) == dict:
            result = '''
You win {} times, tie {} times, and lose {} times out of {} combats. There are {} units and {} enemy units left. You give {} damages to the enemy, take {} damage on health, and take {} damage on shield on average.
'''.format(result["win"], result["tie"], result["lose"], result["times"], result["units_num"], result["enemy_num"], result["damage"], result["damage_taken"], result["damage_shield"])


        prompt = self.task_content + '''

The code is: 
{}

The result is: 
{}

The abilitie names are:
{}

The Tie result is equal to lose.
'''.format(code, result, self.abilities_name)

        if 'bug' in result:
            prompt += "There have bug in code, you should figure out the bug reason and provide most important suggest to fix it."

        else:
            prompt += '''
From the result and code. Find out the reason why you lose, and provide suggestions which can win the task. You can give advise from the position, strategy, ability use and so on.
'''

    
        response = self.summarizer_bot.query(self.system_content, prompt, maintain_history=False)


        return response
    
