from openai import OpenAI
from LLM.call_llm_api.call_llm import TextChatbot
import config
import re
import shutil

class LLMPlanner:
    
    def __init__(self, abilities):

        import config

        self.task_config = config.reload_config()

        self.planner_bot = TextChatbot("planner")

        self.abilities = abilities

        self.system_content = '''
You are a StarCraft II player and a helpful assistant and you are facing the complex and difficult tasks.
I will describe the map and the units on the map. You should not build any new buildings or new units. 
You should focus on management tactics to win the combat.
There are basic tactics like Stutter-Step Kiting, Focus Fire, Baiting, aviod aoe, forming line and so on. Meanwhile, diffierent type of units have their special tactics.
You should provide me the tactics in the format below:
### Tactic 1: Tactic 1' name
**Condition to use:**
**Tactic Skeleton**

### Tactic 2: Tactic 2' name
**Condition to use:**
**Tactic Skeleton**
 
'''

        self.task_content = "The basic task content is: " + self.task_config + "The abilities in this task are:" + self.abilities + '''
You should provide me with the most important tactics and describe the chosen tactic skeleton in detail according to the situations of your unit and enemy units.
You should also indicate the condition to use this tactic. Make sure the conditions are not conflict with each other. 
You must realize that someone has to bear the attack in front.
'''

        self.tactic_history = {}



    def plan(self, message=None, tactics = '', promotion = ''):

        if not message==None:

            if type(message) == str:
                result = '''The generated code has bug which might not be the reason from you. '''
            else:
                result = '''
You win {} times, tie {} times, and lose {} times out of {} combats. There are {} units and {} enemy units left. You achieve {} scores, give {} damages to the enemy, take {} damage on health, and take {} damage on shield on average.
'''.format(message["win"], message["tie"], message["lose"], message["times"], message["units_num"], message["enemy_num"], message["score"], message["damage"], message["damage_taken"], message["damage_shield"])


            # history = 'The history strategy and the results are: '
            # for k, v in self.tactic_history.items():
            #     history += '[{}]: {} scores, '.format(k, v[0])


        if not promotion == '':
            result_message = "The result is:" + result + 'The history tactics are:' + tactics + 'The promotion is:' + promotion + 'To improve the winning rates, you can change some new tactic or add some new tactics based on the history tactics.' + '\nYou must realize that someone has to bear the attack in front.'
        else:
            message = None
        response = self.planner_bot.query(self.system_content, self.task_content if message==None else result_message, maintain_history=False)

        return response
    


    def update_history(self, name, score):
        if name not in self.tactic_history:
            self.tactic_history[name] = (score, 1)
        else:
            avg_score = self.tactic_history[name][0]
            times = self.tactic_history[name][1]
            new_score = (avg_score * times + score) / (times + 1) 
            self.tactic_history[name] = (new_score, times+1)

    def retrival_information(self, tactic):
        retrived_name = re.findall(r'### Tactic (.*?)\n', tactic, re.DOTALL)
        return [t.split(': ')[1] for t in retrived_name]