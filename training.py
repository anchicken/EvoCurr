from api.LLMCoder import LLMCoder
from api.LLMPlanner import LLMPlanner
from api.LLMSummarizer import LLMSummarizer
from api.LLMChecker import LLMChecker
import json
import os
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from LLM.call_llm_api.call_llm import main_logger
import shutil
from configs.rollout_config import wining_rate
import config

def copy_and_rename_files(file_list, target_folder, prefix="success"):
    """
    复制文件到目标文件夹并按顺序重命名（保留原始扩展名）
    """
    os.makedirs(target_folder, exist_ok=True)
    
    # 获取已有文件数量
    existing_count = len([f for f in os.listdir(target_folder) 
                         if os.path.isfile(os.path.join(target_folder, f))])
    
    success_count = 0
    for i, file_path in enumerate(file_list):
        try:
            if os.path.exists(file_path):
                # 生成新文件名
                file_number = existing_count + i + 1
                new_filename = f"{prefix}.py"
                target_path = os.path.join(target_folder, new_filename)
                
                # 复制文件
                shutil.copy2(file_path, target_path)
                print(f"✓ 复制: {file_path} -> {target_path}")
                success_count += 1
            else:
                print(f"✗ 文件不存在: {file_path}")
        except Exception as e:
            print(f"✗ 复制文件失败 {file_path}: {e}")

def test_training(test_tech_table, log_dir):


    # os.popen('rm -rf res-*')
    # os.popen('rm -rf *.log')
    # os.popen("rm -rf combat*.json")
    config.reload_config()
    # planner = LLMPlanner(test_tech_table)
    
    tactics_times = 1
    restart_times = 3
    generate_times = 15
    tactics = ''
    promotion = ''
    result = None
    bug_time = 0

    
    # for tactic_idx in range(tactics_times):

    #     tactics = ''
    #     promotion = ''
    #     # shutil.copy2('pre_code.py', 'res-temp.py')
    #     result = None

    #     tactics = planner.plan(result)
    #     main_logger.info(tactics)

    #     for plan_idx in range(plan_times):

    #         main_logger.info('---------------------Planning---------------------')
    #         print('---------------------Planning---------------------')

    #         if tactic_change:
    #             tactics = planner.plan(result, tactics, promotion)
    #             tactic_change = False
    #             main_logger.info(tactics)
    #         print(tactics)

            
    #         coder = LLMCoder(test_tech_table)
    #         # Generate code 5 rounds.
    #         for iter_idx in range(generate_times):

    #             main_logger.info('##################### Generating #####################')
    #             print('##################### Generating #####################')

    #             code = coder.generate_code(tactics, promotion)
    #             main_logger.info('The basic code is:\n' + code)

    #             if code == None:
    #                 main_logger.debug('The on_step function defination is wrong. Re-generate the code.')
    #                 print('The on_step function defination is wrong. Re-generate the code.')
    #                 continue


    #             # main_logger.info('********************* Checking *********************')
    #             # print('********************* Checking *********************')
    #             # checker = LLMChecker(test_tech_table)
    #             # code = checker.check_code(code)
    #             # main_logger.info('The fixed code is:\n' + code)


    #             data = coder.test_code(plan_idx, iter_idx)
    #             if data['type'] == 'bug':
    #                 # TODO
    #                 result = 'There have bug in code.\n' + data['message']
    #             else:
    #                 result = data['message']
    #                 if isinstance(result, dict) and (result.get('win') / result.get('times')) >= wining_rate:
    #                     shutil.copy2('res-temp.py', 'pre_code.py')
    #                     files_to_copy = ['pre_code.py']
    #                     copy_and_rename_files(files_to_copy, log_dir, "success")
    #                     main_logger.debug('Achieve Winning results, process terminated')
    #                     print('Achieve Winning results, process terminated')
    #                     return result
                    
    #             main_logger.info('!!!!!!!!!!!!!!!!!!!!! Summarizing !!!!!!!!!!!!!!!!!!!!!')
    #             print('!!!!!!!!!!!!!!!!!!!!! Summarizing !!!!!!!!!!!!!!!!!!!!!')
                
    #             if iter_idx != generate_times -1 :
    #                 summarizer = LLMSummarizer(test_tech_table)
    #                 promotion = summarizer.summarize(code, tactics, result)
    #                 print(promotion)

    #             if 'Change Tactic' in promotion:
    #                 tactic_change = True
    #                 break

    for restart_idx in range(restart_times):
        coder = LLMCoder(test_tech_table)
        shutil.copy2('pre_code.py', 'res-temp.py')

        for iter_idx in range(generate_times):

            main_logger.info('##################### Generating #####################')
            print('##################### Generating #####################')

            code = coder.generate_code(promotion)
            main_logger.info('The basic code is:\n' + code)

            if code == None:
                main_logger.debug('The on_step function defination is wrong. Re-generate the code.')
                print('The on_step function defination is wrong. Re-generate the code.')
                continue
            data = coder.test_code(restart_idx, iter_idx)
            if data['type'] == 'bug':
                # TODO
                bug_time += 1
                result = 'There have bug in code.\n' + data['message']
            else:
                result = data['message']
                bug_time = 0
                if isinstance(result, dict) and (result.get('win') / result.get('times')) >= wining_rate:
                    shutil.copy2('res-temp.py', 'pre_code.py')
                    files_to_copy = ['pre_code.py']
                    copy_and_rename_files(files_to_copy, log_dir, "success")
                    main_logger.debug('Achieve Winning results, process terminated')
                    print('Achieve Winning results, process terminated')
                    return result
            
            if bug_time == 4:
                break
            main_logger.info('!!!!!!!!!!!!!!!!!!!!! Summarizing !!!!!!!!!!!!!!!!!!!!!')
            print('!!!!!!!!!!!!!!!!!!!!! Summarizing !!!!!!!!!!!!!!!!!!!!!')
            
            if iter_idx != generate_times -1 :
                summarizer = LLMSummarizer(test_tech_table)
                promotion = summarizer.summarize(code, result)
                print(promotion)


    return result

if __name__ == '__main__':

    test_training()
    

    
